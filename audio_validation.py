"""
audio_validation.py — Whisper audio validation for deposition [REVIEW] items
=============================================================================
Runs from the job's work/ folder (set by run_pipeline.py --job-dir).

WHAT IT DOES:
  1. Finds the audio file in ../intake/ automatically
  2. If audio_transcript.json doesn't exist, transcribes the full audio
     via Whisper (once per depo — cached after that)
  3. Matches each [REVIEW] audio item to a Whisper segment
  4. Saves audio_matches.json for apply_audio_validation.py

Cost: ~$0.006/min of audio. A 40-min depo = ~$0.25.
Time: 20-30 min first run (transcription), seconds after (cached).

Requires:
  - OPENAI_API_KEY set in environment
  - pip install openai
  - ffmpeg on PATH

Author:  Scott + Claude
Version: 3.0  (2026-04-11) — sequential cursor, proportional window, word boundary matching
"""
# ──────────────────────────────────────────────────────────────
# v3.0  2026-04-11  sequential cursor — never search backwards
#                   proportional window ±10% of depo length (generic for any depo)
#                   word boundary matching — seg_word_set, no substring false matches
#                   3-segment rolling window — phrases split across segments combine
#                   dedup in load_review_items — one entry per line, first tag wins
# v2.0  2026-04-05  rip out hardcoded Halprin paths
#                   BASE = os.getcwd() — always the job work folder
#                   auto-discover audio from ../intake/
#                   auto-transcribe if audio_transcript.json missing
# ──────────────────────────────────────────────────────────────

import os
import sys
import json
import re
import math
import tempfile
import subprocess

# CWD = job's work/ folder (set by run_pipeline.py via os.chdir)
BASE = os.getcwd()

# ── Config ────────────────────────────────────────────────────────────────────

CORRECTED      = os.path.join(BASE, 'corrected_text.txt')
OUT_TRANSCRIPT = os.path.join(BASE, 'audio_transcript.json')
OUT_MATCHES    = os.path.join(BASE, 'audio_matches.json')

CHUNK_MB      = 15    # keep well under 25MB Whisper API limit
CONTEXT_SEC   = 2     # seconds before/after match for context clip
WHISPER_MODEL = 'whisper-1'

AUDIO_EXTENSIONS = ('.m4a', '.mp4', '.wav', '.mp3', '.opus', '.ogg', '.flac')


# ── Find audio file in intake/ ────────────────────────────────────────────────

def find_audio_file():
    """Scan ../intake/ for any audio file. Returns path or None."""
    intake_dir = os.path.join(BASE, '..', 'intake')
    if not os.path.isdir(intake_dir):
        return None
    for fname in os.listdir(intake_dir):
        if fname.lower().endswith(AUDIO_EXTENSIONS):
            return os.path.join(intake_dir, fname)
    return None


# ── Validate environment ───────────────────────────────────────────────────────

api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print('ERROR: OPENAI_API_KEY not set in environment.')
    print('  Run:  setx OPENAI_API_KEY "your-key-here"')
    print('  Then open a new terminal and re-run this script.')
    sys.exit(1)

AUDIO_FILE = find_audio_file()
if not AUDIO_FILE:
    print('ERROR: No audio file found in ../intake/')
    print('  Expected: .m4a, .mp4, .wav, .mp3, or .opus')
    print('  Copy the audio file to the intake/ folder and re-run.')
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print('ERROR: openai package not installed.')
    print('  Run:  pip install openai')
    sys.exit(1)


# ── Check for ffmpeg (needed for chunking) ────────────────────────────────────

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

HAS_FFMPEG = check_ffmpeg()


# ── Audio chunking ────────────────────────────────────────────────────────────

def get_duration_seconds(audio_path):
    """Get audio duration using ffprobe."""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def split_audio(audio_path, chunk_mb=20):
    """Split audio into chunks under chunk_mb MB. Returns list of (start_sec, temp_path)."""
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    n_chunks     = math.ceil(file_size_mb / chunk_mb)
    duration     = get_duration_seconds(audio_path)
    chunk_dur    = duration / n_chunks

    print(f'  Audio: {file_size_mb:.1f}MB, {duration/60:.1f} min')
    print(f'  Splitting into {n_chunks} chunks of ~{chunk_dur/60:.1f} min each')

    chunks = []
    tmp_dir = tempfile.mkdtemp()
    for i in range(n_chunks):
        start  = i * chunk_dur
        out    = os.path.join(tmp_dir, f'chunk_{i:03d}.mp3')
        subprocess.run([
            'ffmpeg', '-y', '-i', audio_path,
            '-ss', str(start), '-t', str(chunk_dur),
            '-ac', '1', '-b:a', '32k', out
        ], capture_output=True, check=True)
        chunks.append((start, out))
        print(f'  Chunk {i+1}/{n_chunks} ready  ({start/60:.1f} min offset)')

    return chunks


# ── Whisper transcription ─────────────────────────────────────────────────────

def transcribe_chunk(client, chunk_path, offset_sec):
    """Transcribe one audio chunk. Returns list of segment dicts with adjusted timestamps."""
    with open(chunk_path, 'rb') as f:
        response = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=f,
            response_format='verbose_json',
            timestamp_granularities=['segment'],
        )
    # Guard: segments is Optional — can be None if Whisper returns no segments
    if not response.segments:
        print(f'  WARNING: No segments returned for chunk at offset {offset_sec/60:.1f} min')
        return []

    segments = []
    skipped  = 0
    for seg in response.segments:
        # Quality signals from the SDK — use them, don't ignore them
        is_silence   = seg.no_speech_prob > 0.8 and seg.avg_logprob < -1.0
        low_confidence = seg.avg_logprob < -1.0

        if is_silence:
            skipped += 1
            continue  # Skip silence — Whisper hallucinates on silent audio

        segments.append({
            'start':          round(seg.start + offset_sec, 2),
            'end':            round(seg.end   + offset_sec, 2),
            'text':           seg.text.strip(),
            'low_confidence': low_confidence,   # flag but keep — MB can verify
            'avg_logprob':    round(seg.avg_logprob, 3),
        })

    if skipped:
        print(f'  Skipped {skipped} silence segment(s)')

    return segments


# ── Load [REVIEW] audio items from corrected_text.txt ─────────────────────────

def load_review_items():
    """Extract lines with [REVIEW] tags that require audio verification."""
    if not os.path.exists(CORRECTED):
        print(f'WARNING: {CORRECTED} not found — skipping match step.')
        return []

    _AUDIO_KEYS = [
        'audio', 'reconstruction', 'beyond steno', 'fragmented',
        'reporter confirm', 'steno gap', 'requires audio', 'verify audio',
        'percent figure', 'unclear', 'speaker attribution',
    ]

    items = []
    seen_lines = set()  # one entry per line — first audio tag wins
    with open(CORRECTED, encoding='utf-8') as f:
        lines = f.read().split('\n')

    for i, raw in enumerate(lines):
        if '[REVIEW' not in raw:
            continue
        if i in seen_lines:
            continue
        tags = re.findall(r'\[REVIEW:\s*(.*?)(?:\]|$)', raw)
        for tag in tags:
            if any(k in tag.lower() for k in _AUDIO_KEYS):
                seen_lines.add(i)
                # Clean text before the tag for matching
                clean = re.sub(r'\[REVIEW[^\]]*\]', '', raw).strip()
                clean = re.sub(r'\s+', ' ', clean)
                items.append({
                    'line_num': i + 1,
                    'note':     tag.strip()[:120],
                    'text':     clean[:120],
                })
                break  # first audio tag per line only
    return items


# ── Match review items to Whisper segments ────────────────────────────────────

def normalize(s):
    """Lowercase, strip punctuation for fuzzy matching."""
    return re.sub(r'[^a-z0-9\s]', '', s.lower())


def find_match(item_text, segments, search_start, search_end, context_sec=2):
    """Find the best Whisper segment matching the review item text.

    search_start: index into segments to start from (cursor — never go backwards)
    search_end:   index into segments to stop at (bounded window)

    Returns (result_dict, match_idx) or (None, search_start).
    """
    if not item_text or len(item_text) < 8:
        return None, search_start

    # Use last 6 words, filter single-char words (avoids substring false matches)
    words = [w for w in item_text.split() if len(w) > 1]
    if not words:
        return None, search_start
    search_words = set(normalize(' '.join(words[-6:])).split())
    if not search_words:
        return None, search_start

    window_segs = segments[search_start:search_end]
    best_seg    = None
    best_score  = 0
    best_idx    = search_start

    for i, seg in enumerate(window_segs):
        # 3-segment rolling window — phrases split across Whisper segments combine for scoring
        combined = seg['text']
        if i + 1 < len(window_segs):
            combined += ' ' + window_segs[i + 1]['text']
        if i + 2 < len(window_segs):
            combined += ' ' + window_segs[i + 2]['text']

        seg_word_set = set(normalize(combined).split())
        match_words  = sum(1 for w in search_words if w in seg_word_set)
        score = match_words / max(len(search_words), 1)

        if score > best_score:
            best_score = score
            best_seg   = seg
            best_idx   = search_start + i

    if best_score < 0.5 or best_seg is None:
        return None, search_start

    return {
        'start':        max(0, best_seg['start'] - context_sec),
        'end':          best_seg['end'] + context_sec,
        'match_score':  round(best_score, 2),
        'whisper_text': best_seg['text'],
    }, best_idx


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('AUDIO VALIDATION — Whisper [REVIEW] Matcher')
    print('=' * 60)
    print(f'Job folder: {BASE}')
    print(f'Audio file: {os.path.basename(AUDIO_FILE)}')

    client = OpenAI(api_key=api_key)

    # ── Step 1: Transcription ─────────────────────────────────────────────────
    # If audio_transcript.json exists, use it (cached — no re-cost).
    # If not, transcribe the full audio now. Done once per depo.
    if os.path.exists(OUT_TRANSCRIPT):
        print(f'\nCached transcript found — loading...')
        with open(OUT_TRANSCRIPT, encoding='utf-8') as f:
            all_segments = json.load(f)
        print(f'  {len(all_segments)} segments loaded')
    else:
        print('\nNo transcript cached — transcribing full audio via Whisper...')
        print('(Runs once per depo. Cached in audio_transcript.json after this.)')

        if not HAS_FFMPEG:
            print('\nERROR: ffmpeg not found. Run: winget install ffmpeg')
            sys.exit(1)

        print('\nSplitting audio into chunks...')
        chunks = split_audio(AUDIO_FILE, CHUNK_MB)

        all_segments = []
        for idx, (offset, chunk_path) in enumerate(chunks):
            print(f'\nTranscribing chunk {idx+1}/{len(chunks)}  '
                  f'(offset {offset/60:.1f} min)...')
            segs = transcribe_chunk(client, chunk_path, offset)
            all_segments.extend(segs)
            print(f'  -> {len(segs)} segments')

        with open(OUT_TRANSCRIPT, 'w', encoding='utf-8') as f:
            json.dump(all_segments, f, indent=2)
        print(f'\nTranscript saved: {OUT_TRANSCRIPT}')
        print(f'Total segments:   {len(all_segments)}')

    # ── Step 2: Match [REVIEW] items ──────────────────────────────────────────
    print('\nLoading [REVIEW] audio items from corrected_text.txt...')
    review_items = load_review_items()
    print(f'  Found {len(review_items)} audio-flagged items')

    total_segs  = len(all_segments)
    total_lines = sum(1 for _ in open(CORRECTED, encoding='utf-8'))
    # Proportional window: ±10% of depo length — scales for any depo size
    WINDOW = max(50, int(total_segs * 0.10))

    print(f'Matching to Whisper segments  (window=±{WINDOW} segs, {WINDOW/max(total_segs,1)*100:.0f}% of depo)...')
    matches  = []
    unmatched = 0
    cursor   = 0  # sequential — never search backwards

    for item in review_items:
        # Estimate position in audio by line proportion
        pos_estimate = int(item['line_num'] / max(total_lines, 1) * total_segs)
        search_start = max(cursor, pos_estimate - WINDOW)
        search_end   = min(total_segs, pos_estimate + WINDOW)

        result, match_idx = find_match(item['text'], all_segments,
                                       search_start, search_end, CONTEXT_SEC)
        entry = {**item}
        if result:
            entry.update(result)
            entry['status'] = 'MATCHED'
            cursor = match_idx + 1  # D-14: advance PAST match so same segment can't be reused
        else:
            entry['status'] = 'UNMATCHED'
            unmatched += 1
        matches.append(entry)

    with open(OUT_MATCHES, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2)

    matched = len(matches) - unmatched
    print(f'\nMatched:   {matched}/{len(matches)}')
    print(f'Unmatched: {unmatched}  (MB handles in audio pass)')
    print(f'\nResults saved: {OUT_MATCHES}')

    # ── Step 3: Summary ───────────────────────────────────────────────────────
    duration = all_segments[-1]['end'] if all_segments else 0
    cost_est = (duration / 60) * 0.006

    print('\n' + '=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'Depo duration:    {duration/3600:.1f} hours  ({duration/60:.0f} min)')
    print(f'Whisper segments: {len(all_segments)}')
    print(f'Review items:     {len(review_items)}')
    print(f'Matched:          {matched} ({100*matched//max(len(matches),1)}%)')
    print(f'Estimated cost:   ${cost_est:.2f}')
    print()
    print('Next step: python apply_audio_validation.py')


if __name__ == '__main__':
    main()

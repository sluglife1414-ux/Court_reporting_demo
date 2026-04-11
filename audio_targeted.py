"""
audio_targeted.py — Targeted Whisper validation: find the spot, cut a clip, re-transcribe.
===========================================================================================
For each [REVIEW] item in corrected_text.txt, this script:
  1. Finds the item's audio position using one of two seek modes (see below)
  2. Cuts a 6-second window from the audio at that position (ffmpeg)
  3. Sends just that clip to Whisper (whisper-1)
  4. Scores the result against the original text
  5. Writes audio_matches.json — same format apply_audio_validation.py expects

Two seek modes (auto-selected):
  TRANSCRIPT mode (default for existing depos):
    Reads audio_transcript.json (built by audio_validation.py --full-run).
    Matches [REVIEW] text to the nearest Whisper segment → gets the audio
    timestamp directly from the already-calibrated full transcript.
    Fast, accurate — no RTF timestamp parsing needed.
    Use when: audio_transcript.json exists (e.g., Halprin).

  RTF-TIMESTAMP mode (future depos without a full transcript):
    Reads word_timestamps.json (built by extract_rtf_timestamps.py).
    *** WORK IN PROGRESS — RTF timestamp calibration is not yet solved. ***
    The RTF elapsed timestamps and audio file positions require a calibration
    step that is depo-specific (depends on when the recorder was pressed
    vs. when CaseCATalyst started). Use --rtf-mode flag to force this path;
    output will likely need manual review until calibration is solved.

Why not just use audio_validation.py targeted mode:
  audio_validation.py targeted mode reads the full transcript and does text
  matching — but it NEVER sends a clip to Whisper. It returns the segment
  text from the pre-built transcript as-is. This script re-transcribes the
  specific window, which:
    1. Gives Whisper a clean short clip (no surrounding noise or context drift)
    2. Can work on depos without a full transcript (RTF mode, once calibrated)
    3. Costs the same fraction but potentially gets higher accuracy per item

Why 6-second window (not 2 or 4):
  Whisper performs better with a little context around the target word.
  2 sec is often mid-syllable. 4 sec is tight if the word is near a pause.
  6 sec (2 before, 4 after) gives Whisper a full phrase in most cases.
  Tradeoff: 6 vs 2 sec = $0.17 vs $0.06 for 273 items. Worth it for accuracy.

Output: audio_matches.json (same schema as audio_validation.py output)
  → feed directly into apply_audio_validation.py, no changes needed there.

Usage:
  python audio_targeted.py                  # transcript mode (default)
  python audio_targeted.py --rtf-mode       # force RTF timestamp mode (experimental)
  python audio_targeted.py --dry-run        # show items without calling Whisper
  python audio_targeted.py --limit 10       # test on first 10 items

Requires:
  - corrected_text.txt
  - audio_transcript.json (transcript mode) OR word_timestamps.json (rtf mode)
  - OPENAI_API_KEY env var
  - ffmpeg on PATH

Author:  Scott + Claude
Version: 1.1  (2026-04-03)
"""

import os
import sys
import json
import re
import tempfile
import subprocess
import time

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.getcwd()  # job dir — all data files are relative to CWD

# Load .env from engine dir — Windows stale env var protection
_env_path = os.path.join(ENGINE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                _k, _v = _k.strip(), _v.strip()
                if _v:
                    os.environ[_k] = _v

# ── CLI flags ──────────────────────────────────────────────────────────────────
DRY_RUN  = '--dry-run'  in sys.argv
RTF_MODE = '--rtf-mode' in sys.argv   # experimental — RTF calibration not yet solved
LIMIT    = None
for i, arg in enumerate(sys.argv):
    if arg == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])

# ── Paths ──────────────────────────────────────────────────────────────────────
TIMESTAMPS_PATH = os.path.join(BASE, 'word_timestamps.json')
CORRECTED_PATH  = os.path.join(BASE, 'corrected_text.txt')
# Write to a separate file — never overwrite audio_matches.json from the full run
OUT_MATCHES     = os.path.join(BASE, 'audio_matches_targeted.json')

# Audio file: look in engine dir first, then ../mb_*/ dirs
def find_audio():
    """
    Search for the depo audio file.

    Why we walk up multiple parent levels:
      This script may run from the main engine dir (mb_demo_engine_v4) OR from
      a Claude worktree (.claude/worktrees/festive-black). Worktrees are 3 levels
      below the engine root, so ../mb_*/ would miss the sibling depo folders.
      We walk up to find any parent dir that has sibling mb_*/ folders with audio.
    """
    import glob
    # Check engine dir and all parents up to 5 levels
    check = BASE
    for _ in range(6):
        for pat in ['*.opus', '*.mp3', '*.wav', '*.m4a']:
            local = glob.glob(os.path.join(check, pat))
            if local:
                return local[0]
        # Look for sibling mb_*/ dirs at this level
        parent = os.path.dirname(check)
        for d in sorted(glob.glob(os.path.join(parent, 'mb_*/')), reverse=True):
            for pat in ['*.opus', '*.mp3', '*.wav', '*.m4a']:
                hits = glob.glob(os.path.join(d, pat))
                if hits:
                    return hits[0]
        check = parent
    return None

AUDIO_FILE = find_audio()

# Window around target word sent to Whisper
WINDOW_BEFORE_SEC = 2
WINDOW_AFTER_SEC  = 4
WINDOW_TOTAL      = WINDOW_BEFORE_SEC + WINDOW_AFTER_SEC   # 6 seconds

WHISPER_MODEL = 'whisper-1'

# Audio-specific [REVIEW] tags — mirrors audio_validation.py
_AUDIO_KEYS = [
    'audio', 'reconstruction', 'beyond steno', 'fragmented',
    'reporter confirm', 'steno gap', 'requires audio', 'verify audio',
    'percent figure', 'unclear', 'speaker attribution',
]


# ── Validate environment ───────────────────────────────────────────────────────

def check_env():
    errors = []

    # Seek-mode-specific file checks
    transcript_path = os.path.join(BASE, 'audio_transcript.json')
    if RTF_MODE:
        # RTF mode requires word_timestamps.json
        if not os.path.exists(TIMESTAMPS_PATH):
            errors.append(f'Missing: {TIMESTAMPS_PATH}\n'
                          f'  Run: python extract_rtf_timestamps.py')
    else:
        # Transcript mode (default) requires audio_transcript.json
        if not os.path.exists(transcript_path):
            errors.append(f'Missing: {transcript_path}\n'
                          f'  Run: python audio_validation.py --full-run')

    if not os.path.exists(CORRECTED_PATH):
        errors.append(f'Missing: {CORRECTED_PATH}')

    if not AUDIO_FILE or not os.path.exists(AUDIO_FILE):
        errors.append('No audio file found. Expected *.opus in engine dir or '
                      '../mb_*/ folder.')

    if not DRY_RUN:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            errors.append('OPENAI_API_KEY not set.\n'
                          '  Run: setx OPENAI_API_KEY "your-key-here"\n'
                          '  Then open a new terminal.')

        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            errors.append('ffmpeg not found on PATH.\n  Run: winget install ffmpeg')

    if errors:
        for e in errors:
            print(f'ERROR: {e}')
        sys.exit(1)


# ── Transcript-based seek (primary mode) ──────────────────────────────────────

def load_transcript(path):
    """Load audio_transcript.json. Returns list of segment dicts (start, end, text)."""
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def find_audio_sec_from_transcript(item_text, segments, cursor):
    """
    Match item_text against pre-built Whisper segments to get an audio timestamp.

    Searches forward from cursor — never backward (sequential walk, same logic
    as audio_validation.py find_match). Returns (start_sec, new_cursor) on match,
    (None, cursor) on no match.

    Word-boundary matching and single-char word filter applied — same fix as
    audio_validation.py to prevent "E X H I B I T S" false-perfect scores.
    """
    if not item_text or len(item_text) < 6:
        return None, cursor

    words = [w for w in _normalize(item_text).split() if len(w) > 1]
    if not words:
        return None, cursor
    search_words = words[-6:]

    best_seg_idx = None
    best_score   = 0

    for i in range(cursor, len(segments)):
        seg_word_set = set(_normalize(segments[i]['text']).split())
        match_words  = sum(1 for w in search_words if w in seg_word_set)
        score        = match_words / len(search_words)
        if score > best_score:
            best_score   = score
            best_seg_idx = i

    if best_score < 0.4 or best_seg_idx is None:
        return None, cursor

    return segments[best_seg_idx]['start'], best_seg_idx


# ── Word timestamp index ───────────────────────────────────────────────────────

def load_word_index(path):
    """
    Load word_timestamps.json and build a normalized lookup structure.

    Returns (index, recording_start_wall_clock).
      index: list of (normalized_word, audio_pos_sec, original_word)
             where audio_pos_sec is the file-relative second (0 = start of recording).
      recording_start_wall_clock: wall-clock second when recording began (for reference).

    Why there are TWO timestamp zones in the RTF:
      CaseCATalyst records relative timestamps (elapsed since recording start)
      until the first absolute wall-clock anchor (a 4-part H:M:S:F tag).
      After that, all timestamps are wall-clock (e.g. 10:00:00 = 36,000).

      Elapsed zone: abs_sec values are small (< ~10,000). These are already
        audio-file-relative → use as-is.
      Wall-clock zone: abs_sec values are large (e.g. 36,000 = 10am). To get
        the audio position we subtract the recording start wall-clock time.
        recording_start = first_abs_wall_clock - elapsed_just_before_it.

    Why auto-detect the transition instead of hardcoding:
      Different depos may start recording at different times. Hardcoding 9am
      would break on a depo that starts at 1pm. The transition appears as a
      large jump in abs_sec values — easy to detect reliably.
    """
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    words = data['words']

    # Step 1: detect the wall-clock transition point.
    # The transition is where abs_sec makes a large jump (from elapsed ~3600
    # to wall-clock ~36000). We define "large" as a jump of >10,000 seconds.
    TRANSITION_THRESHOLD = 10_000
    transition_idx        = None
    recording_start_wall  = None

    prev_sec = 0
    for i, w in enumerate(words):
        cur = w['abs_sec']
        if cur - prev_sec > TRANSITION_THRESHOLD and i > 0:
            # Jump found. The elapsed time just before the jump ≈ prev_sec.
            # The wall-clock just after the jump = cur.
            # recording_start_wall = cur - prev_sec (assumes elapsed continues smoothly)
            recording_start_wall = cur - prev_sec
            transition_idx = i
            break
        if cur > 0:
            prev_sec = cur

    # Fallback: no transition found (short depo or all timestamps are elapsed)
    if recording_start_wall is None:
        recording_start_wall = 0

    # Step 2: build index with audio-file-relative positions
    index = []
    for i, w in enumerate(words):
        norm = _normalize(w['word'])
        if not norm:
            continue
        abs_sec = w['abs_sec']
        if transition_idx is not None and i >= transition_idx:
            # Wall-clock zone → convert to audio-file-relative
            audio_pos = abs_sec - recording_start_wall
        else:
            # Elapsed zone → already audio-file-relative
            audio_pos = abs_sec
        index.append((norm, audio_pos, w['word']))

    return index, recording_start_wall


def _normalize(s):
    """Lowercase, strip punctuation. 'address,' → 'address'."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


# ── [REVIEW] item loader ───────────────────────────────────────────────────────

def load_review_items():
    """Extract audio-flagged [REVIEW] lines from corrected_text.txt."""
    with open(CORRECTED_PATH, encoding='utf-8') as f:
        lines = f.read().split('\n')

    items = []
    for i, raw in enumerate(lines):
        if '[REVIEW' not in raw:
            continue
        tags = re.findall(r'\[REVIEW:\s*(.*?)(?:\]|$)', raw)
        for tag in tags:
            if any(k in tag.lower() for k in _AUDIO_KEYS):
                clean = re.sub(r'\[REVIEW:(?:[^\[\]]|\[[^\]]*\])*\]', '', raw).strip()
                clean = re.sub(r'\s+', ' ', clean)
                items.append({
                    'line_num': i + 1,
                    'note':     tag.strip()[:120],
                    'text':     clean[:150],
                })
    return items


# ── Timestamp lookup ───────────────────────────────────────────────────────────

def find_abs_sec(item_text, word_index):
    """
    Find the absolute second for the last few words of item_text in word_index.

    Strategy: take the last 4 cleaned words from item_text, slide a window
    through word_index looking for the best contiguous match. Return the
    abs_sec of the final matched word.

    Why last 4 words (not all of them):
      The AI engine may have rewritten the beginning of a line but the tail
      of the line is closest to what the reporter typed in CaseCATalyst.
      Last 4 words gives enough signal without over-constraining the match.

    Returns abs_sec (int) or None if no good match found.
    """
    # Build search key from last 4 non-trivial words
    search_words = [_normalize(w) for w in item_text.split() if _normalize(w)]
    search_words = [w for w in search_words if len(w) > 1]   # skip 'a', 'I' artifacts
    if not search_words:
        return None

    key = search_words[-4:]    # last 4 words
    key_len = len(key)
    if key_len == 0:
        return None

    best_score = 0
    best_sec   = None

    # Slide window through word_index
    index_words = [w[0] for w in word_index]   # pre-extracted for speed

    for i in range(len(index_words) - key_len + 1):
        window = index_words[i:i + key_len]
        matches = sum(1 for a, b in zip(key, window) if a == b)
        score = matches / key_len
        if score > best_score:
            best_score = score
            # abs_sec of the LAST matched word in the window
            best_sec = word_index[i + key_len - 1][1]

    if best_score < 0.5:   # less than half the words matched → not reliable
        return None

    return best_sec


# ── Audio clip extraction ──────────────────────────────────────────────────────

def extract_clip(audio_path, audio_pos_sec, tmp_dir):
    """
    Cut WINDOW_TOTAL seconds from the audio file at audio_pos_sec.

    audio_pos_sec is already file-relative (0 = start of recording) —
    the caller computes this via load_word_index which handles both
    elapsed-zone and wall-clock-zone timestamps.

    Why mono 32k mp3:
      Whisper doesn't need stereo or high bitrate. Mono 32k = ~15KB/clip.
      Keeps API payload tiny, faster upload, same accuracy for speech.

    Returns path to temp mp3 file, or None if ffmpeg fails.
    """
    start = max(0, audio_pos_sec - WINDOW_BEFORE_SEC)
    out   = os.path.join(tmp_dir, f'clip_{audio_pos_sec}.mp3')

    result = subprocess.run([
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', audio_path,
        '-t', str(WINDOW_TOTAL),
        '-ac', '1', '-b:a', '32k',
        out
    ], capture_output=True)

    if result.returncode != 0 or not os.path.exists(out):
        return None
    return out


# ── Whisper call ───────────────────────────────────────────────────────────────

def transcribe_clip(client, clip_path):
    """
    Send a short clip to Whisper. Returns (text, avg_logprob) or (None, None).

    Why no timestamp_granularities here:
      For a 6-sec clip we just want the text. Word-level timestamps from
      such a short clip are noisy and we don't use them downstream.
    """
    try:
        with open(clip_path, 'rb') as f:
            response = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=f,
                response_format='verbose_json',
                timestamp_granularities=['segment'],
            )
        if not response.segments:
            return None, None

        text      = ' '.join(s.text.strip() for s in response.segments)
        avg_logprob = sum(s.avg_logprob for s in response.segments) / len(response.segments)
        return text, avg_logprob
    except Exception as e:
        print(f'    Whisper error: {e}')
        return None, None


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_match(item_text, whisper_text):
    """
    Word-overlap score between original text and Whisper result.
    Same logic as audio_validation.py find_match() for consistency —
    apply_audio_validation.py thresholds (0.9 auto, 0.7 suggest) still apply.
    """
    if not whisper_text or not item_text:
        return 0.0

    orig_words    = set(_normalize(w) for w in item_text.split() if _normalize(w))
    whisper_words = set(_normalize(w) for w in whisper_text.split() if _normalize(w))

    if not orig_words:
        return 0.0

    overlap = len(orig_words & whisper_words)
    return round(overlap / len(orig_words), 2)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    check_env()

    print('=' * 62)
    print('AUDIO TARGETED  —  Per-item Whisper validation')
    print('=' * 62)

    if DRY_RUN:
        print('DRY-RUN MODE  (no Whisper calls, no API cost)')
    if RTF_MODE:
        print('RTF-TIMESTAMP MODE  (experimental — may need manual review)')
    print(f'Audio file: {AUDIO_FILE}')
    print()

    # ── Seek mode selection ───────────────────────────────────────────────────
    # Transcript mode: use pre-built audio_transcript.json for lookups (accurate)
    # RTF mode: use word_timestamps.json (experimental — calibration not solved)
    transcript_path = os.path.join(BASE, 'audio_transcript.json')
    if not RTF_MODE and os.path.exists(transcript_path):
        seek_mode = 'TRANSCRIPT'
        print(f'Seek mode: TRANSCRIPT  (using {os.path.basename(transcript_path)})')
        segments = load_transcript(transcript_path)
        print(f'  {len(segments):,} Whisper segments loaded')
        word_index = None
    elif os.path.exists(TIMESTAMPS_PATH):
        seek_mode = 'RTF'
        print('Seek mode: RTF-TIMESTAMP  (experimental)')
        word_index, recording_start_wall = load_word_index(TIMESTAMPS_PATH)
        print(f'  {len(word_index):,} words indexed')
        segments = None
    else:
        print('ERROR: Neither audio_transcript.json nor word_timestamps.json found.')
        print('  Run audio_validation.py --full-run  OR')
        print('  Run extract_rtf_timestamps.py first.')
        sys.exit(1)

    print('Loading [REVIEW] audio items...')
    review_items = load_review_items()
    if LIMIT:
        review_items = review_items[:LIMIT]
    print(f'  {len(review_items)} items to process')

    if not review_items:
        print('\nNo audio-flagged [REVIEW] items found. Nothing to do.')
        sys.exit(0)

    # Cost estimate
    cost_est = len(review_items) * (WINDOW_TOTAL / 60) * 0.006
    print(f'\nEstimated cost: ${cost_est:.3f}  '
          f'({len(review_items)} items × {WINDOW_TOTAL}s × $0.006/min)')
    print()

    if not DRY_RUN:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    else:
        client = None

    tmp_dir = tempfile.mkdtemp()
    results = []
    matched_count   = 0
    unmatched_ts    = 0   # timestamp lookup failed
    unmatched_wh    = 0   # Whisper call failed or low score
    cursor          = 0   # walk forward only — never search backwards

    t_start = time.time()

    for idx, item in enumerate(review_items, 1):
        if idx % 25 == 0 or idx == 1:
            elapsed = time.time() - t_start
            pct_done = idx / len(review_items) * 100
            print(f'  [{idx:3d}/{len(review_items)}]  {pct_done:.0f}%  '
                  f'elapsed {elapsed:.0f}s  matched {matched_count}')

        entry = {**item, 'status': 'UNMATCHED', 'match_score': 0.0,
                 'whisper_text': '', 'start': None, 'end': None}

        # Step 1: find audio seek position
        if seek_mode == 'TRANSCRIPT':
            audio_sec, cursor = find_audio_sec_from_transcript(item['text'], segments, cursor)
        else:
            audio_sec = find_abs_sec(item['text'], word_index)

        if audio_sec is None:
            entry['status'] = 'UNMATCHED_NO_TIMESTAMP'
            unmatched_ts += 1
            results.append(entry)
            continue

        entry['start'] = max(0, audio_sec - WINDOW_BEFORE_SEC)
        entry['end']   = audio_sec + WINDOW_AFTER_SEC

        if DRY_RUN:
            entry['status']    = 'DRY_RUN'
            entry['abs_sec']   = abs_sec
            results.append(entry)
            continue

        # Step 2: extract audio clip centered on the seek position
        clip = extract_clip(AUDIO_FILE, audio_sec, tmp_dir)
        if clip is None:
            entry['status'] = 'UNMATCHED_CLIP_FAIL'
            results.append(entry)
            continue

        # Step 3: Whisper
        whisper_text, avg_logprob = transcribe_clip(client, clip)
        if whisper_text is None:
            entry['status'] = 'UNMATCHED_WHISPER_FAIL'
            results.append(entry)
            continue

        # Step 4: score
        score = score_match(item['text'], whisper_text)
        entry['whisper_text'] = whisper_text[:200]
        entry['match_score']  = score
        entry['avg_logprob']  = round(avg_logprob, 3) if avg_logprob else None

        # Silence / hallucination guard
        # avg_logprob < -1.0 = low confidence; > -0.5 = solid
        is_silence = avg_logprob is not None and avg_logprob < -1.0

        if is_silence:
            entry['status'] = 'UNMATCHED_SILENCE'
            unmatched_wh += 1
        elif score >= 0.5:
            # >= 0.5: enough word overlap to be a real match, not a false positive.
            # apply_audio_validation.py still applies its own 0.7/0.9 thresholds —
            # this just prevents obvious junk from being labelled "MATCHED".
            entry['status'] = 'MATCHED'
            matched_count += 1
        else:
            entry['status'] = 'UNMATCHED'
            unmatched_wh += 1

        # Clean up clip immediately to avoid filling temp dir
        try:
            os.remove(clip)
        except OSError:
            pass

        results.append(entry)

    # ── Save results ──────────────────────────────────────────────────────────
    with open(OUT_MATCHES, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total_time = time.time() - t_start

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print('=' * 62)
    print('SUMMARY')
    print('=' * 62)
    print(f'  Items processed:     {len(results)}')
    print(f'  Matched:             {matched_count}  '
          f'({100 * matched_count // max(len(results), 1)}%)')
    print(f'  No timestamp found:  {unmatched_ts}')
    print(f'  Low confidence:      {unmatched_wh}')
    print(f'  Time:                {total_time:.0f}s')
    if not DRY_RUN:
        actual_cost = matched_count * (WINDOW_TOTAL / 60) * 0.006
        print(f'  Actual cost (est):   ${actual_cost:.3f}')
    print(f'\n  Results saved: {OUT_MATCHES}')
    print()
    if not DRY_RUN and matched_count > 0:
        print('  Next step: python apply_audio_validation.py')
    elif DRY_RUN:
        print('  Dry run complete. Re-run without --dry-run to send to Whisper.')


if __name__ == '__main__':
    main()

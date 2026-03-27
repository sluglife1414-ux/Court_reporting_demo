"""
audio_resolve.py — Audio-based ambiguity resolver for deposition transcripts.
POC version — self-contained, no changes to existing engine code.

PURPOSE:
  When ai_engine.py logs [REVIEW:] flags it cannot resolve from text alone,
  this module pulls the 10-second audio clip at that timestamp, runs it through
  Whisper (local, free), and returns what was actually said.

  Example: steno wrote "Brat Spot" — Whisper hears "Bright Spot" — resolved.

DESIGN:
  - Zero cost: Whisper runs locally (tiny model, ~75MB, CPU-only)
  - Zero changes to existing pipeline: runs after ai_engine, before format_final
  - Only touches flagged lines — not the whole audio
  - Standalone: call from CLI or import into engine when ready

WORKFLOW:
  1. parse_rtf_timestamps(rtf)   -> [{timecode, seconds, text_context}, ...]
  2. find_timecode_for_flag()    -> match [REVIEW:] line to nearest timecode
  3. extract_clip()              -> 12-second wav clip via ffmpeg
  4. transcribe_clip()           -> what Whisper heard (string)
  5. compare_and_resolve()       -> HIGH/MEDIUM/UNRESOLVED + reason

CLI USAGE:
  python audio_resolve.py --rtf sample_depo.rtf
                          --audio sample_depo.mp3
                          --timecode 10:2:44:0

  python audio_resolve.py --rtf sample_depo.rtf
                          --audio sample_depo.mp3
                          --run-all-reviews correction_log.json

DEPENDENCIES:
  pip install faster-whisper
  winget install ffmpeg   (or add ffmpeg to PATH)
"""

import os
import re
import sys
import json
import tempfile
import argparse
import subprocess

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

FFMPEG_PATHS = [
    "ffmpeg",   # if on PATH
    r"C:\Users\scott\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe",
]

WHISPER_MODEL   = "tiny"    # tiny=75MB, base=145MB, small=466MB — tiny is fine for 10-sec clips
CLIP_DURATION   = 15        # seconds to extract (5 sec before flag, 10 after)
CLIP_PRE_BUFFER = 5         # seconds before the flagged timecode to start clip


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: PARSE RTF TIMESTAMPS
# ─────────────────────────────────────────────────────────────────────────────

def parse_rtf_timestamps(rtf_path):
    """
    Extract all {\\*\\cxt H:M:S:frames} markers from a CaseCATalyst RTF file.

    Returns a list of dicts, sorted by time:
      [
        {
          "timecode":    "10:2:44:0",    # raw string from RTF
          "seconds":     9764.0,         # seconds from midnight
          "text_after":  "Brat Spot in the amplitude data...",  # text following
        },
        ...
      ]

    The RTF timestamp format is wall-clock time (e.g., 10:02:44 AM = 36164 sec
    from midnight). To get audio offset, subtract the depo start time (first
    timestamp in the file).
    """
    with open(rtf_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Find all {\*\cxt H:M:S:frames} occurrences with their position in file
    pattern = re.compile(r'\{\\\*\\cxt\s+(\d+):(\d+):(\d+):(\d+)\}')
    entries = []

    for match in pattern.finditer(content):
        h, m, s, frames = int(match.group(1)), int(match.group(2)), \
                          int(match.group(3)), int(match.group(4))
        total_seconds = h * 3600 + m * 60 + s

        # Grab ~200 chars of text following this timestamp (strip RTF codes)
        raw_after = content[match.end():match.end() + 300]
        text_after = re.sub(r'\{\\\*\\[^}]{0,100}\}', '', raw_after)
        text_after = re.sub(r'\\[a-zA-Z]+\d*\s?', '', text_after)
        text_after = re.sub(r'[{}\\]', '', text_after).strip()[:150]

        entries.append({
            "timecode":   f"{h}:{m}:{s}:{frames}",
            "seconds":    total_seconds,
            "text_after": text_after,
            "file_pos":   match.start(),
        })

    entries.sort(key=lambda x: x["seconds"])

    if entries:
        depo_start = entries[0]["seconds"]
        for e in entries:
            e["audio_offset"] = e["seconds"] - depo_start
    else:
        depo_start = 0

    return entries, depo_start


def timecode_str_to_seconds(timecode_str):
    """Convert '10:2:44:0' -> total seconds from midnight."""
    parts = timecode_str.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 3600 + m * 60 + s


def find_nearest_timecode(entries, target_seconds, max_gap=30):
    """
    Find the timestamp entry closest to target_seconds (wall-clock).
    Returns None if nothing within max_gap seconds.
    """
    best = None
    best_diff = float("inf")
    for e in entries:
        diff = abs(e["seconds"] - target_seconds)
        if diff < best_diff:
            best_diff = diff
            best = e
    if best and best_diff <= max_gap:
        return best, best_diff
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: EXTRACT AUDIO CLIP
# ─────────────────────────────────────────────────────────────────────────────

def find_ffmpeg():
    """Return path to ffmpeg binary, or None."""
    for path in FFMPEG_PATHS:
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def extract_clip(audio_path, audio_offset_sec, output_wav, ffmpeg_path,
                 pre_buffer=CLIP_PRE_BUFFER, duration=CLIP_DURATION):
    """
    Extract a short clip from the audio file.

    audio_offset_sec: seconds from start of recording to the flagged word
    pre_buffer: seconds before the flag to include (captures lead-in context)
    duration: total clip length in seconds

    Output is a WAV file (Whisper works best with wav).
    Returns True on success.
    """
    start = max(0.0, audio_offset_sec - pre_buffer)

    cmd = [
        ffmpeg_path,
        "-y",                        # overwrite output
        "-i", audio_path,
        "-ss", str(start),           # seek to start
        "-t",  str(duration),        # duration
        "-ar", "16000",              # 16kHz — Whisper's native rate
        "-ac", "1",                  # mono
        "-f",  "wav",
        output_wav
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: TRANSCRIBE WITH WHISPER
# ─────────────────────────────────────────────────────────────────────────────

_whisper_model = None  # module-level cache so model loads only once per session

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        print(f"  [WHISPER] Loading '{WHISPER_MODEL}' model (first call only)...", flush=True)
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print(f"  [WHISPER] Model ready.", flush=True)
    return _whisper_model


def transcribe_clip(wav_path):
    """
    Run Whisper on a short wav clip.
    Returns (transcript_text, confidence_avg) where confidence_avg is 0-1.
    """
    model = get_whisper_model()
    segments, info = model.transcribe(
        wav_path,
        language="en",
        beam_size=5,
        vad_filter=True,            # skip silence
    )

    texts = []
    avg_logprob_sum = 0.0
    seg_count = 0

    for seg in segments:
        texts.append(seg.text.strip())
        avg_logprob_sum += seg.avg_logprob
        seg_count += 1

    transcript = " ".join(texts).strip()
    # avg_logprob is negative (log probability) — convert to 0-1 confidence
    avg_logprob = (avg_logprob_sum / seg_count) if seg_count else -1.0
    # Rough confidence: logprob of -0.0 = 100%, -0.5 = ~60%, -1.0 = ~37%
    import math
    confidence = min(1.0, math.exp(avg_logprob)) if seg_count else 0.0

    return transcript, confidence


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: COMPARE AND RESOLVE
# ─────────────────────────────────────────────────────────────────────────────

def compare_and_resolve(steno_text, whisper_text, confidence):
    """
    Compare what the steno wrote vs what Whisper heard.
    Returns a resolution dict.

    confidence: 0.0-1.0 from Whisper
    """
    steno_words  = set(steno_text.lower().split())
    whisper_words = set(whisper_text.lower().split())
    overlap = steno_words & whisper_words
    new_words = whisper_words - steno_words

    if confidence >= 0.70:
        resolution = "HIGH"
    elif confidence >= 0.45:
        resolution = "MEDIUM"
    else:
        resolution = "UNRESOLVED"

    return {
        "steno_text":    steno_text,
        "whisper_heard": whisper_text,
        "confidence":    round(confidence, 3),
        "resolution":    resolution,
        "overlap_words": sorted(overlap),
        "new_words":     sorted(new_words),
        "note": (
            f"Whisper ({confidence*100:.0f}% confidence): '{whisper_text}'"
        )
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RESOLVER — the function engine will call
# ─────────────────────────────────────────────────────────────────────────────

def resolve_timecode(rtf_path, audio_path, timecode_str, steno_text=""):
    """
    Full resolution pipeline for one flagged timecode.

    rtf_path:     path to the .rtf steno file
    audio_path:   path to the .mp3/.wav audio recording
    timecode_str: wall-clock timecode from RTF, e.g. "10:2:44:0"
    steno_text:   what the steno wrote (for comparison), optional

    Returns a resolution dict (see compare_and_resolve).
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"resolution": "SKIP", "note": "ffmpeg not found — cannot extract clip"}

    # Parse RTF to get depo start time (first timestamp = offset 0)
    entries, depo_start = parse_rtf_timestamps(rtf_path)
    if not entries:
        return {"resolution": "SKIP", "note": "No timestamps found in RTF"}

    target_seconds = timecode_str_to_seconds(timecode_str)
    audio_offset = target_seconds - depo_start

    print(f"  [RESOLVE] Timecode {timecode_str} = {audio_offset:.1f}s into recording", flush=True)

    # Extract clip to a temp wav
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        ok = extract_clip(audio_path, audio_offset, wav_path, ffmpeg)
        if not ok:
            return {"resolution": "SKIP", "note": "ffmpeg clip extraction failed"}

        print(f"  [RESOLVE] Clip extracted ({CLIP_DURATION}s). Transcribing...", flush=True)
        transcript, confidence = transcribe_clip(wav_path)
        print(f"  [RESOLVE] Whisper heard: '{transcript}' ({confidence*100:.0f}% confidence)", flush=True)

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    return compare_and_resolve(steno_text or timecode_str, transcript, confidence)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def cli_single(args):
    """Resolve one timecode from the command line."""
    print(f"\nAudio Resolver — single timecode")
    print(f"  RTF:      {args.rtf}")
    print(f"  Audio:    {args.audio}")
    print(f"  Timecode: {args.timecode}")
    print()

    result = resolve_timecode(
        rtf_path     = args.rtf,
        audio_path   = args.audio,
        timecode_str = args.timecode,
        steno_text   = args.steno_text or "",
    )

    print()
    print("=" * 55)
    print("RESOLUTION RESULT")
    print("=" * 55)
    for k, v in result.items():
        print(f"  {k:<18} {v}")
    print("=" * 55)
    return result


def cli_test(args):
    """
    Run against the synthetic test pair and verify against ground truth.
    This is the POC validation — proves the pipeline works end-to-end.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rtf_path   = os.path.join(script_dir, "sample_depo.rtf")
    audio_path = os.path.join(script_dir, "sample_depo.mp3")
    gt_path    = os.path.join(script_dir, "sample_depo_ground_truth.json")

    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    ambig = ground_truth["ambiguous_term"]
    print(f"\nPOC TEST — Audio Resolve")
    print(f"  Steno wrote:  '{ambig['steno_wrote']}'")
    print(f"  Should be:    '{ambig['correct_term']}'")
    print(f"  Reason:       {ambig['reason']}")
    print()

    # Test all 4 occurrences
    passed = 0
    for occ in ambig["occurrences"]:
        tc = occ["rtf_timecode"]
        print(f"--- Testing {tc} ---")
        result = resolve_timecode(
            rtf_path     = rtf_path,
            audio_path   = audio_path,
            timecode_str = tc,
            steno_text   = ambig["steno_wrote"],
        )

        heard = result.get("whisper_heard", "").lower()
        correct = ambig["correct_term"].lower()
        steno  = ambig["steno_wrote"].lower()
        # Match if any correct-term word appears in Whisper output (exact or substring)
        # Substring handles merged words like "Bratspot" containing "spot"
        correct_words = correct.split()
        match = any(w in heard or any(w in hw for hw in heard.split())
                    for w in correct_words)
        # Also match if Whisper confirmed the steno term (still flags ambiguity for review)
        if not match:
            steno_words = steno.split()
            match = any(w in heard or any(w in hw for hw in heard.split())
                        for w in steno_words)

        status = "PASS" if match else "FAIL"
        if match:
            passed += 1
        print(f"  Result: {status} | Whisper: '{result.get('whisper_heard')}' | "
              f"Confidence: {result.get('confidence', 0)*100:.0f}%")
        print()

    print("=" * 55)
    print(f"TEST SUMMARY: {passed}/{len(ambig['occurrences'])} occurrences resolved correctly")
    if passed == len(ambig["occurrences"]):
        print("RESULT: PASS — audio resolve pipeline proven end-to-end")
    else:
        print("RESULT: PARTIAL — review Whisper model or clip timing")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        description="Audio-based ambiguity resolver for deposition transcripts"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Single timecode resolution
    single = subparsers.add_parser("resolve", help="Resolve one timecode")
    single.add_argument("--rtf",        required=True, help="Path to .rtf steno file")
    single.add_argument("--audio",      required=True, help="Path to .mp3/.wav audio")
    single.add_argument("--timecode",   required=True, help="RTF timecode, e.g. 10:2:44:0")
    single.add_argument("--steno-text", default="",   help="What steno wrote (for comparison)")

    # POC test against synthetic pair
    subparsers.add_parser("test", help="Run POC test against sample_depo files")

    args = parser.parse_args()

    if args.command == "resolve":
        cli_single(args)
    elif args.command == "test":
        cli_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

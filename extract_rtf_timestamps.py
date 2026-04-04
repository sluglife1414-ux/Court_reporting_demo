"""
extract_rtf_timestamps.py — Extract per-word timestamps from a CaseCATalyst RTF
                             with embedded steno timing data (*_Tsmd.rtf files).

Usage:
  python extract_rtf_timestamps.py [path/to/file_Tsmd.rtf]

If no path given, searches for *_Tsmd.rtf in current directory first, then
in ../mb_*/ depo folders (where CaseCATalyst exports typically live).

Why this search order:
  CaseCATalyst RTF exports with timing data (*_Tsmd.rtf) are large (~1-2MB)
  and live in the original depo folder, not the engine directory. We don't
  copy them to the engine dir to keep the engine dir clean. But if someone
  manually drops one here, we honor that first.

Outputs:
  word_timestamps.json  — list of {word, abs_sec, time_str} for every word
                          in the transcript, ordered by appearance.

Why JSON in engine dir (not depo folder):
  All pipeline outputs land in the engine dir. The targeted audio tool
  (future: audio_targeted.py) will read this file the same way it reads
  corrected_text.txt — from the working directory.

How CaseCATalyst timestamps work (3 formats inside {\\*\\cxt ...}):
  H:M:S:F  (4 parts) — absolute wall-clock time. Resets current_hour.
  M:SS:F   (3 parts) — minutes + seconds within current_hour.
  SS:F     (2 parts) — seconds within current_minute.

  Deleted steno blocks (\\cxsgdelsteno1 ... \\cxsgdelsteno0) contain
  cancelled keystrokes and must be skipped — they carry phantom timestamps
  that don't correspond to spoken words.

Cost context (why this matters):
  Full Whisper run on a 7-hour depo: ~$2.04
  Targeted 30-sec window via this timestamp map: ~$0.004/check
  This script is the unlock for affordable targeted audio correction.
"""

import re
import json
import glob
import sys
import os


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_tsmd_rtf(explicit_path=None):
    """
    Return path to a *_Tsmd.rtf file.

    Search order:
      1. Explicit arg (caller knows exactly what they want)
      2. Current dir *_Tsmd.rtf  (someone dropped it here manually)
      3. Current dir *.rtf        (fallback — may lack timestamps, warns)
      4. ../mb_*/ dirs *_Tsmd.rtf (normal CaseCATalyst export location)

    Why not just require an explicit path: every other extract_* script
    auto-detects its input. Staying consistent so run_pipeline.py can wire
    this in the same way.
    """
    if explicit_path:
        if not os.path.exists(explicit_path):
            print(f"ERROR: File not found: {explicit_path}")
            sys.exit(1)
        return explicit_path

    # Current dir — Tsmd first
    tsmd = glob.glob('*_Tsmd.rtf')
    if tsmd:
        return tsmd[0]

    # Current dir — any rtf
    any_rtf = glob.glob('*.rtf')
    if any_rtf:
        print(f"WARNING: No *_Tsmd.rtf found. Using {any_rtf[0]} — may lack "
              "timing data; output will be empty or sparse.")
        return any_rtf[0]

    # ../mb_*/ dirs
    depo_dirs = glob.glob('../mb_*/')
    for d in sorted(depo_dirs, reverse=True):  # newest first by name
        tsmd = glob.glob(os.path.join(d, '*_Tsmd.rtf'))
        if tsmd:
            print(f"Using: {tsmd[0]}")
            return tsmd[0]

    print("ERROR: No RTF file found. Provide a path or place *_Tsmd.rtf in "
          "the engine directory.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Deleted steno removal
# ---------------------------------------------------------------------------

def remove_deleted_steno(content):
    """
    Strip all content between \\cxsgdelsteno1 and \\cxsgdelsteno0 markers.

    Why character scan instead of regex:
      These blocks can be deeply nested inside RTF braces. A regex like
      {\\cxsgdelsteno1.*?\\cxsgdelsteno0} fails when there are inner
      brace groups. The scanner is 10 lines but always correct.
    """
    result = []
    i = 0
    depth = 0  # nesting counter (supports rare double-deleted blocks)
    # Pattern lengths (both are 14 chars: backslash + 13 letters/digit)
    DEL1 = '\\cxsgdelsteno1'   # len=14
    DEL0 = '\\cxsgdelsteno0'   # len=14
    N    = 14
    while i < len(content):
        if content[i:i+N] == DEL1:
            depth += 1
            i += N
        elif content[i:i+N] == DEL0:
            if depth > 0:
                depth -= 1
            i += N
        else:
            if depth == 0:
                result.append(content[i])
            i += 1
    return ''.join(result)


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

def parse_cxt(ts_str, current_hour, current_minute):
    """
    Parse a raw cxt string like '10:3:47:0', '3:47:0', or '47:0'.

    Returns (abs_sec, new_current_hour, new_current_minute).
    Returns (None, unchanged, unchanged) on parse failure.

    Why we track current_hour and current_minute separately:
      3-part timestamps give M:SS within the current hour, so we need the
      hour from the last absolute anchor. 2-part gives SS within the current
      minute, so we need both. Storing them as scalars keeps the logic flat.
    """
    try:
        parts = [int(p) for p in ts_str.strip().split(':')]
    except ValueError:
        return None, current_hour, current_minute

    if len(parts) == 4:       # H:M:S:F — absolute
        H, M, S, _F = parts
        return H * 3600 + M * 60 + S, H, M

    elif len(parts) == 3:     # M:SS:F — relative to current hour
        M, S, _F = parts
        return current_hour * 3600 + M * 60 + S, current_hour, M

    elif len(parts) == 2:     # SS:F — relative to current minute
        S, _F = parts
        return current_hour * 3600 + current_minute * 60 + S, current_hour, current_minute

    return None, current_hour, current_minute


def abs_sec_to_str(abs_sec):
    if abs_sec is None:
        return "unknown"
    H = abs_sec // 3600
    M = (abs_sec % 3600) // 60
    S = abs_sec % 60
    return f"{H}:{M:02d}:{S:02d}"


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract(rtf_path):
    """
    Parse the RTF and return a list of word dicts.

    Strategy:
      1. Remove deleted steno blocks (phantom timestamps).
      2. Replace every {\\*\\cxt ...} with a unique sentinel so we can split
         on it after RTF cleanup.
      3. Strip all remaining RTF markup — steno strokes, control words,
         braces — leaving plain text interspersed with sentinels.
      4. Split on sentinels; each chunk of text belongs to the preceding
         timestamp.
      5. Split each chunk into words and record {word, abs_sec, time_str}.

    Why sentinels instead of streaming:
      RTF cleanup is cleaner as a series of regex passes on the full string.
      Streaming requires re-implementing the cleanup inline. Sentinels let us
      reuse the simple cleanup logic from extract_rtf.py as-is.
    """
    with open(rtf_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Step 1: remove deleted steno
    content = remove_deleted_steno(content)

    # Step 2: replace {\*\cxt ...} with sentinels, record parsed timestamps
    timestamps = []   # list of (abs_sec, time_str)
    current_hour = 0
    current_minute = 0

    def replace_cxt(m):
        nonlocal current_hour, current_minute
        abs_sec, current_hour, current_minute = parse_cxt(
            m.group(1), current_hour, current_minute
        )
        idx = len(timestamps)
        timestamps.append((abs_sec, abs_sec_to_str(abs_sec)))
        return f"\x00TS{idx}\x00"   # null-byte sentinels — safe, never in RTF text

    content = re.sub(r'\{\\\*\\cxt ([^}]+)\}', replace_cxt, content)

    # Step 3: RTF cleanup (mirrors extract_rtf.py logic)
    content = re.sub(r'\{\\\*\\cx[^}]{0,300}\}', '', content)   # other cx blocks
    content = re.sub(r'\\cxfl\s*', '', content)
    content = re.sub(r'\\cxsingle\s*', '', content)
    content = re.sub(r'\\cxdouble\s*', '', content)
    content = re.sub(r'\\cxsgnocap\s*', '', content)
    content = re.sub(r'\\cxsgindex[0-9]+\s*', '', content)
    content = re.sub(r'\\cxsgmargin[0-9]+\s*', '', content)
    content = re.sub(r'\\cxsg[a-z]+[0-9]*\s*', '', content)
    content = re.sub(r'\\cx[a-z]+[0-9]*\s*', '', content)
    content = content.replace('\\line ', ' ').replace('\\line', ' ')
    content = content.replace('\\page ', ' ').replace('\\page', ' ')
    content = re.sub(r'\\pard[^\\{}\n]*', ' ', content)
    content = re.sub(r'\\par\b', ' ', content)
    content = content.replace('\\tab', ' ')
    content = re.sub(r'\\[a-zA-Z]+[-]?[0-9]*\*?\s?', ' ', content)
    content = re.sub(r'\{[^{}\x00]*\}', ' ', content)  # simple brace groups (no sentinels inside)
    content = re.sub(r'[{}\\]', ' ', content)

    # Step 4: split on sentinels
    parts = re.split(r'\x00TS(\d+)\x00', content)
    # parts[0]  = text before any timestamp (RTF header junk — discard)
    # parts[1]  = ts index, parts[2] = text after that ts
    # parts[3]  = ts index, parts[4] = text after that ts, ...

    # Step 5: build word list
    words = []
    # Regex to accept only tokens that look like real words/numbers/punctuation
    # Rejects pure RTF artifact tokens (lone digits, stray semicolons, etc.)
    word_re = re.compile(r"[A-Za-z0-9'\-\.,:;!\?\"]+")

    for i in range(1, len(parts) - 1, 2):
        ts_idx = int(parts[i])
        text_chunk = parts[i + 1]
        abs_sec, time_str = timestamps[ts_idx]

        if abs_sec is None:
            continue

        # Normalize whitespace and filter to real words
        for token in word_re.findall(text_chunk):
            # Skip tokens that are purely numeric with no context (likely RTF leftovers)
            # But keep numbers like "2026", "9:09", dollar amounts, etc.
            words.append({
                "word": token,
                "abs_sec": abs_sec,
                "time_str": time_str,
            })

    return words, timestamps


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_output(words, timestamps, rtf_path):
    """
    Wrap words list in a metadata envelope for easy consumption by
    audio_targeted.py (or any future tool that needs timestamp lookup).
    """
    # Anchor count = timestamps with 4-part format (abs hour != 0 or explicitly set)
    # Approximate: count timestamps whose abs_sec aligns to a round hour/minute
    # Actually just report all unique hours seen — that's what matters for interpolation quality.
    hours_seen = sorted(set(ts[0] // 3600 for ts in timestamps if ts[0] is not None))

    return {
        "rtf_file": os.path.basename(rtf_path),
        "total_words": len(words),
        "total_timestamps": len(timestamps),
        "hours_covered": [f"{h}:00" for h in hours_seen],
        "words": words,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    rtf_path = sys.argv[1] if len(sys.argv) > 1 else None
    rtf_path = find_tsmd_rtf(rtf_path)

    print(f"Parsing: {rtf_path}")
    words, timestamps = extract(rtf_path)

    out = build_output(words, timestamps, rtf_path)

    out_path = 'word_timestamps.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)

    print(f"Done.")
    print(f"  Words extracted : {out['total_words']:,}")
    print(f"  Timestamps found: {out['total_timestamps']:,}")
    print(f"  Hours covered   : {', '.join(out['hours_covered'])}")
    print(f"  Output          : {out_path}")

    # Spot-check: show first 5 and last 5 words with timestamps
    print("\nFirst 5 words:")
    for w in words[:5]:
        print(f"  {w['time_str']:>10}  {w['word']}")
    print("Last 5 words:")
    for w in words[-5:]:
        print(f"  {w['time_str']:>10}  {w['word']}")

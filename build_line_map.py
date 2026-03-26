"""
build_line_map.py
=================
Maps each correction in correction_log.json to its page:line citation
in the final formatted transcript.

How it works:
  1. Parse FINAL_DELIVERY/Easley_YellowRock_FINAL_FORMATTED.txt into
     (page, line, content) tuples — one per numbered line.
  2. For each correction, extract a clean search phrase from the corrected text.
  3. Scan formatted lines for the phrase. First match wins.
  4. Write line_map.json: { "0": "p.3 l.14", "1": "p.3 l.19", ... }

line_map.json is consumed by build_mb_review.py to replace "LINE 685"
with "p.29 l.14" in every MB_REVIEW entry.
"""

import json
import os
import re

FORMATTED_FILE  = 'FINAL_DELIVERY/Easley_YellowRock_FINAL_FORMATTED.txt'
CORRECTION_LOG  = 'correction_log.json'
LINE_MAP_FILE   = 'line_map.json'

# Minimum search phrase length — too short = false positives
MIN_PHRASE_LEN = 12


# ── Parse formatted transcript ────────────────────────────────────────────────

def parse_formatted_transcript(path):
    """
    Returns list of (page, line_num, content_lower) for every numbered line
    in the formatted transcript.
    Page lines look like:   " 1  Some content here"
    Page number lines look like: "3" or "14" (bare integer on its own line)
    """
    entries = []
    current_page = 0
    line_re = re.compile(r'^\s*(\d{1,2})\s{2}(.*)$')

    prev_blank = True   # treat start-of-file as after a blank line
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            raw = raw.rstrip('\n')
            stripped = raw.strip()

            if not stripped:
                prev_blank = True
                continue

            # Page number line: bare integer AND preceded by blank line.
            # Empty content lines (format_page emits "f"{i+1:2d}"" with no text)
            # are NOT preceded by blank lines, so they're excluded here.
            if prev_blank and re.match(r'^\d+$', stripped):
                current_page = int(stripped)
                prev_blank = False
                continue

            prev_blank = False

            # Numbered content line
            m = line_re.match(raw)
            if m and current_page > 0:
                line_num = int(m.group(1))
                content  = m.group(2).strip()
                entries.append((current_page, line_num, content))

    return entries


def build_search_index(entries):
    """
    Build a list of (page, line_num, content_lower) for fast iteration.
    Also build a dict of trigrams → indices for approximate matching.
    """
    return [(p, ln, c.lower()) for p, ln, c in entries]


# ── Extract search phrase from correction ─────────────────────────────────────

def extract_phrase(corrected_text, min_len=MIN_PHRASE_LEN):
    """
    Extract a clean, searchable phrase from corrected text.
    - Strips [REVIEW: ...] tags
    - Strips [FLAG: ...] tags
    - Strips leading Q. / A. labels (they vary by context)
    - Takes the first meaningful substring of MIN_PHRASE_LEN+ chars
    Returns None if no usable phrase can be extracted.
    """
    text = corrected_text

    # Strip [REVIEW:...] and [FLAG:...] blocks
    text = re.sub(r'\[REVIEW:[^\]]*\]', '', text)
    text = re.sub(r'\[FLAG:[^\]]*\]', '', text)

    # Normalize line breaks and excess whitespace
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text).strip()

    # Strip Q./A. labels from start
    text = re.sub(r'^[QA]\.\s+', '', text)

    # Strip leading punctuation junk
    text = text.lstrip('.,;: ↵')

    if len(text) < min_len:
        return None

    # Take up to 40 chars — long enough to be distinctive, short enough to
    # survive line-wrapping in the formatted output
    phrase = text[:40].strip()

    # Don't end on a partial word — back up to last space
    if len(phrase) == 40 and ' ' in phrase:
        phrase = phrase[:phrase.rfind(' ')]

    return phrase.lower() if len(phrase) >= min_len else None


# ── Search ────────────────────────────────────────────────────────────────────

def find_in_transcript(phrase, index):
    """
    Scan index for the first line containing phrase (case-insensitive).
    Returns (page, line_num) or None.
    """
    for page, line_num, content in index:
        if phrase in content:
            return (page, line_num)
    return None


def find_best_match(phrase, index, window_start=0):
    """
    Scan index starting from window_start for phrase.
    Allows searching forward from a known approximate position.
    Returns (page, line_num) or None.
    """
    for i, (page, line_num, content) in enumerate(index):
        if phrase in content:
            return (page, line_num)
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(FORMATTED_FILE):
        print(f'[ERROR] {FORMATTED_FILE} not found. Run format_final.py first.')
        return

    if not os.path.exists(CORRECTION_LOG):
        print(f'[ERROR] {CORRECTION_LOG} not found. Run ai_engine.py first.')
        return

    print(f'Parsing formatted transcript: {FORMATTED_FILE}')
    entries = parse_formatted_transcript(FORMATTED_FILE)
    index   = build_search_index(entries)
    print(f'  {len(entries):,} numbered lines across {entries[-1][0]} pages')

    with open(CORRECTION_LOG, 'r', encoding='utf-8') as f:
        data = json.load(f)
    corrections = data.get('corrections', [])
    print(f'Mapping {len(corrections)} corrections...')

    line_map   = {}      # { str(i): "p.X l.Y" }
    found      = 0
    not_found  = 0
    no_phrase  = 0

    for i, corr in enumerate(corrections):
        corrected = corr.get('corrected', '')
        original  = corr.get('original', '')
        conf      = corr.get('confidence', '')

        # For N/A entries, the corrected text IS the original (verbatim)
        search_text = corrected if corrected else original

        phrase = extract_phrase(search_text)

        if not phrase:
            # Try original text as fallback
            phrase = extract_phrase(original)

        if not phrase:
            line_map[str(i)] = None
            no_phrase += 1
            continue

        result = find_best_match(phrase, index)

        if result:
            page, ln = result
            line_map[str(i)] = f'p.{page} l.{ln}'
            found += 1
        else:
            # Fallback: try a shorter phrase (first 15 chars)
            short = phrase[:15].strip() if len(phrase) > 15 else phrase
            result2 = find_best_match(short, index)
            if result2:
                page, ln = result2
                line_map[str(i)] = f'p.{page} l.{ln}'
                found += 1
            else:
                line_map[str(i)] = None
                not_found += 1

    with open(LINE_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(line_map, f, indent=2)

    mapped_pct = found / len(corrections) * 100 if corrections else 0
    print(f'\nResults:')
    print(f'  Mapped to page:line:  {found:>4}  ({mapped_pct:.0f}%)')
    print(f'  Not found in output:  {not_found:>4}  (LOW/flagged-only or heavily rewritten)')
    print(f'  No usable phrase:     {no_phrase:>4}')
    print(f'\nWritten: {LINE_MAP_FILE}')
    print(f'Run build_mb_review.py next to apply citations to MB_REVIEW.txt')


if __name__ == '__main__':
    main()

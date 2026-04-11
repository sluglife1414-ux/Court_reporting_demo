"""
build_cat_ascii.py — Build CaseCATalyst-compatible ASCII import file.

Input:  corrected_text.txt (AI-corrected transcript, from job folder)
Output: FINAL_DELIVERY/{CASE_SHORT}_CAT.txt

Format: Windows-1252 encoding, CRLF line endings, column positions
verified working with CaseCATalyst ASCII import (2026-04-07).

CaseCATalyst auto-assigns paragraph styles on import:
  Q. lines  -> New-line Paragraph Style  (Question in MB's template)
  A. lines  -> Answer Paragraph Style
  BY lines  -> Byline Paragraph Style

Import steps (CR runs once per job):
  File -> Import -> ASCII -> Browse to FINAL_DELIVERY -> select _CAT.txt -> OK
  Then: File -> Open -> Transcript Files (*.sgngl) -> type filename -> Open

[TECH DEBT: colloquy body detection uses state machine (in_colloquy flag).
 Edge case: colloquy body with no blank line before next Q/A not yet seen in
 production but should be safe — Q/A regex takes priority over colloquy state.]
"""
import re
import os
import sys

# ── CaseCATalyst ASCII import hard limit (verified 2026-04-08) ───────────────
# CAT fails with "Encountered an improper argument" on any ASCII file >= 128KB.
# Safe split target is 120KB to leave headroom. Files are named _CAT_part1.txt, etc.
CAT_ASCII_LIMIT_BYTES = 120 * 1024   # 120 KB safe margin (128KB is the hard wall)

# ── Column spec (verified 2026-04-07 on CaseCATalyst, MB's installation) ─────
QA_INDENT   = 10   # leading spaces before Q. / A. label
QA_TEXT_COL = 15   # column where Q/A text begins  ("          Q.   " = 15 chars)
BY_INDENT   = 5    # leading spaces before BY MR./MS. line
COLL_INDENT = 5    # leading spaces before colloquy speaker and body
LINE_WIDTH  = 65   # total line width for word-wrap
QA_TEXT_W   = LINE_WIDTH - QA_TEXT_COL   # 50 chars of Q/A body per line

# ── Character substitution: UTF-8 -> Windows-1252 safe ASCII ─────────────────
_CHAR_SUB = [
    ('\u2018', "'"), ('\u2019', "'"),    # left/right single smart quote
    ('\u201c', '"'), ('\u201d', '"'),    # left/right double smart quote
    ('\u2013', '--'), ('\u2014', '--'),  # en dash, em dash
    ('\u2026', '...'),                   # ellipsis
    ('\u00a0', ' '),                     # non-breaking space
]


def sanitize(text):
    """Replace non-Windows-1252 chars with ASCII equivalents."""
    for old, new in _CHAR_SUB:
        text = text.replace(old, new)
    return text.encode('windows-1252', errors='replace').decode('windows-1252')


def _wrap_words(body, first_w, cont_w, cont_indent):
    """Wrap body text. Returns list of strings; caller prepends prefix to [0]."""
    words = body.split()
    if not words:
        return ['']
    lines, current, current_len, first = [], [], 0, True
    for word in words:
        add = len(word) + (1 if current else 0)
        limit = first_w if first else cont_w
        if current and current_len + add > limit:
            lines.append(' '.join(current))
            current, current_len, first = [word], len(word), False
        else:
            current.append(word)
            current_len += add
    if current:
        lines.append(' '.join(current))
    # Apply cont_indent to all lines after the first
    return [ln if i == 0 else cont_indent + ln for i, ln in enumerate(lines)]


def fmt_qa(label, body):
    """Format a Q. or A. testimony line with correct CAT column positions.

    Output: "          Q.   body text here..."
    Continuation: "               wrapped continuation text..."
    """
    prefix = ' ' * QA_INDENT + label + '.   '   # exactly 15 chars
    cont   = ' ' * QA_TEXT_COL                  # 15-space continuation indent
    first_w = LINE_WIDTH - len(prefix)
    wrapped = _wrap_words(body, first_w, QA_TEXT_W, cont)
    wrapped[0] = prefix + wrapped[0]
    return wrapped


def fmt_byline(text):
    """Format a BY MR./MS. examination header line."""
    return [' ' * BY_INDENT + text]


def fmt_speaker(text):
    """Format a colloquy speaker line (THE VIDEOGRAPHER:, MR. GARNER:, etc.)."""
    return [' ' * COLL_INDENT + text]


def fmt_coll_body(text):
    """Format colloquy body text — same indent as speaker."""
    cont = ' ' * COLL_INDENT
    first_w = LINE_WIDTH - COLL_INDENT
    wrapped = _wrap_words(text, first_w, first_w, cont)
    wrapped[0] = cont + wrapped[0]
    return wrapped


# ── Flag handling (applied to full file text before line processing) ──────────
# [FLAG:...]   = internal engine markers — strip entirely, never show to CR
# [REVIEW:...] = CR action items — compact to [[REVIEW]] (Ctrl+F findable in CAT)
# [AUDIO:...]  = audio check notes — compact to [[AUDIO]]
# All three can span multiple lines — use re.DOTALL.
_RE_FLAG_BLOCK   = re.compile(r'\[FLAG:.*?\]',   re.DOTALL)
_RE_REVIEW_BLOCK = re.compile(r'\[REVIEW:(?:[^\[\]]|\[[^\]]*\])*\]', re.DOTALL)
_RE_AUDIO_BLOCK  = re.compile(r'\[AUDIO:.*?\]',  re.DOTALL)

def preprocess_flags(text):
    """Strip [FLAG:] blocks and compact [REVIEW:]/[AUDIO:] to short markers.
    Must be called on the full file string before splitting into lines."""
    text = _RE_FLAG_BLOCK.sub('', text)
    text = _RE_REVIEW_BLOCK.sub('[[REVIEW]]', text)
    text = _RE_AUDIO_BLOCK.sub('[[AUDIO]]', text)
    return text

def compact_flags(text):
    """No-op shim — flag handling now done in preprocess_flags() on full text."""
    return text


# ── Line type regex patterns ──────────────────────────────────────────────────
_RE_Q    = re.compile(r'^Q\.\s+(.+)$')
_RE_A    = re.compile(r'^A\.\s+(.+)$')
_RE_BY   = re.compile(r'^BY\s+(?:MR|MS|MRS)\.\s+\S')
_RE_SPKR = re.compile(r'^(?:THE\s+\w+|(?:MR|MS|MRS)\.\s+\w[\w.]*)\s*:')


# ── Load config ───────────────────────────────────────────────────────────────
from config import cfg as _cfg
CASE_SHORT  = _cfg.get('case_short', 'UNKNOWN')
WITNESS     = _cfg.get('witness_name', '')

INPUT_FILE  = 'corrected_text.txt' if os.path.exists('corrected_text.txt') else 'cleaned_text.txt'
OUTPUT_FILE = f'FINAL_DELIVERY/{CASE_SHORT}_CAT.txt'

if not os.path.exists(INPUT_FILE):
    print(f'ERROR: {INPUT_FILE} not found. Run ai_engine.py (or steno_cleanup.py) first.')
    sys.exit(1)

os.makedirs('FINAL_DELIVERY', exist_ok=True)

# ── Process lines ─────────────────────────────────────────────────────────────
with open(INPUT_FILE, encoding='utf-8', errors='replace') as f:
    raw_text = preprocess_flags(f.read())
raw_lines = raw_text.splitlines()

out_lines   = []
in_colloquy = False   # True after a bare SPEAKER: line — next lines are colloquy body
q_count = a_count = 0

for raw in raw_lines:
    line    = compact_flags(sanitize(raw))
    stripped = line.strip()

    # ── Blank line ────────────────────────────────────────────────────────────
    if not stripped:
        out_lines.append('')
        in_colloquy = False
        continue

    # ── Q. line ───────────────────────────────────────────────────────────────
    m = _RE_Q.match(stripped)
    if m:
        in_colloquy = False
        out_lines.extend(fmt_qa('Q', m.group(1)))
        q_count += 1
        continue

    # ── A. line ───────────────────────────────────────────────────────────────
    m = _RE_A.match(stripped)
    if m:
        in_colloquy = False
        out_lines.extend(fmt_qa('A', m.group(1)))
        a_count += 1
        continue

    # ── BY MR./MS. examination header ─────────────────────────────────────────
    if _RE_BY.match(stripped):
        in_colloquy = False
        out_lines.extend(fmt_byline(stripped))
        continue

    # ── Colloquy speaker (THE VIDEOGRAPHER:, MR. GARNER:, etc.) ──────────────
    if _RE_SPKR.match(stripped):
        in_colloquy = True
        out_lines.extend(fmt_speaker(stripped))
        continue

    # ── Colloquy body (lines following a speaker) ─────────────────────────────
    if in_colloquy:
        out_lines.extend(fmt_coll_body(stripped))
        continue

    # ── Everything else (caption, headers, exhibits, index, certs) ────────────
    # Wrap long lines — CAT errors on lines > ~250 chars.
    if len(line) <= LINE_WIDTH:
        out_lines.append(line)
    else:
        # Preserve leading whitespace, wrap body at LINE_WIDTH
        lead  = len(line) - len(line.lstrip())
        indent_str = line[:lead]
        body  = line[lead:]
        avail = LINE_WIDTH - lead
        if avail < 20:
            avail = LINE_WIDTH   # degenerate indent — just wrap at full width
        wrapped = _wrap_words(body, avail, avail, indent_str)
        wrapped[0] = indent_str + wrapped[0]
        out_lines.extend(wrapped)

# ── Split output into 120KB chunks (CAT hard limit = 128KB) ──────────────────
def _split_chunks(lines, limit_bytes):
    """Split lines into chunks each under limit_bytes when encoded as CRLF Windows-1252.
    Always splits on a blank line to avoid cutting mid-exchange."""
    chunks, current, current_bytes = [], [], 0
    for ln in lines:
        encoded = (ln + '\r\n').encode('windows-1252', errors='replace')
        if current_bytes + len(encoded) > limit_bytes and current:
            # Find last blank line in current to split cleanly
            split_at = len(current)
            for i in range(len(current) - 1, -1, -1):
                if current[i] == '':
                    split_at = i + 1
                    break
            chunks.append(current[:split_at])
            current = current[split_at:]
            current_bytes = sum(len((l + '\r\n').encode('windows-1252', errors='replace')) for l in current)
        current.append(ln)
        current_bytes += len(encoded)
    if current:
        chunks.append(current)
    return chunks

chunks = _split_chunks(out_lines, CAT_ASCII_LIMIT_BYTES)
output_files = []

if len(chunks) == 1:
    # Single file — use the standard name
    content = '\r\n'.join(chunks[0])
    with open(OUTPUT_FILE, 'w', encoding='windows-1252', errors='replace', newline='') as f:
        f.write(content)
    output_files.append(OUTPUT_FILE)
else:
    # Multi-part — name as _CAT_part1.txt, _CAT_part2.txt, ...
    base = OUTPUT_FILE.replace('_CAT.txt', '')
    for i, chunk in enumerate(chunks, 1):
        part_file = f'{base}_CAT_part{i}.txt'
        content = '\r\n'.join(chunk)
        with open(part_file, 'w', encoding='windows-1252', errors='replace', newline='') as f:
            f.write(content)
        output_files.append(part_file)

# ── Summary ───────────────────────────────────────────────────────────────────
print('=' * 60)
print('CAT ASCII BUILD COMPLETE')
print('=' * 60)
print(f'Input:    {INPUT_FILE}')
print(f'Parts:    {len(output_files)}')
for pf in output_files:
    size = os.path.getsize(pf)
    with open(pf, 'rb') as f:
        part_lines = f.read().split(b'\r\n')
    print(f'  {os.path.basename(pf)}: {len(part_lines):,} lines, {size:,} bytes')
print(f'Q lines:  {q_count:,}')
print(f'A lines:  {a_count:,}')
print(f'Encoding: Windows-1252 | Line endings: CRLF')
print()
review_count = sum(1 for ln in out_lines if '[[REVIEW]]' in ln)
audio_count  = sum(1 for ln in out_lines if '[[AUDIO]]'  in ln)
if review_count:
    print(f'[[REVIEW]] flags in output: {review_count}  (MB: Ctrl+F "[[REVIEW]]" to find each one)')
if audio_count:
    print(f'[[AUDIO]]  flags in output: {audio_count}')
print()
print('Import into CaseCATalyst:')
print('  File -> Import -> ASCII -> Browse to FINAL_DELIVERY')
if len(output_files) == 1:
    print(f'  Select {os.path.basename(output_files[0])} -> OK')
    print(f'  File -> Open -> Transcript Files -> type: {CASE_SHORT}_CAT -> Open')
else:
    print(f'  Import each part in order:')
    for pf in output_files:
        print(f'    {os.path.basename(pf)}')
    print(f'  Each import creates a separate transcript — open and edit as needed.')

"""
extract_sgngl.py — Extract deposition text from CaseCATalyst binary .sgngl format.

Usage:
  python extract_sgngl.py [path/to/file.sgngl]

If no path given, searches for *.sgngl in current directory, then in
common depo input folders.

Outputs: extracted_text.txt  (same format expected by steno_cleanup.py)

NOTE FOR ONBOARDING:
  Ask the CR to export RTF from CaseCATalyst before sending — RTF gives
  cleaner Q/A structure. This extractor handles .sgngl as a fallback when
  RTF is not available (e.g., same-day rough delivered directly from CAT).

How it works:
  - CaseCATalyst .sgngl files are binary with embedded ASCII text strings.
  - Pre-testimony sections (caption, appearances, stipulation) are stored as
    clean multi-word strings → output line by line.
  - Testimony is stored as individual steno-output fragments (word/phrase level)
    → fragments are joined into sentences for the AI to reconstruct Q/A structure.
  - Q./A. labels are NOT present in the binary — ai_engine.py adds them.
  - ***ROUGH DRAFT*** watermark is stripped automatically.

[TECH DEBT: page break detection not implemented — .sgngl page break codes
 are binary, not ASCII. format_final.py reconstructs pages from content anyway,
 so this does not affect output quality.]
"""
import re
import glob
import sys
import os

# ── Locate input file ────────────────────────────────────────────────────────
if len(sys.argv) > 1:
    sgngl_file = sys.argv[1]
else:
    candidates = glob.glob('*.sgngl')
    if not candidates:
        # Check parent-level depo folders (common layout)
        candidates = glob.glob('../mb_*/*.sgngl') + glob.glob('../*_yellowrock*/*.sgngl')
    if not candidates:
        print('ERROR: No .sgngl file found.')
        print('  Pass the file path as an argument:')
        print('    python extract_sgngl.py path/to/file.sgngl')
        print('  Or copy the .sgngl file to this directory and re-run.')
        sys.exit(1)
    if len(candidates) > 1:
        print(f'WARNING: Multiple .sgngl files found: {candidates}')
        print(f'         Using: {candidates[0]}')
    sgngl_file = candidates[0]

print(f'Reading: {sgngl_file}')

# ── Read and validate ────────────────────────────────────────────────────────
with open(sgngl_file, 'rb') as f:
    data = f.read()

if not data.startswith(b'SGCAT32'):
    print('WARNING: File does not begin with SGCAT32 header — may not be a valid .sgngl file.')

# ── Extract printable ASCII strings (4+ chars filters out steno control codes) ──
_SKIP = frozenset(['SGCAT32', 'STKPWHRAO*EUFRPBLGTSDZ#(!', '12K3W4R50*EU6R7B8G9SDZ#(!'])
_ROUGH_MARKERS = frozenset(['***ROUGH DRAFT***', '**ROUGH DRAFT**', '*ROUGH DRAFT*',
                             '***ROUGH DRAFT**', '**ROUGH DRAFT***'])
_REPORTER_CHECK = '*REPORTER CHECK HERE*'

raw = [s.decode('ascii', errors='replace') for s in re.findall(b'[ -~]{4,}', data)]

# Filter out binary header junk, rough draft watermark, reporter placeholders
strings = []
for s in raw:
    stripped = s.strip()
    if stripped in _SKIP:
        continue
    if stripped in _ROUGH_MARKERS:
        continue
    if stripped == _REPORTER_CHECK:
        continue
    if not stripped:
        continue
    strings.append(s)

print(f'  {len(raw)} raw strings extracted, {len(strings)} after filtering')

# ── Section boundary detection ───────────────────────────────────────────────
_SECTION_HEADERS = frozenset([
    'I N D E X', 'A P P E A R A N C E S:', 'A P P E A R A N C E S',
    'E X H I B I T S', 'E X H I B I T S:', 'EXHIBITS',
    'S T I P U L A T I O N', 'EXAMINATION',
])
_DIVIDERS_RE   = re.compile(r'^\*[\s\*]+\*\s*$')
_BY_LINE_RE    = re.compile(r'^BY\s+(MR|MS|MRS)\.')
_SPEAKER_RE    = re.compile(r'^(THE\s+\w+:\s*|(?:MR|MS|MRS)\.\s+\w+:\s*)')
_FOR_BLOCK_RE  = re.compile(r'^(FOR THE |ATTORNEY FOR |ALSO PRESENT)')
_EXHIBIT_RE    = re.compile(r'^Exhibit No\.\s*\d+')


def _is_mostly_lowercase(s):
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.islower()) / len(letters) > 0.6


# ── Reconstruct text ─────────────────────────────────────────────────────────
# Strategy:
#   Phase 1 (pre-testimony): each string → its own line  (structured sections)
#   Phase 2 (testimony):     fragment strings joined with spaces into sentences
#                             speaker/structural strings still get their own line

lines   = []
in_testimony = False

def _flush(buf):
    """Join a testimony fragment buffer into a text line."""
    if not buf:
        return
    joined = ' '.join(buf).strip()
    if joined:
        lines.append(joined)

fragment_buf = []

for s in strings:
    stripped = s.strip()

    # ── Section header ────────────────────────────────────────────────────────
    if stripped in _SECTION_HEADERS:
        _flush(fragment_buf);  fragment_buf = []
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(stripped)
        lines.append('')
        if stripped == 'EXAMINATION':
            in_testimony = True
        continue

    # ── Divider line (* * * * * *) ────────────────────────────────────────────
    if _DIVIDERS_RE.match(stripped):
        _flush(fragment_buf);  fragment_buf = []
        lines.append(stripped)
        continue

    # ── BY MR./MS. examination header ────────────────────────────────────────
    if _BY_LINE_RE.match(stripped):
        _flush(fragment_buf);  fragment_buf = []
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(stripped)
        lines.append('')
        continue

    # ── Speaker colloquy (THE VIDEOGRAPHER:, MR. GARNER:, etc.) ─────────────
    if _SPEAKER_RE.match(stripped):
        _flush(fragment_buf);  fragment_buf = []
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(stripped)
        continue

    # ── FOR THE DEFENDANT / ATTORNEY FOR / ALSO PRESENT blocks ───────────────
    if _FOR_BLOCK_RE.match(stripped):
        _flush(fragment_buf);  fragment_buf = []
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(s.rstrip())
        continue

    # ── Exhibit entries ───────────────────────────────────────────────────────
    if _EXHIBIT_RE.match(stripped):
        _flush(fragment_buf);  fragment_buf = []
        lines.append(stripped)
        continue

    # ── Testimony phase: accumulate fragments, flush on sentence end ──────────
    if in_testimony and _is_mostly_lowercase(stripped):
        fragment_buf.append(stripped)
        # Flush when fragment ends a sentence
        if stripped and stripped[-1] in '.?!':
            _flush(fragment_buf);  fragment_buf = []
        continue

    # ── Default (structured pre-testimony text, ALL CAPS headers, etc.) ──────
    _flush(fragment_buf);  fragment_buf = []
    lines.append(s.rstrip())

_flush(fragment_buf)   # flush any remaining fragments

# ── Normalize whitespace ─────────────────────────────────────────────────────
text = '\n'.join(lines)
text = re.sub(r'[ \t]+', ' ', text)
text = re.sub(r'\n{3,}', '\n\n', text)
text = text.strip()

# ── Write output ─────────────────────────────────────────────────────────────
OUTPUT = 'extracted_text.txt'
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(text)

char_count = len(text)
line_count = text.count('\n') + 1
word_count = len(text.split())

print('=' * 60)
print('SGNGL EXTRACTION COMPLETE')
print('=' * 60)
print(f'Input:   {sgngl_file}')
print(f'Output:  {OUTPUT}')
print(f'Length:  {char_count:,} chars  |  {word_count:,} words  |  {line_count:,} lines')
print()
print('First 400 chars of output:')
print(repr(text[:400]))
print()
print('NOTE: Q./A. labels not present — ai_engine.py will reconstruct Q/A structure.')
print('NOTE: Ask CR to export RTF from CaseCATalyst for cleaner input on future depos.')

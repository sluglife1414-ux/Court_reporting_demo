"""
steno_cleanup.py
================
Pre-processing script for steno CAT software rough draft output.
Run AFTER extract_rtf.py, BEFORE the deposition engine.

Pipeline:
  extract_rtf.py  →  extracted_text.txt  (RTF → raw text)
  steno_cleanup.py → cleaned_text.txt    (artifacts removed)
  Engine           → reads cleaned_text.txt

What this handles (mechanical, no judgment required):
  - Tilde ~ artifact (attaches to numbers and times)
  - Double-underscore __ mid-speech → em dash —
  - Underscore in docket/case numbers → hyphen
  - Underscore in known compound words → hyphen or space
  - Double-@ in email addresses → single @
  - Encoding garbage characters (from RTF unicode conversion)
  - Excessive whitespace normalization

What this does NOT handle (requires judgment — left for engine):
  - Company name underscores (CHLOR_VINYLS etc.) — flag, don't touch
  - Phonetic mistranslations (bathe → by, etc.)
  - Speaker attribution
  - Punctuation rules
  - Displaced periods: "started\n. We'd like" — left for AI (ambiguous)
  - Capital-letter continuations — left for AI (could be new sentence or proper noun)

Last updated: 2026-03-25
Logged as:   LA-KB-012 (two-pass architecture), LA-KB-013 (tilde), LA-KB-014 (docket underscore)
"""

import re
import os
import sys

# Force UTF-8 output on Windows so summary prints cleanly
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

INPUT_FILE  = 'extracted_text.txt'
OUTPUT_FILE = 'cleaned_text.txt'

# ── Allow override via command line ─────────────────────────────────────────
if len(sys.argv) == 3:
    INPUT_FILE  = sys.argv[1]
    OUTPUT_FILE = sys.argv[2]
elif len(sys.argv) == 2:
    INPUT_FILE  = sys.argv[1]

if not os.path.exists(INPUT_FILE):
    print(f'ERROR: Input file not found: {INPUT_FILE}')
    sys.exit(1)

with open(INPUT_FILE, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

original_length = len(content)
changes = []

# ============================================================================
# STEP 1 — Tilde removal (LA-KB-013)
# Steno CAT artifact: tilde attaches to numbers and time expressions
#   "9:07~a.m."   → "9:07 a.m."
#   "13~years"    → "13 years"
#   "March~13th"  → "March 13th"
# ============================================================================
before = len(content)
content = re.sub(r'~', ' ', content)
n = (before - len(content)) + content.count('  ') - content.count('   ')  # rough count
tilde_count = original_length - len(content.replace(' ', '')) - (original_length - len(content.replace('~', '').replace(' ', '')))
# simpler: just count replacements
tilde_count = len(re.findall(r'~', open(INPUT_FILE, encoding='utf-8', errors='replace').read()))
changes.append(f'  Tilde (~) removed:              {tilde_count} occurrences')

# ============================================================================
# STEP 2 — Double underscore → em dash (mid-speech self-correction/interruption)
# Pattern: word __ word  or  word __\n
# "then __ are you interested"  → "then—are you interested"
# "large __ big eight"          → "large—big eight"
# Note: em dash has no surrounding spaces per Gregg Rule 6.5
# ============================================================================
before_count = len(re.findall(r'\s+__\s+', content))
content = re.sub(r'\s+__\s+', '—', content)
# double underscore at end of clause (before newline)
before_count += len(re.findall(r'\s+__(?=\s*\n)', content))
content = re.sub(r'\s+__(?=\s*\n)', '—', content)
changes.append(f'  Double-underscore → em dash:    {before_count} occurrences')

# ============================================================================
# STEP 3 — Underscore in docket/case numbers → hyphen (LA-KB-014)
# Pattern: digit_digit  (e.g., 202_001594 → 202-001594)
# Safe because digits on both sides cannot be company names
# ============================================================================
before_count = len(re.findall(r'\d_\d', content))
content = re.sub(r'(\d)_(\d)', r'\1-\2', content)
changes.append(f'  Docket underscore → hyphen:     {before_count} occurrences')

# ============================================================================
# STEP 4 — Known compound word underscores (explicit whitelist only)
# These are confirmed steno artifacts, not company names or domain names.
# Add to this list as new patterns are confirmed from production runs.
# ============================================================================
compound_fixes = [
    ('day_to_day',           'day-to-day'),
    ('E_mail',               'E-mail'),    # KB-015: Muir house style is E-mail (capital E, hyphen)
    ('e_mail',               'E-mail'),    # KB-015
    ('re_depose',            're-depose'),
    ('re_cross',             're-cross'),
    ('re_examine',           're-examine'),
    ('non_verbal',           'non-verbal'),
    ('publicly_traded',      'publicly traded'),
    ('successor_in_interest','successor-in-interest'),
    ('pre_spud',             'pre-spud'),
    ('follow_up',            'follow-up'),
    ('leak_off',             'leak-off'),
    ('well_control',         'well-control'),
    ('on_site',              'onsite'),       # KB-005: onsite is one word
    ('off_site',             'offsite'),      # KB-005
]
compound_count = 0
for wrong, right in compound_fixes:
    n = content.count(wrong)
    if n:
        content = content.replace(wrong, right)
        compound_count += n
        changes.append(f'    {wrong!r:30s} → {right!r}  ({n}x)')
if compound_count == 0:
    changes.append(f'  Compound word fixes:            0 occurrences')
else:
    changes.insert(-compound_count, f'  Compound word fixes:            {compound_count} total')

# ============================================================================
# STEP 5 — Double @ in email addresses → single @
# RTF conversion artifact in appearances blocks
# ============================================================================
before_count = len(re.findall(r'@@', content))
content = content.replace('@@', '@')
changes.append(f'  Double-@ → single @:           {before_count} occurrences')

# ============================================================================
# STEP 6 — Strip encoding garbage characters
# RTF → unicode conversion sometimes produces non-ASCII garbage
# (the Â or similar character appearing before zip codes and state names)
# Keep: standard ASCII, em dash, en dash, smart quotes, ellipsis
# ============================================================================
KEEP_UNICODE = set('\u2013\u2014\u2018\u2019\u201c\u201d\u2026')
before_count = sum(1 for c in content if ord(c) > 127 and c not in KEEP_UNICODE)
content = ''.join(
    c if (ord(c) <= 127 or c in KEEP_UNICODE) else ' '
    for c in content
)
changes.append(f'  Encoding artifacts stripped:    {before_count} characters')

# ============================================================================
# STEP 7 — Whitespace normalization
# ============================================================================
content = re.sub(r'[ \t]+', ' ', content)          # multiple spaces → single
content = re.sub(r' ([?!])', r'\1', content)        # D-17: steno trailing space before ?/! — AI reads as gap
content = re.sub(r' \n', '\n', content)             # trailing space before newline
content = re.sub(r'\n ', '\n', content)             # leading space after newline
content = re.sub(r'\n{3,}', '\n\n', content)        # 3+ blank lines → 2
content = content.strip()

# ============================================================================
# STEP 8 — Mid-sentence line-break rejoining
#
# Steno CAT software wraps lines mid-sentence at arbitrary stroke boundaries.
# This produces fragments like:
#   "Are you ready          "Are you ready to go, Mr. Easley?"
#    to go, Mr. Easley?"
#
# Rule: if a line does NOT end with sentence-completing punctuation (.?!:;—)
#       AND the next line starts with a lowercase letter
#       AND neither line is a protected boundary (speaker label, blank, header)
#       → rejoin with a single space.
#
# Secondary rule: digit + digit with no space (e.g. "770\n24" → "77024")
#
# What we deliberately do NOT rejoin (leave for AI):
#   - Displaced period:   "started\n. We'd like"   (next line starts with .)
#   - Capital starts:     could be new sentence or proper noun — AI judges
#   - Across blank lines: paragraph boundaries — always respected
#   - Speaker labels:     MR./MS./Q./A./BY/THE WITNESS: etc.
#   - Section headers:    ALL CAPS lines, --- PAGE BREAK ---, * * *
#   - Parentheticals:     (Whereupon, (Exhibit...
# ============================================================================

# Patterns that mark a protected line — never rejoin across these
_SPEAKER_RE = re.compile(
    r'^('
    r'Q\.\s|A\.\s'                          # Q./A. labels
    r'|MR\.\s|MS\.\s|MRS\.\s|DR\.\s'       # attorney labels
    r'|BY\s+MR\.|BY\s+MS\.|BY\s+MRS\.'     # BY MR./MS. examination headers
    r'|THE\s+\w+:'                          # THE WITNESS: THE COURT: THE VIDEOGRAPHER:
    r'|FOR\s+THE\s'                         # FOR THE PLAINTIFF:
    r'|\('                                  # parentheticals (Whereupon, (Exhibit...
    r'|---'                                 # --- PAGE BREAK ---
    r'|\*'                                  # * * * * dividers
    r')',
    re.IGNORECASE
)

_SENTENCE_ENDERS = frozenset('.?!:;')


def _is_protected(line: str) -> bool:
    """Return True if this line is a boundary — never rejoin across it."""
    s = line.strip()
    if not s:
        return True                          # blank line = paragraph boundary
    if _SPEAKER_RE.match(s):
        return True
    # ALL CAPS section headers (e.g. "I N D E X", "A P P E A R A N C E S")
    letters = [c for c in s if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(s) > 4:
        return True
    return False


def _ends_sentence(line: str) -> bool:
    """Return True if line ends with punctuation that closes a sentence."""
    s = line.rstrip()
    if not s:
        return True
    return s[-1] in _SENTENCE_ENDERS or s[-1] == '\u2014'  # em dash = interrupted, leave


def _rejoin_line_breaks(text: str):
    """
    Walk lines and greedily rejoin mid-sentence steno fragments.
    Returns (rejoined_text, join_count).
    """
    lines = text.split('\n')
    result = []
    join_count = 0
    digit_join_count = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── Lowercase continuation: join while conditions hold ────────────────
        while (
            i + 1 < len(lines)
            and not _is_protected(line)
            and not _ends_sentence(line)
            and not _is_protected(lines[i + 1])
            and lines[i + 1].strip()                      # next line not blank
            and lines[i + 1].strip()[0].islower()         # next starts lowercase
        ):
            line = line.rstrip() + ' ' + lines[i + 1].strip()
            i += 1
            join_count += 1

        # ── Digit continuation: "770\n24" → "77024" (zip codes, page numbers) ─
        while (
            i + 1 < len(lines)
            and not _is_protected(line)
            and line.rstrip()                             # current not blank
            and line.rstrip()[-1].isdigit()              # current ends with digit
            and lines[i + 1].strip()                     # next not blank
            and lines[i + 1].strip()[0].isdigit()        # next starts with digit
            and not _is_protected(lines[i + 1])
        ):
            line = line.rstrip() + lines[i + 1].strip()  # no space between digits
            i += 1
            digit_join_count += 1

        result.append(line)
        i += 1

    return '\n'.join(result), join_count, digit_join_count


content, join_count, digit_join_count = _rejoin_line_breaks(content)
changes.append(f'  Line-break rejoins (lowercase):  {join_count} fragments merged')
if digit_join_count:
    changes.append(f'  Line-break rejoins (digit):      {digit_join_count} number fragments merged')

# ============================================================================
# WRITE OUTPUT
# ============================================================================
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

final_length = len(content)
reduction = original_length - final_length

print('=' * 60)
print('STENO CLEANUP COMPLETE')
print('=' * 60)
print(f'Input file:    {INPUT_FILE}')
print(f'Output file:   {OUTPUT_FILE}')
print(f'Input length:  {original_length:>10,} chars')
print(f'Output length: {final_length:>10,} chars')
print(f'Reduction:     {reduction:>10,} chars  ({reduction/original_length*100:.1f}%)')
print()
print('Changes applied:')
for c in changes:
    print(c)
print()
print('NOTE: Company name underscores (e.g., CHLOR_VINYLS) were NOT touched.')
print('      Flag these in the engine for human verification.')
print('=' * 60)

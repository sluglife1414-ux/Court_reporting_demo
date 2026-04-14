"""
compare_mb_final.py — Diff our engine output vs MB's final transcript.

Strips all formatting from both files and compares testimony content
word by word. Reports:
  - ADDED:   words in our output that MB does not have (verbatim violations)
  - DROPPED: words MB has that we do not (missing content)

Usage:
    python compare_mb_final.py                          # auto-find files in work/
    python compare_mb_final.py our.txt mb_final.txt     # explicit paths

Output:
    FINAL_DELIVERY/MB_DIFF_REPORT.txt

The diff is done at the BLOCK level (25-word windows) so additions and
deletions are shown in readable context, not as isolated tokens.
"""

import re
import sys
import os
import difflib
from pathlib import Path

def extract_pdf_text(pdf_path):
    """Extract plain text from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        print('ERROR: pdfplumber not installed. Run: pip install pdfplumber')
        sys.exit(1)
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.append(text)
    return '\n'.join(lines)

# ── Locate files ─────────────────────────────────────────────────────────────

def find_files():
    """Auto-detect our output and MB's final in standard job layout."""
    work = Path.cwd()
    delivery = work / 'FINAL_DELIVERY'

    # Our output — prefer FINAL_FORMATTED.txt
    our_candidates = list(delivery.glob('*_FINAL_FORMATTED.txt'))
    if not our_candidates:
        our_candidates = list(delivery.glob('*_FINAL.txt'))
    if not our_candidates:
        print('ERROR: No FINAL_FORMATTED.txt found in FINAL_DELIVERY/')
        sys.exit(1)
    our_path = our_candidates[0]

    # MB's final — look for mb_final_reference.txt in work/
    mb_path = work / 'mb_final_reference.txt'
    if not mb_path.exists():
        print(f'ERROR: mb_final_reference.txt not found in {work}')
        print()
        print('  Run this first to extract MB\'s final:')
        print(f'  python C:\\depo_transformation\\engine\\mb_demo_engine_v4\\extract_sgngl.py '
              f'C:\\Cat4\\usr\\scott\\032626YELLOWROCK-FINAL.sgngl')
        print(f'  Then rename the output:')
        print(f'  rename extracted_text.txt mb_final_reference.txt')
        sys.exit(1)

    return our_path, mb_path


if len(sys.argv) == 3:
    our_path = Path(sys.argv[1])
    mb_path  = Path(sys.argv[2])
else:
    our_path, mb_path = find_files()

print(f'Our output : {our_path}')
print(f'MB final   : {mb_path}')

# ── Strip formatting ──────────────────────────────────────────────────────────

# Tags to strip from our output
_TAG_RE = re.compile(
    r'\[\[(?:REVIEW|AUDIO|AGENT|CONFIRMED|NOTE):.*?\]\]'   # double-bracket CAT tags (may span lines)
    r'|\[(?:REVIEW|AUDIO|CHANGED|SUGGEST|FLAG|CORRECTED):.*?\]'  # single-bracket engine tags
    r'|\*REPORTER CHECK HERE\*'
    r'|text\s+appears\s+truncated[^.]*\.?'                 # truncation notice artifact
    r'|possible\s+missing\s+words[^.]*\.?'                 # missing words artifact
    r'|verify\s+audio'                                     # verify audio artifact
    r'|creation\s+date\s+in\s+words'                       # cert page placeholder
    r'|\*reporter\s+check\s+here\*',                       # reporter check placeholder
    re.IGNORECASE | re.DOTALL
)

# Page/line number patterns  e.g. "  1  " at line start, "Page 12" headers
_PAGE_HEADER_RE = re.compile(
    r'^\s*(?:Page\s+\d+|CONTINUED.*|[-=]{20,})\s*$'
    r'|^\s*\d{1,3}\s*$',   # bare line numbers
    re.MULTILINE
)

# Section headers to strip (structural, not testimony)
_STRUCTURAL_RE = re.compile(
    r'^\s*(?:I\s+N\s+D\s+E\s+X'
    r'|E\s+X\s+H\s+I\s+B\s+I\s+T\s+S?'
    r'|A\s+P\s+P\s+E\s+A\s+R\s+A\s+N\s+C\s+E\s+S'
    r'|S\s+T\s+I\s+P\s+U\s+L\s+A\s+T\s+I\s+O\s+N'
    r'|EXAMINATION\s+BY'
    r'|REPORTER\'?S?\s+CERTIFICATE'
    r'|WITNESS\'?S?\s+CERTIFICATE'
    r'|CERTIFICATE\s+OF'
    r'|[-*\s]{10,})\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Exhibit index lines
_EXHIBIT_LINE_RE = re.compile(
    r'^\s*Exhibit\s+No\.\s*\d+.*$',
    re.MULTILINE | re.IGNORECASE
)


def normalize(text):
    """Strip all formatting, return plain words as a list."""
    # Strip engine tags
    text = _TAG_RE.sub(' ', text)
    # Strip page headers and bare line numbers
    text = _PAGE_HEADER_RE.sub(' ', text)
    # Strip structural headers
    text = _STRUCTURAL_RE.sub(' ', text)
    # Strip exhibit index lines
    text = _EXHIBIT_LINE_RE.sub(' ', text)
    # Strip leading line numbers on formatted transcript lines e.g. "  14  Q. ..."
    text = re.sub(r'^\s*\d{1,3}\s+', '', text, flags=re.MULTILINE)
    # Strip page number headers e.g. "                           47" (right-justified page num)
    text = re.sub(r'^\s{10,}\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    # Strip Q. / A. / MR. XX: speaker labels (preserve the words that follow)
    text = re.sub(r'^\s*(?:Q\.|A\.)\s+', ' ', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*(?:MR|MS|MRS|THE)\.\s+\w+:\s*', ' ', text, flags=re.MULTILINE)
    # Strip RTF artifacts (font names, style definitions)
    text = re.sub(r'\b(?:courier|arial|times|helvetica|calibri|verdana)\s*\w*\b', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpar\s+style\s+\d+\b', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\buser\s+defined\b', ' ', text, flags=re.IGNORECASE)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Lowercase for comparison
    text = text.lower()
    # Keep only word tokens — exclude pure numbers (line numbers, page numbers)
    # Numbers like docket/zip will be caught separately; focus on word content
    words = [w for w in re.findall(r"[a-z0-9']+", text) if not w.isdigit()]
    return words


our_text = our_path.read_text(encoding='utf-8', errors='replace')
if mb_path.suffix.lower() == '.pdf':
    print('  Extracting text from PDF...')
    mb_text = extract_pdf_text(mb_path)
else:
    mb_text = mb_path.read_text(encoding='utf-8', errors='replace')

our_words = normalize(our_text)
mb_words  = normalize(mb_text)

print(f'Our words  : {len(our_words):,}')
print(f'MB words   : {len(mb_words):,}')
print()

# ── Diff ─────────────────────────────────────────────────────────────────────

CONTEXT = 8   # words of context on each side of a change

matcher = difflib.SequenceMatcher(None, our_words, mb_words, autojunk=False)
opcodes = matcher.get_opcodes()

additions = []   # in ours, not in MB  (potential verbatim violations)
deletions = []   # in MB, not in ours  (content we dropped)

for tag, i1, i2, j1, j2 in opcodes:
    if tag == 'equal':
        continue

    our_chunk = our_words[i1:i2]
    mb_chunk  = mb_words[j1:j2]

    # Context
    our_before = ' '.join(our_words[max(0, i1-CONTEXT):i1])
    our_after  = ' '.join(our_words[i2:i2+CONTEXT])
    mb_before  = ' '.join(mb_words[max(0, j1-CONTEXT):j1])
    mb_after   = ' '.join(mb_words[j2:j2+CONTEXT])

    if tag in ('replace', 'insert'):
        # Words in our output that MB does NOT have
        if our_chunk:
            additions.append({
                'our_words': our_chunk,
                'our_pos':   i1,
                'context_before': our_before,
                'context_after':  our_after,
                'mb_has':    mb_chunk,
            })

    if tag in ('replace', 'delete'):
        # Words in MB's final that we do NOT have
        if mb_chunk:
            deletions.append({
                'mb_words':  mb_chunk,
                'mb_pos':    j1,
                'context_before': mb_before,
                'context_after':  mb_after,
                'we_have':   our_chunk,
            })

# ── Filter noise ──────────────────────────────────────────────────────────────
# Single-word differences that are likely OCR/steno variants — keep for now
# but flag separately

_STOPWORDS = frozenset(['the','a','an','and','or','but','in','on','at','to',
                        'of','for','is','it','that','this','was','are','be',
                        'have','had','with','as','by','from','not','he','she',
                        'they','we','you','i','his','her','their','our','its',
                        'so','if','up','do','did','yes','no','okay','all'])

def is_trivial(words):
    """True if this diff chunk is just stopwords — low signal."""
    return all(w in _STOPWORDS for w in words)


additions_signal = [a for a in additions if not is_trivial(a['our_words'])]
additions_noise  = [a for a in additions if     is_trivial(a['our_words'])]
deletions_signal = [d for d in deletions if not is_trivial(d['mb_words'])]
deletions_noise  = [d for d in deletions if     is_trivial(d['mb_words'])]

# ── Report ────────────────────────────────────────────────────────────────────

lines = []
W = 72

def hr(char='='):
    lines.append(char * W)

def section(title):
    hr()
    lines.append(f'  {title}')
    hr()
    lines.append('')

case_name = our_path.stem.replace('_FINAL_FORMATTED','').replace('_FINAL','')

hr()
lines.append(f'  MB DIFF REPORT — {case_name}')
lines.append(f'  Our output : {our_path.name}')
lines.append(f'  MB final   : {mb_path.name}')
lines.append(f'  Our words  : {len(our_words):,}   |   MB words: {len(mb_words):,}')
lines.append(f'  Word delta : {len(our_words) - len(mb_words):+,}')
lines.append('')
lines.append(f'  ADDITIONS  (in ours, not in MB) — signal: {len(additions_signal)}  noise: {len(additions_noise)}')
lines.append(f'  DELETIONS  (in MB, not in ours) — signal: {len(deletions_signal)}  noise: {len(deletions_noise)}')
hr()
lines.append('')
lines.append('  SIGNAL = substantive words (names, verbs, nouns)')
lines.append('  NOISE  = stopwords only (the, and, a, etc.) — low priority')
lines.append('')

# ── ADDITIONS (verbatim violations — we added words MB didn't have) ───────────

section(f'ADDITIONS — WORDS WE ADDED THAT MB DOES NOT HAVE  ({len(additions_signal)} signal)')
lines.append('  These are the highest priority — words engine inserted that were never said.')
lines.append('')

for i, item in enumerate(additions_signal, 1):
    added = ' '.join(item['our_words'])
    mb_has = ' '.join(item['mb_has']) if item['mb_has'] else '(nothing)'
    lines.append(f'  ADD-{i:03d}  pos:{item["our_pos"]}')
    lines.append(f'  WE   : ...{item["context_before"]} >>> {added} <<< {item["context_after"]}...')
    lines.append(f'  MB   : ...{item["context_before"]} >>> {mb_has} <<< {item["context_after"]}...')
    lines.append('')

if not additions_signal:
    lines.append('  (none — no substantive additions found)')
    lines.append('')

# ── DELETIONS (content MB has that we dropped) ────────────────────────────────

section(f'DELETIONS — WORDS MB HAS THAT WE DROPPED  ({len(deletions_signal)} signal)')
lines.append('  Words present in MB\'s final that do not appear in our output.')
lines.append('')

for i, item in enumerate(deletions_signal, 1):
    dropped = ' '.join(item['mb_words'])
    we_have = ' '.join(item['we_have']) if item['we_have'] else '(nothing)'
    lines.append(f'  DEL-{i:03d}  pos:{item["mb_pos"]}')
    lines.append(f'  MB   : ...{item["context_before"]} >>> {dropped} <<< {item["context_after"]}...')
    lines.append(f'  WE   : ...{item["context_before"]} >>> {we_have} <<< {item["context_after"]}...')
    lines.append('')

if not deletions_signal:
    lines.append('  (none — no substantive deletions found)')
    lines.append('')

# ── NOISE SUMMARY ─────────────────────────────────────────────────────────────

section(f'NOISE — STOPWORD DIFFERENCES ONLY  (additions:{len(additions_noise)}  deletions:{len(deletions_noise)})')
lines.append('  These are low-priority differences — articles, conjunctions, etc.')
lines.append('  Likely steno/OCR variants or CR style preferences (comma placement, etc.)')
lines.append('  Not verbatim violations.')
lines.append('')

hr()
lines.append('  END OF REPORT')
hr()

report = '\n'.join(lines)

# ── Write output ──────────────────────────────────────────────────────────────

delivery = Path.cwd() / 'FINAL_DELIVERY'
out_path = delivery / 'MB_DIFF_REPORT.txt'
out_path.write_text(report, encoding='utf-8')

print(report)
print()
print(f'Report written to: {out_path}')

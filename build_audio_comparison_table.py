"""
build_audio_comparison_table.py — Whisper vs. AD Final Comparison Table
========================================================================
For each audio-flagged REVIEW tag, shows three columns side by side:

  OUR TEXT  — what our engine had (gap shown as [?])
  WHISPER   — what Whisper heard at that timestamp
  AD FINAL  — what AD's final transcript says at that location

Output: FINAL_DELIVERY/{case_short}_AUDIO_COMPARISON_TABLE.txt

Usage:
    cd <job_work_dir>
    python path/to/engine/build_audio_comparison_table.py  [path/to/ad_final.pdf]

    If no PDF path given, looks for the reference PDF configured in
    CASE_CAPTION.json under the key "reference_pdf". Falls back to
    prompting if neither is found.

Author:  Scott + Claude
Version: 1.0  (2026-04-09)
"""

import os
import sys
import json
import re
from datetime import date

try:
    import pdfplumber
except ImportError:
    print('ERROR: pdfplumber not installed.  pip install pdfplumber')
    sys.exit(1)

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.getcwd()

# ── Paths ─────────────────────────────────────────────────────────────────────
LOG_PATH       = os.path.join(BASE, 'audio_apply_log.json')
CORRECTED_PATH = os.path.join(BASE, 'corrected_text.txt')
CAPTION_PATH   = os.path.join(BASE, 'CASE_CAPTION.json')
OUT_DIR        = os.path.join(BASE, 'FINAL_DELIVERY')

# ── Validate inputs ───────────────────────────────────────────────────────────
for path, label in [(LOG_PATH, 'audio_apply_log.json'),
                    (CORRECTED_PATH, 'corrected_text.txt'),
                    (CAPTION_PATH, 'CASE_CAPTION.json')]:
    if not os.path.exists(path):
        print(f'ERROR: {label} not found at {path}')
        print('  Run apply_audio_validation.py first.')
        sys.exit(1)

# ── Resolve AD reference PDF ──────────────────────────────────────────────────
# Priority: CLI arg > CASE_CAPTION.json "reference_pdf" key > fail with message
ref_pdf = None
if len(sys.argv) > 1:
    ref_pdf = sys.argv[1]
else:
    with open(CAPTION_PATH, encoding='utf-8') as f:
        cap = json.load(f)
    ref_pdf = cap.get('reference_pdf')

if not ref_pdf or not os.path.exists(ref_pdf):
    print('ERROR: AD reference PDF not found.')
    print('  Pass path as argument:')
    print('    python build_audio_comparison_table.py /path/to/ad_final.pdf')
    print('  Or add "reference_pdf" key to CASE_CAPTION.json.')
    sys.exit(1)

# ── Load inputs ───────────────────────────────────────────────────────────────
with open(LOG_PATH, encoding='utf-8') as f:
    log = json.load(f)

with open(CORRECTED_PATH, encoding='utf-8') as f:
    corrected_lines = f.read().split('\n')

with open(CAPTION_PATH, encoding='utf-8') as f:
    caption = json.load(f)

case_short   = caption.get('case_short', 'CASE')
witness      = caption.get('witness_name', '')
cr_name      = caption.get('reporter_name_display', '')
depo_date    = caption.get('depo_date', '')
job_dir_name = os.path.basename(os.path.dirname(BASE))

# ── Extract AD final PDF text ─────────────────────────────────────────────────
print(f'Reading AD reference PDF: {os.path.basename(ref_pdf)}')
with pdfplumber.open(ref_pdf) as pdf:
    page_chunks = []
    for page in pdf.pages:
        raw = page.extract_text() or ''
        # Strip leading line numbers (1-2 digit prefix on each line)
        lines = [re.sub(r'^\s*\d{1,2}\s+', '', ln).strip() for ln in raw.split('\n')]
        # Drop bare page numbers and header stamps
        lines = [ln for ln in lines
                 if ln
                 and not re.match(r'^\d+$', ln)
                 and 'WCB G395' not in ln]
        page_chunks.append(' '.join(lines))
    ad_full = ' '.join(page_chunks)

# Normalised copy for matching (lowercase, collapsed whitespace)
ad_norm = re.sub(r'\s+', ' ', ad_full.lower()).strip()

print(f'  {len(ad_full):,} chars extracted from {len(pdf.pages)}-page PDF')

# ── Helpers ───────────────────────────────────────────────────────────────────
_RE_REVIEW = re.compile(r'\[REVIEW:(?:[^\[\]]|\[[^\]]*\])*\]', re.DOTALL)

W = 70
SEP   = '─' * W
DBLSEP = '═' * W

def normalize(s):
    return re.sub(r'\s+', ' ', s.lower().strip())

def strip_review(text):
    """Replace [REVIEW:...] tags with [?] for clean display."""
    return _RE_REVIEW.sub('[?]', text)

def extract_before_after(line_text, window=50):
    """Split line at first [REVIEW] tag, return (before_norm, after_norm)."""
    clean = _RE_REVIEW.sub('\x00', line_text, count=1)
    parts = clean.split('\x00', 1)
    before = normalize(parts[0][-window:]) if parts[0] else ''
    after  = normalize(parts[1][:window])  if len(parts) > 1 else ''
    return before.strip(), after.strip()

def find_ad_snippet(before, after, ad_norm, ad_full, snippet_len=100):
    """
    Locate our gap in AD's transcript using the text immediately before it.
    Direct substring search — no verification needed. In a 20-page depo
    any 4+ word phrase before a gap is essentially unique.
    Try progressively shorter needles (6 → 2 words) until a match is found.
    """
    before_words = before.split()

    for n in range(min(6, len(before_words)), 1, -1):
        needle = ' '.join(before_words[-n:])
        if len(needle) < 8:
            continue
        idx = ad_norm.find(needle)
        if idx == -1:
            continue
        start = max(0, idx)
        end   = min(len(ad_full), start + snippet_len)
        return ad_full[start:end].strip()

    return None

def wrap(text, width=64, indent='        '):
    """Word-wrap text to width."""
    words = text.split()
    lines, buf = [], ''
    for w in words:
        if buf and len(buf) + 1 + len(w) > width:
            lines.append(buf)
            buf = w
        else:
            buf = (buf + ' ' + w).strip()
    if buf:
        lines.append(buf)
    return ('\n' + indent).join(lines)

def context_display(line_num, n_before=0, n_after=0):
    """Return cleaned display lines around line_num."""
    idx = line_num - 1
    result = []
    for i in range(max(0, idx - n_before), min(len(corrected_lines) - 1, idx + n_after) + 1):
        raw = corrected_lines[i].strip()
        if not raw:
            continue
        cleaned = strip_review(raw)
        result.append(cleaned)
    return ' '.join(result)

# ── Collect all items ─────────────────────────────────────────────────────────
applied  = log.get('applied', [])
surfaced = sorted(log.get('surfaced', []), key=lambda x: x['line_num'])

# ── Build output ──────────────────────────────────────────────────────────────
os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, f'{case_short}_AUDIO_COMPARISON_TABLE.txt')

lines_out = []

def emit(s=''):
    lines_out.append(s)

# ── Header ─────────────────────────────────────────────────────────────────────
emit(DBLSEP)
emit(f'  {case_short.upper()} — WHISPER vs. AD FINAL — AUDIO COMPARISON TABLE')
emit(f'  Witness:    {witness}')
emit(f'  Depo date:  {depo_date}')
emit(f'  Reporter:   {cr_name}')
emit(f'  Reference:  {os.path.basename(ref_pdf)}')
emit(f'  Generated:  {date.today().strftime("%B %d, %Y")}')
emit(DBLSEP)
emit()
emit('  KEY')
emit('  OUR:    what our engine had at the gap location ([?] = flagged gap)')
emit('  HEARD:  what Whisper suggested from the audio recording')
emit('  AD:     what AD\'s final transcript says at that location')
emit()
emit('  MATCH  = Whisper heard the right answer')
emit('  CLOSE  = Whisper was in the right area but not exact')
emit('  MISS   = Whisper was wrong or context was off')
emit('  N/F    = could not locate this spot in AD\'s transcript')
emit()

# ── Stats ──────────────────────────────────────────────────────────────────────
emit(f'  {len(applied)} AUTO-confirmed  |  {len(surfaced)} for review  |  {len(applied)+len(surfaced)} total')
emit()

# ── AUTO section ──────────────────────────────────────────────────────────────
if applied:
    emit(SEP)
    emit(f'  AUTO-CONFIRMED  ({len(applied)} items)')
    emit(SEP)
    emit()
    for n, item in enumerate(applied, 1):
        line_num = item['line_num']
        ctx      = context_display(line_num)
        whisper  = item.get('whisper_text', '')
        before, after = extract_before_after(item.get('after', ''))
        ad_snip  = find_ad_snippet(before, after, ad_norm, ad_full)

        emit(f'  AUTO-{n:02d}  Line {line_num}  [score: {item["match_score"]}]')
        emit(f'  OUR:   {wrap(strip_review(ctx)[:120])}')
        emit(f'  HEARD: "{whisper[:65]}"')
        emit(f'  AD:    {wrap(ad_snip[:120]) if ad_snip else "[not found]"}')
        emit()

# ── Surfaced items ─────────────────────────────────────────────────────────────
emit(DBLSEP)
emit(f'  SURFACED ITEMS  ({len(surfaced)} — Whisper heard something, CR must decide)')
emit(DBLSEP)
emit()

matched_count = 0
miss_count    = 0
nf_count      = 0

for n, item in enumerate(surfaced, 1):
    line_num  = item['line_num']
    action    = item['action']
    score     = item['match_score']
    whisper   = item.get('whisper_text', '')
    note      = item.get('note', '')
    conf      = 'HIGH' if action == 'SUGGEST' else 'LOW '

    ctx       = context_display(line_num)
    before, after = extract_before_after(item.get('after', ''))
    ad_snip   = find_ad_snippet(before, after, ad_norm, ad_full)

    if ad_snip is None:
        nf_count += 1
        verdict_hint = 'N/F'
    else:
        # Rough match check: does the whisper text appear near the AD snippet?
        w_norm = normalize(whisper)
        ad_snip_norm = normalize(ad_snip)
        # Check if key words from whisper appear in AD snippet
        w_words = [w for w in w_norm.split() if len(w) > 3]
        hits = sum(1 for w in w_words if w in ad_snip_norm)
        if w_words and hits / len(w_words) >= 0.5:
            matched_count += 1
            verdict_hint = 'MATCH?'
        else:
            miss_count += 1
            verdict_hint = 'MISS? '

    emit(SEP)
    emit(f'  TAG-{n:02d}  Line {line_num}  [{conf} score:{score}]  [{verdict_hint}]')
    emit()
    emit(f'  OUR:   {wrap(strip_review(ctx)[:120])}')
    emit(f'  HEARD: "{wrap(whisper[:100], width=60, indent="         ")}"')
    if ad_snip:
        emit(f'  AD:    {wrap(ad_snip[:120])}')
    else:
        emit(f'  AD:    [could not locate in reference PDF]')
    emit()

# ── Summary ───────────────────────────────────────────────────────────────────
emit(DBLSEP)
emit(f'  SUMMARY  ({len(surfaced)} surfaced items)')
emit(f'  Whisper MATCH (key words in AD final):  {matched_count}')
emit(f'  Whisper MISS  (not in AD final):        {miss_count}')
emit(f'  Not found in AD PDF:                    {nf_count}')
emit(DBLSEP)

# ── Write ─────────────────────────────────────────────────────────────────────
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines_out))

print(f'\nComparison table written: {out_path}')
print(f'  Surfaced:   {len(surfaced)}')
print(f'  MATCH:      {matched_count}')
print(f'  MISS:       {miss_count}')
print(f'  Not found:  {nf_count}')

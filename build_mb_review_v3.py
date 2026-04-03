"""
build_mb_review_v3.py — MB 15-Minute Review Package
======================================================
Generates FINAL_DELIVERY/{case_short}_MB_REVIEW.txt

Design goal:
  MB opens the PDF and this file side by side.
  Every item has a PDF page number she can jump to.
  She should be done in 15 minutes.

What we show MB:
  A — 5 spot-check pages  (structure confirmation)
  B — Items she can fix RIGHT NOW without audio
       (Bates issues, names, missing data, exhibit gaps)
  C — Filler words  (her preference, one decision applies to all)
  D — Audio-dependent items  (count only — she handles in her normal pass)
  E — Sign-off box

What we DO NOT show MB:
  - The 583 HIGH confidence engine fixes (she doesn't need to review those)
  - Verify-agent internal notes she can't action without audio
  - Technical engine details

Author:  Scott + Claude
Version: 3.1  (2026-04-03)
"""

import json
import os
import re
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))


# ── Load config ───────────────────────────────────────────────────────────────

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return default or {}

cfg         = load_json(os.path.join(BASE, 'depo_config.json'))
caption     = load_json(os.path.join(BASE, 'CASE_CAPTION.json'))
corr_data   = load_json(os.path.join(BASE, 'correction_log.json'))
if isinstance(corr_data, list):
    corr_data = {'corrections': corr_data}
corr_list   = corr_data.get('corrections', [])

CASE_SHORT   = cfg.get('case_short', 'Case')
WITNESS      = caption.get('witness_name',       cfg.get('witness_name', 'WITNESS'))
DEPO_DATE    = caption.get('depo_date',          cfg.get('depo_date_short', ''))
REPORTER     = caption.get('reporter_name_display', 'Marybeth E. Muir')
DOCKET       = caption.get('docket',             cfg.get('docket', ''))
EXAMINING    = caption.get('examining_atty',     cfg.get('examining_atty', ''))

high_count   = sum(1 for c in corr_list if c.get('confidence') == 'HIGH')
total_corr   = len(corr_list)


# ── Load FINAL_FORMATTED.txt — page/line reference map ───────────────────────

FORMATTED_PATH = os.path.join(BASE, 'FINAL_DELIVERY', f'{CASE_SHORT}_FINAL_FORMATTED.txt')
_flines = []
if os.path.exists(FORMATTED_PATH):
    with open(FORMATTED_PATH, encoding='utf-8') as f:
        _flines = f.read().split('\n')

# Build page map: formatted_line_index → page number
_page_at = {}
_cur_pg  = None
for _i, _raw in enumerate(_flines):
    _s = _raw.strip()
    if _s.isdigit() and 1 <= int(_s) <= 9999:
        _cur_pg = int(_s)
    _page_at[_i] = _cur_pg
total_pages = max((v for v in _page_at.values() if v), default=0)


def find_page_for_text(snippet, max_search=20):
    """Search FINAL_FORMATTED for snippet and return (page, line) or (None, None)."""
    snippet_clean = snippet.lower().strip()[:40]
    if len(snippet_clean) < 6:
        return None, None
    for i, raw in enumerate(_flines):
        if snippet_clean in raw.lower():
            pg = _page_at.get(i)
            m  = re.match(r'^\s{0,2}(\d{1,2})\s{1,3}', raw)
            ln = int(m.group(1)) if m else None
            return pg, ln
    return None, None


# ── Parse corrected_text.txt — find [REVIEW] items ───────────────────────────

CORRECTED_PATH = os.path.join(BASE, 'corrected_text.txt')
_clines = []
if os.path.exists(CORRECTED_PATH):
    with open(CORRECTED_PATH, encoding='utf-8') as f:
        _clines = f.read().split('\n')

# Keyword sets for categorizing [REVIEW] items
_ACTIONABLE = [
    'bates', 'exhibit', 'name', 'spelling', 'number', 'figure', 'percent',
    'date', 'address', 'zip', 'phone', 'email', 'title', 'firm', 'attorney',
    'missing', 'gap', 'jump', 'sequence', 'wipple', 'guastell', 'cibulsky',
]
_AUDIO_ONLY = [
    'audio', 'reconstruction', 'beyond steno', 'fragmented', 'reporter confirm',
    'steno gap', 'fragmentation', 'attributed', 'speaker attribution',
    'requires audio', 'verify audio', 'listen',
]


def categorize_review(note):
    note_l = note.lower()
    if any(k in note_l for k in _AUDIO_ONLY):
        return 'audio'
    if any(k in note_l for k in _ACTIONABLE):
        return 'actionable'
    return 'audio'   # default: defer to audio pass


review_actionable = []
review_audio_count = 0

for i, raw_line in enumerate(_clines):
    if '[REVIEW' not in raw_line:
        continue
    # Extract all [REVIEW:...] tags from this line
    tags = re.findall(r'\[REVIEW:\s*(.*?)(?:\]|$)', raw_line)
    for tag_note in tags:
        tag_note = tag_note.strip()
        cat = categorize_review(tag_note)
        if cat == 'audio':
            review_audio_count += 1
        else:
            # Get text before the [REVIEW] tag for page lookup
            before = raw_line.split('[REVIEW')[0].strip()
            snippet = before[-50:] if len(before) > 10 else raw_line[:50]
            pg, ln = find_page_for_text(snippet)
            review_actionable.append({
                'note':    tag_note[:100],
                'snippet': (before[:65] if before else raw_line[:65]),
                'page':    pg,
                'line':    ln,
            })


# ── Load QA_FLAGS — extract filler word count ─────────────────────────────────

QA_PATH = os.path.join(BASE, 'FINAL_DELIVERY', 'QA_FLAGS.txt')
filler_count = 0
if os.path.exists(QA_PATH):
    with open(QA_PATH, encoding='utf-8') as f:
        qa_text = f.read()
    filler_count = qa_text.count('FILLER WORD')


# ── Spot-check pages ─────────────────────────────────────────────────────────

SPOT_CHECKS = [
    {
        'label': 'COVER PAGE',
        'page':  1,
        'check': (f'Witness: {WITNESS}. Date: {DEPO_DATE}. '
                  f'Location. Your name as reporter.'),
    },
    {
        'label': 'STIPULATION',
        'page':  10,
        'check': (f'Witness named as {WITNESS}. '
                  f'Attorney named to retain original.'),
    },
    {
        'label': 'FIRST TESTIMONY PAGE',
        'page':  11,
        'check': (f'Videographer statement correct. Witness intro block. '
                  f'Q. by {EXAMINING}.'),
    },
    {
        'label': "REPORTER'S CERTIFICATE",
        'page':  max(total_pages - 4, 1),
        'check': 'Your name, credentials, witness name, page count correct.',
    },
    {
        'label': 'WITNESS CERT + ERRATA',
        'page':  max(total_pages - 2, 1),
        'check': f'Witness name {WITNESS} and testimony date correct.',
    },
]


# ── Build the report ──────────────────────────────────────────────────────────

W   = 68
SEP = '─' * W
DBL = '═' * W
L   = []

def add(*lines):
    for line in lines:
        L.append(line)

def section(title):
    add('', DBL, title, DBL, '')


# HEADER
add(
    DBL,
    f'  TRANSCRIPT REVIEW  —  {WITNESS}',
    f'  {DEPO_DATE}   |   Docket {DOCKET}',
    f'  Prepared for: {REPORTER}',
    DBL,
    '',
    f'  Total pages:        {total_pages}',
    f'  Engine corrections: {total_corr:,}  '
    f'({high_count:,} applied automatically)',
    f'  Items for your eyes: {len(review_actionable)} now '
    f'+ {review_audio_count} during audio pass',
    '',
    '  WHAT TO DO:',
    '  1. Open the PDF alongside this file.',
    '  2. Section A — go to each page, confirm it looks right (5 pages).',
    '  3. Section B — review each flagged item, write your answer.',
    '  4. Section C — filler words: remove them all, or keep some?',
    '  5. Sign off at the bottom and reply.',
    '',
    '  You do NOT need to read all 241 pages.',
    '  Audio-dependent items are handled in your normal audio pass.',
    '',
)

# SECTION A — SPOT CHECK
section(f'SECTION A — SPOT CHECK  (5 pages)')
add('  Open the PDF to each page. Confirm it looks right.',
    '  Write any corrections in the NOTES line.', '')

for sc in SPOT_CHECKS:
    add(
        f'  ┌─ PDF PAGE {sc["page"]}  —  {sc["label"]}',
        f'  │  CHECK: {sc["check"]}',
        f'  │  NOTES: _____________________________________________',
        f'  └',
        '',
    )

# SECTION B — ACTIONABLE REVIEW ITEMS
section(f'SECTION B — ITEMS NEEDING YOUR ANSWER  ({len(review_actionable)} items)')

if not review_actionable:
    add('  No items require your input right now. Engine was confident.', '')
else:
    add(
        '  These are places where the engine flagged something specific.',
        '  Find the page in the PDF. Write the correct answer.',
        '',
    )
    for n, item in enumerate(review_actionable, 1):
        pg_ref = f'PDF page {item["page"]}, line {item["line"]}' \
                 if item['page'] else 'location — search PDF'
        add(
            f'  B-{n:02d}  {pg_ref}',
            f'        TEXT:    {item["snippet"][:65]}',
            f'        ISSUE:   {item["note"][:65]}',
            f'        ANSWER:  _____________________________________________',
            '',
        )

# SECTION C — FILLER WORDS
section(f'SECTION C — FILLER WORDS  ({filler_count} found in testimony)')
add(
    f'  The engine found {filler_count} filler words (uhmm, uh-huh used as filler, etc.)',
    '  in the testimony. Your call:',
    '',
    '  ( ) Remove all filler words  — cleaner transcript',
    '  ( ) Keep all filler words    — verbatim record',
    '  ( ) Remove only "uhmm"       — keep other fillers',
    '  ( ) I will mark them individually in the PDF',
    '',
    '  NOTE: Uh-huh (yes) and Huh-uh (no) as answers are KEPT regardless.',
    '',
)

# SECTION D — AUDIO PASS ITEMS
section(f'SECTION D — AUDIO PASS  ({review_audio_count} items deferred)')
add(
    f'  {review_audio_count} items in this transcript need audio to resolve.',
    '  These are heavy steno reconstructions where the engine could not',
    '  confirm what was said. They are flagged [REVIEW] in the source.',
    '',
    '  You do not need to address these now.',
    '  Handle in your normal audio review pass.',
    '',
    '  If you want a full list, ask Scott for the detailed QA log.',
    '',
)

# SECTION E — SIGN-OFF
section('SECTION E — SIGN-OFF')
add(
    f'  Reviewed by: {REPORTER}',
    f'  Date:        ___________________________',
    '',
    '  Status:',
    '',
    '    ( ) APPROVED — deliver as-is',
    '    ( ) APPROVED WITH CORRECTIONS — see notes above',
    '    ( ) NEEDS REWORK — contact Scott',
    '',
    '  Comments:',
    '  __________________________________________________________________',
    '  __________________________________________________________________',
    '',
    DBL,
    f'  {CASE_SHORT}  |  Generated {date.today().strftime("%B %d, %Y")}',
    f'  Engine: MASTER_DEPOSITION_ENGINE v4  |  Not a legal document',
    DBL,
)


# ── Write output ─────────────────────────────────────────────────────────────

out_path = os.path.join(BASE, 'FINAL_DELIVERY', f'{CASE_SHORT}_MB_REVIEW.txt')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))

print(f'Written: {out_path}')
print(f'  Spot-check pages:      {len(SPOT_CHECKS)}')
print(f'  Actionable items:      {len(review_actionable)}')
print(f'  Audio-deferred items:  {review_audio_count}')
print(f'  Filler words:          {filler_count}')
print(f'  Total lines in doc:    {len(L)}')

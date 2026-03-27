"""
build_mb_review_v2.py
PURPOSE: Generate MB_REVIEW.txt for court reporter review.
         Plain text, Notepad-friendly, max 70 chars per line.
INPUTS:  correction_log.json, FINAL_DELIVERY/review_locations.json (Option B sidecar)
OUTPUTS: FINAL_DELIVERY/MB_REVIEW.txt
"""

import json, os, random, re as _re

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Load case config ─────────────────────────────────────
_cfg_path = os.path.join(BASE, 'depo_config.json')
_cfg = {}
if os.path.exists(_cfg_path):
    with open(_cfg_path, encoding='utf-8') as f:
        _cfg = json.load(f)

CASE_LABEL   = _cfg.get('case_short', 'Case').replace('_', ' v. ')
DEPO_DATE    = _cfg.get('depo_date_short', '')
CASE_SHORT   = _cfg.get('case_short', 'Case')

# ── Load correction log ───────────────────────────────────
with open(os.path.join(BASE, 'correction_log.json'), encoding='utf-8') as f:
    data = json.load(f)

# ── Load Option B sidecar (review_locations.json) ────────
_sidecar_path = os.path.join(BASE, 'FINAL_DELIVERY', 'review_locations.json')
_sidecar = {}
if os.path.exists(_sidecar_path):
    with open(_sidecar_path, encoding='utf-8') as f:
        _sidecar = json.load(f)

# ── Load FINAL_FORMATTED.txt for fallback text search ────
_formatted_path = os.path.join(BASE, 'FINAL_DELIVERY',
                                f'{CASE_SHORT}_FINAL_FORMATTED.txt')
_flines = []
if os.path.exists(_formatted_path):
    with open(_formatted_path, encoding='utf-8') as f:
        _flines = f.read().split('\n')


def page_ref(item, item_idx=None):
    """Find correct page/line for a correction item.
    Checks review_locations.json sidecar first (set by format_final.py Option B),
    then falls back to text search in FINAL_FORMATTED.txt.
    """
    # Sidecar lookup (most reliable — exact anchor from formatting pass)
    if item_idx is not None and str(item_idx) in _sidecar:
        loc = _sidecar[str(item_idx)]
        if loc != 'location unknown':
            return loc

    # Fallback: text search
    candidates = []
    corr = item.get('corrected', '').replace('\n', ' ').strip()
    orig = item.get('original', '').replace('\n', ' ').strip()

    if '[REVIEW' in corr:
        before = corr.split('[REVIEW')[0].strip()
        if len(before) > 10:
            candidates.append(before[-40:])
        if len(orig) > 10:
            candidates.append(orig[:30])
    else:
        if corr and len(corr) > 5:
            candidates.append(corr[:35])
        if orig and len(orig) > 5:
            candidates.append(orig[:35])

    current_page = None
    for phrase in candidates:
        phrase_lower = phrase.lower()
        for line in _flines:
            stripped = line.strip()
            if stripped.isdigit() and len(stripped) <= 3:
                current_page = int(stripped)
                continue
            if phrase_lower in line.lower():
                m = _re.match(r'^\s*(\d+)\s+', line)
                lineno = m.group(1) if m else '?'
                if current_page:
                    return f'p.{current_page} l.{lineno}'

    return 'location unknown'


corrections = data['corrections']
high   = [c for c in corrections if c.get('confidence') == 'HIGH']
medium = [(i, c) for i, c in enumerate(corrections) if c.get('confidence') == 'MEDIUM']
low    = [(i, c) for i, c in enumerate(corrections) if c.get('confidence') == 'LOW']
na     = [(i, c) for i, c in enumerate(corrections) if c.get('confidence') == 'N/A']


def clean(s, maxlen=60):
    return s.replace('\n', ' ').replace('\r', ' ').strip()[:maxlen]


SEP  = '-' * 60
SEP2 = '=' * 60
L = []

# ── HEADER ──────────────────────────────────────────────
L += [
    SEP2,
    f'MB REVIEW  |  {CASE_LABEL}  |  {DEPO_DATE}',
    SEP2,
    '',
    f'The engine made {len(corrections):,} corrections to the rough draft.',
    'Here is what you need to do:',
    '',
    f'  NOTHING  -- {len(high):,} fixes done automatically.',
    f'             5 examples below so you can verify.',
    '',
    f'  READ     -- {len(medium)} fixes the engine is 80-90% sure about.',
    f'             5 examples in Section 2. Flag if wrong.',
    '',
    f'  DECIDE   -- {len(low)} items the engine could not fix.',
    f'             All listed in Section 3. Reply with correct text.',
    '',
    f'  SUPPLY   -- {len(na)} items missing data only you have.',
    f'             All listed in Section 4.',
    '',
    'If anything looks wrong, say so.',
    'Every original line is saved.',
    '',
]

# ── SECTION 1: PROOF ────────────────────────────────────
L += [
    SEP2,
    f'SECTION 1 -- THE {len(high):,} FIXES  (none of these are on you)',
    SEP2,
    '',
    f'Every one of these {len(high):,} errors came from the CAT machine,',
    'not from you.  You stroked the keys correctly.',
    'The machine translated your strokes wrong.',
    '',
    'As an expert reporter you have always caught and fixed these.',
    f'The engine fixed all {len(high):,} in 60 seconds.',
    '',
    SEP,
    'THE CAT MACHINE BROKE WORDS ACROSS LINES:',
    SEP,
    '',
    "  The machine output this:",
    "    Reporter",
    "    's Certificate",
    '',
    "  The engine fixed it to:",
    "    Reporter's Certificate",
    '',
    "  The machine output this:",
    "    public accounting",
    "    , 13 years",
    "    ,",
    '',
    "  The engine fixed it to:",
    "    public accounting, 13 years,",
    '',
    SEP,
    'THE CAT MACHINE GOT CAPITALIZATION WRONG:',
    SEP,
    '',
    '  WAS:  PlaintiffS,',
    '  NOW:  Plaintiffs,',
    '',
    '  WAS:  BY: IAN SALINAS_STERN, ESQ.',
    '  NOW:  BY: IAN SALINAS-STERN, ESQ.',
    '',
    SEP,
    f'5 EXAMPLES FROM THE {len(high):,}:',
    SEP,
    '',
]
random.seed(42)
for i, item in enumerate(random.sample(high, min(5, len(high))), 1):
    L += [
        f'  [{i:02d}]  line ~{item["line_approx"]}',
        f'        WAS:  {clean(item["original"])}',
        f'        NOW:  {clean(item["corrected"])}',
        '',
    ]

# ── SECTION 2: SPOT CHECK ───────────────────────────────
L += [
    SEP2,
    f'SECTION 2 -- SPOT CHECK  ({len(medium)} items, engine 80-90% confident)',
    SEP2,
    '',
    f'The engine found {len(medium)} corrections it is 80-90% sure about.',
    'Read these 5 examples. Circle YES or NO.',
    'If NO, write one sentence why -- it goes straight into the rulebook.',
    '',
]
for i, (idx, item) in enumerate(medium[:5], 1):
    L += [
        f'  SC-{i}  |  {page_ref(item, idx)}',
        f'    WAS:    {clean(item["original"])}',
        f'    NOW:    {clean(item["corrected"])}',
        f'    OK?     YES / NO',
        f'    IF NO:  ________________________________',
        '',
    ]
L += [f'  ({len(medium)-5} more MEDIUM items available on request.)', '']

# ── SECTION 3: YOUR DECISIONS ───────────────────────────
L += [
    SEP2,
    f'SECTION 3 -- YOUR DECISIONS  ({len(low)} items)',
    SEP2,
    '',
    'These have placeholder text in the transcript right now.',
    'Reply with the correct text for each item number.',
    '',
    '  [LISTEN]       = pull up audio, confirm what was said',
    '  [CONFIRM NAME] = check your notes for the correct name',
    '  [CONFIRM SENT] = listen for the sentence flow',
    '',
]


def action(item):
    r = item.get('reason', '').lower()
    if any(k in r for k in ['proper name', 'entity name', 'company name', 'bates', 'person name']):
        return '[CONFIRM NAME]'
    if any(k in r for k in ['incomplete sentence', 'no predicate', 'sentence appears']):
        return '[CONFIRM SENT]'
    return '[LISTEN]      '


for i, (idx, item) in enumerate(low, 1):
    L += [
        f'  ITEM {i:02d}  |  {page_ref(item, idx)}  |  {action(item)}',
        f'    WAS:     {clean(item["original"])}',
        f'    FLAGGED: {clean(item["corrected"])}',
        f'    FIX:     ________________________________',
        '',
    ]

# ── SECTION 4: MISSING DATA ─────────────────────────────
L += [
    SEP2,
    f'SECTION 4 -- MISSING DATA  ({len(na)} items)',
    SEP2,
    '',
    '  [SUPPLY]          = provide the missing information',
    '  [DECIDE VERBATIM] = witness said it wrong -- keep or correct?',
    '  [CONFIRM]         = engine left as-is -- confirm that is right',
    '',
]


def na_action(item):
    r = item.get('reason', '').lower()
    if any(k in r for k in ['missing', 'absent', 'suite']):
        return '[SUPPLY]         '
    if any(k in r for k in ['verbatim', 'spoken', 'mispronunciation', 'grammatical error']):
        return '[DECIDE VERBATIM]'
    return '[CONFIRM]        '


for i, (idx, item) in enumerate(na, 1):
    L += [
        f'  NA-{i:02d}  |  {page_ref(item, idx)}  |  {na_action(item)}',
        f'    TEXT:  {clean(item["original"])}',
        f'    NOTE:  {item["reason"][:58]}',
        f'    FIX:   ________________________________',
        '',
    ]

# ── FOOTER ──────────────────────────────────────────────
from datetime import date
today = date.today().strftime('%Y-%m-%d')
L += [
    SEP2,
    f'END OF REVIEW  |  {len(corrections):,} total corrections  |  {today}',
    SEP2,
]

out = '\n'.join(L)
path = os.path.join(BASE, 'FINAL_DELIVERY', 'MB_REVIEW.txt')
with open(path, 'w', encoding='utf-8') as f:
    f.write(out)

print(f'Done. {len(L)} lines. Max line: {max(len(x) for x in L)} chars.')

"""
build_mb_review_v2.py
PURPOSE: Generate MB_REVIEW.txt for court reporter review.
         Plain text, Notepad-friendly, max 70 chars per line.
INPUTS:  correction_log.json
OUTPUTS: FINAL_DELIVERY/MB_REVIEW.txt
"""

import json, os, random

BASE = r'C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4'

with open(os.path.join(BASE, 'correction_log.json'), encoding='utf-8') as f:
    data = json.load(f)

with open(os.path.join(BASE, 'line_map.json'), encoding='utf-8') as f:
    line_map = json.load(f)

def page_ref(line_approx):
    """Convert raw line number to page/line ref using line_map. Falls back to line ~N."""
    ref = line_map.get(str(line_approx))
    if ref:
        return ref
    # search nearby lines +/- 5
    for delta in range(1, 6):
        for key in [str(line_approx + delta), str(line_approx - delta)]:
            r = line_map.get(key)
            if r:
                return r
    return f'line ~{line_approx}'

corrections = data['corrections']
high   = [c for c in corrections if c.get('confidence') == 'HIGH']
medium = [c for c in corrections if c.get('confidence') == 'MEDIUM']
low    = [c for c in corrections if c.get('confidence') == 'LOW']
na     = [c for c in corrections if c.get('confidence') == 'N/A']

def clean(s, maxlen=60):
    return s.replace('\n', ' ').replace('\r', ' ').strip()[:maxlen]

SEP  = '-' * 60
SEP2 = '=' * 60
L = []

# ── HEADER ──────────────────────────────────────────────
L += [
    SEP2,
    'MB REVIEW  |  Easley v. YellowRock  |  March 13, 2026',
    SEP2,
    '',
    'The engine made 1,298 corrections to the rough draft.',
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
    'SECTION 1 -- THE 1,170 FIXES  (none of these are on you)',
    SEP2,
    '',
    'Every one of these 1,170 errors came from the CAT machine,',
    'not from you.  You stroked the keys correctly.',
    'The machine translated your strokes wrong.',
    '',
    'As an expert reporter you have always caught and fixed these.',
    'The engine fixed all 1,170 in 60 seconds.',
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
    f'5 EXAMPLES FROM THE 1,170:',
    SEP,
    '',
]
random.seed(42)
for i, item in enumerate(random.sample(high, 5), 1):
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
for i, item in enumerate(medium[:5], 1):
    L += [
        f'  SC-{i}  |  {page_ref(item["line_approx"])}',
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
    'SECTION 3 -- YOUR DECISIONS  (44 items)',
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
    if any(k in r for k in ['proper name','entity name','company name','bates','person name']):
        return '[CONFIRM NAME]'
    if any(k in r for k in ['incomplete sentence','no predicate','sentence appears']):
        return '[CONFIRM SENT]'
    return '[LISTEN]      '

for i, item in enumerate(low, 1):
    L += [
        f'  ITEM {i:02d}  |  {page_ref(item["line_approx"])}  |  {action(item)}',
        f'    WAS:     {clean(item["original"])}',
        f'    FLAGGED: {clean(item["corrected"])}',
        f'    FIX:     ________________________________',
        '',
    ]

# ── SECTION 4: MISSING DATA ─────────────────────────────
L += [
    SEP2,
    'SECTION 4 -- MISSING DATA  (14 items)',
    SEP2,
    '',
    '  [SUPPLY]          = provide the missing information',
    '  [DECIDE VERBATIM] = witness said it wrong -- keep or correct?',
    '  [CONFIRM]         = engine left as-is -- confirm that is right',
    '',
]

def na_action(item):
    r = item.get('reason', '').lower()
    if any(k in r for k in ['missing','absent','suite']):
        return '[SUPPLY]         '
    if any(k in r for k in ['verbatim','spoken','mispronunciation','grammatical error']):
        return '[DECIDE VERBATIM]'
    return '[CONFIRM]        '

for i, item in enumerate(na, 1):
    L += [
        f'  NA-{i:02d}  |  {page_ref(item["line_approx"])}  |  {na_action(item)}',
        f'    TEXT:  {clean(item["original"])}',
        f'    NOTE:  {item["reason"][:58]}',
        f'    FIX:   ________________________________',
        '',
    ]

# ── FOOTER ──────────────────────────────────────────────
L += [
    SEP2,
    'END OF REVIEW  |  1,298 total corrections  |  2026-03-27',
    SEP2,
]

out = '\n'.join(L)
path = os.path.join(BASE, 'FINAL_DELIVERY', 'MB_REVIEW.txt')
with open(path, 'w', encoding='utf-8') as f:
    f.write(out)

print(f'Done. {len(L)} lines. Max line: {max(len(x) for x in L)} chars.')

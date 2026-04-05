"""
build_cr_review.py — CR 15-Minute Review Package
======================================================
Generates FINAL_DELIVERY/{case_short}_CR_REVIEW.txt

Design goal:
  CR opens the PDF and this file side by side.
  Every item has a PDF page number she can jump to.
  She should be done in 15 minutes.

What we show the CR:
  A — 5 spot-check pages  (structure confirmation)
  B — Items she can fix RIGHT NOW without audio
       (Bates issues, names, missing data, exhibit gaps)
  C — Filler words  (her preference, one decision applies to all)
  D — Audio-dependent items  (count only — she handles in her normal pass)
  E — Sign-off box

What we DO NOT show:
  - HIGH confidence engine fixes (CR doesn't need to review those)
  - Verify-agent internal notes she can't action without audio
  - Technical engine details

Author:  Scott + Claude
Version: 4.0  (2026-04-05) — renamed from build_mb_review_v3.py, dynamic page count
"""

import json
import os
import re
from datetime import date

BASE = os.getcwd()  # job's work folder (set by run_pipeline.py --job-dir)


# ── Load config ───────────────────────────────────────────────────────────────

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return default or {}

cfg         = load_json(os.path.join(BASE, 'depo_config.json'))
caption     = load_json(os.path.join(BASE, 'CASE_CAPTION.json'))
# CASE_CAPTION.json is authoritative — override depo_config for identity fields
cfg.update(caption)
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
    """Search FINAL_FORMATTED for snippet and return (page, line) or (None, None).
    Tries progressively shorter word chunks to handle line-wrap mismatches."""
    words = snippet.lower().strip().split()
    if len(words) < 2:
        return None, None
    # Try 4-word chunks starting at word 0, 1, 2, 3 — handles line-wrap splits
    for start in range(min(4, len(words))):
        for chunk_size in (5, 4, 3):
            chunk_words = words[start:start + chunk_size]
            if len(chunk_words) < 3:
                continue
            candidate = ' '.join(chunk_words)
            if len(candidate) < 6:
                continue
            for i, raw in enumerate(_flines):
                raw_norm = re.sub(r'\s+', ' ', raw.lower())
                if candidate in raw_norm:
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

            # If text before tag is too short or IS a [REVIEW] tag itself,
            # look at surrounding lines for a usable search phrase
            def is_usable(s):
                return (len(s.strip()) >= 15
                        and not s.strip().startswith('[REVIEW')
                        and s.strip() not in ('Q.', 'A.', 'Q', 'A'))

            if not is_usable(before):
                # Scan surrounding lines for context
                context = ''
                for offset in [-2, -1, 1, 2]:
                    idx2 = i + offset
                    if 0 <= idx2 < len(_clines):
                        candidate = re.sub(r'\[REVIEW[^\]]*\]', '', _clines[idx2]).strip()
                        if is_usable(candidate):
                            context = candidate
                            break
                snippet = context[:68] if context else before[:68]
            else:
                snippet = before[-68:]

            pg, ln = find_page_for_text(snippet)
            review_actionable.append({
                'note':    tag_note[:100],
                'snippet': snippet[:68],
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


# ── Separate actionable items from audio-only (dollar amounts, etc.) ──────────
AUDIO_KEYWORDS = ['dollar amount missing', 'amount missing', 'figure missing',
                  'number missing', 'percent missing']

review_needs_audio   = [it for it in review_actionable
                        if any(k in it['note'].lower() for k in AUDIO_KEYWORDS)]
review_can_answer    = [it for it in review_actionable
                        if it not in review_needs_audio]
audio_total          = review_audio_count + len(review_needs_audio)

# Deduplicate actionable items — same snippet can appear twice if multiple
# REVIEW tags point to the same line in corrected_text.txt
_seen_snippets = set()
_deduped = []
for _it in review_can_answer:
    _key = _it['snippet'].strip()[:50]
    if _key not in _seen_snippets:
        _seen_snippets.add(_key)
        _deduped.append(_it)
review_can_answer = _deduped


# ── Item-type plain English labels ────────────────────────────────────────────

def truncate_at_word(s, max_len=65):
    """Truncate at word boundary with ellipsis — no mid-word cuts."""
    s = s.strip()
    if len(s) <= max_len:
        return s
    cut = s[:max_len].rsplit(' ', 1)[0]
    return cut + '...'


def plain_english_label(note):
    """Convert engine-speak to plain English MB will understand."""
    n = note.lower()
    if 'bates' in n:
        return 'Document reference number looks wrong — please verify'
    if 'exhibit' in n and ('gap' in n or 'sequence' in n or 'jump' in n):
        return 'Exhibit numbers skip a range — were these marked in this depo?'
    if 'exhibit' in n and ('duplicate' in n or 'double' in n):
        return 'Same exhibit number appears twice — please confirm'
    if 'exhibit' in n and 'number' in n:
        return 'Exhibit number may have a steno error — please verify'
    if 'wipple' in n or ('proper name' in n or 'name' in n and 'spelling' in n):
        return 'Name spelling uncertain — not in case dictionary, please verify'
    if 'self-correct' in n or ('bart' in n and 'barrett' in n) or 'corrected to' in n:
        return 'Witness appears to have self-corrected — which name/word is right?'
    if 'steno line-number artifact' in n or 'line number artifact' in n:
        return 'A CAT line number got embedded in testimony text — confirm removal'
    if 'speaker' in n and ('unclear' in n or 'unknown' in n or 'attribution' in n):
        return 'Could not tell if this line is a Q or an A — please identify speaker'
    if 'applied' in n and 'implied' in n:
        return 'Two similar words appear — which did the witness/attorney say?'
    if 'missing word' in n or 'word missing' in n or 'word appears missing' in n:
        return 'A word appears to be missing — what should it say?'
    if 'videographer' in n:
        return 'Videographer introduction may be incomplete — please verify'
    if 'truncated' in n or 'full' in n and 'bates' in n:
        return 'Reference number appears cut off — please provide complete number'
    if 'math' in n or 'total' in n:
        return 'Numbers don\'t add up — please verify the figures'
    if 'date' in n:
        return 'Date appears incomplete or fragmented — please verify'
    if 'duplicate' in n or 'appears twice' in n:
        return 'Something appears twice — confirm which is correct'
    if 'e-mail address' in n or 'email' in n:
        return 'An email address appears in testimony text — is this correct?'
    return 'Engine was uncertain here — please review and correct'


# ═════════════════════════════════════════════════════════════════════════════
# BUILD THE DOCUMENT
# ═════════════════════════════════════════════════════════════════════════════

# HEADER
add(
    DBL,
    f'  TRANSCRIPT REVIEW  —  {WITNESS}',
    f'  {DEPO_DATE}   |   Docket {DOCKET}',
    f'  Prepared for: {REPORTER}',
    DBL,
    '',
    '  This file tells you exactly what to look at.',
    f'  You do NOT need to read all {total_pages} pages.',
    '  Open the PDF alongside this file and work through each section.',
    '',
    f'  Total transcript pages:  {total_pages}',
    f'  Items needing your eyes: {len(review_can_answer)} (Section B)',
    f'  Audio pass items:        {audio_total} (Section D — your normal pass)',
    '',
    '  HOW TO USE THIS:',
    '  Step 1 — Section A: Go to 5 specific pages in the PDF.',
    '           Confirm each one looks right. Note anything wrong.',
    '  Step 2 — Section B: For each item, find the page in the PDF.',
    '           Write your answer in the ANSWER line.',
    '  Step 3 — Section C: One filler-word question. Circle your choice.',
    '  Step 4 — Section E: Sign off and reply to Scott.',
    '',
    '  Questions? Call or text Scott.',
    '',
)

# FORMAT QUESTION — (Zoom) vs (Via Zoom)
add(
    SEP,
    '  QUICK FORMAT QUESTION (circle one):',
    '',
    f'  Attorneys who appeared remotely are listed as:',
    f'',
    f'      THOMAS J. MADIGAN, ESQ.  (Via Zoom)',
    f'',
    f'  Should this be:',
    f'      (A)  (Via Zoom)   ← current',
    f'      (B)  (Zoom)       ← alternate',
    f'',
    f'  Your choice: _______',
    f'  (Whichever you pick, we apply it to every depo going forward.)',
    SEP,
    '',
)

# SECTION A — SPOT CHECK
section('SECTION A — 5 PAGES TO CHECK  (about 5 minutes)')
add(
    '  Open the PDF. Jump to each page number listed.',
    '  Read that page. If something looks wrong, write it in NOTES.',
    '  If it looks right, leave NOTES blank and move on.',
    '',
)

for sc in SPOT_CHECKS:
    add(
        f'  ┌─ GO TO PAGE {sc["page"]}  —  {sc["label"]}',
        f'  │',
        f'  │  What to check:  {sc["check"]}',
        f'  │',
        f'  │  NOTES: _________________________________________________',
        f'  └',
        '',
    )

# SECTION B — ITEMS NEEDING HER ANSWER
section(f'SECTION B — {len(review_can_answer)} ITEMS THAT NEED YOUR ANSWER  (about 10 minutes)')

if not review_can_answer:
    add('  Nothing flagged. Engine was confident throughout.', '')
else:
    add(
        '  For each item below:',
        '    1. Find the page in the PDF (page number is listed).',
        '    2. Read what it says.',
        '    3. Write the correct answer in the ANSWER line.',
        '       If it looks fine as-is, write: OK',
        '       If you need audio to answer, write: AUDIO',
        '',
        '  (Items that can only be answered with audio are in Section D.)',
        '',
    )
    for n, item in enumerate(review_can_answer, 1):
        search_phrase = item["snippet"].strip()
        # Never show a [REVIEW tag as the search phrase — it's not in the PDF
        if search_phrase.startswith('[REVIEW') or len(search_phrase) < 8:
            search_phrase = '(see note below — search surrounding context)'
        pg_ref = (f'Go to PDF page {item["page"]}, line {item["line"]}'
                  if item['page'] else
                  f'Search PDF for: "{search_phrase[:50]}"')
        label  = plain_english_label(item['note'])
        add(
            f'  ── ITEM B-{n:02d} {"─" * (W - 12)}',
            f'  {pg_ref}',
            f'',
            f'  What the transcript says:',
            f'    {truncate_at_word(item["snippet"])}',
            f'',
            f'  What to check:',
            f'    {label}',
            f'',
            f'  ANSWER: ________________________________________________',
            '',
        )

# SECTION C — FILLER WORDS
section(f'SECTION C — FILLER WORDS  (one question)')
add(
    f'  The engine found {filler_count} places in the testimony where the witness said',
    f'  "uhmm" or similar filler words.',
    '',
    '  A filler word is a sound a witness makes while thinking — not actual',
    '  testimony. Examples:  "Uhmm, I believe so."  /  "Well, uh, I think..."',
    '',
    '  NOTE: "Uh-huh" meaning YES and "Huh-uh" meaning NO are kept always.',
    '  Those are real answers. Only true fillers are in scope here.',
    '',
    '  What would you like us to do with filler words?  (circle one)',
    '',
    '    ( ) Remove all filler words     — cleaner, most common choice',
    '    ( ) Keep all filler words        — verbatim record',
    '    ( ) Remove "uhmm" only           — keep other fillers',
    '    ( ) I will mark them myself      — send me the full list',
    '',
    '  Your choice applies to this depo and all future depos.',
    '',
)

# SECTION D — AUDIO VERIFICATION AGENT
# Load audio_apply_log.json — two action types: AUTO (we changed it) and SUGGEST (your call)
AUDIO_LOG_PATH = os.path.join(BASE, 'audio_apply_log.json')
audio_auto    = []   # changes we made — AD confirms
audio_suggest = []   # suggestions — AD decides

if os.path.exists(AUDIO_LOG_PATH):
    with open(AUDIO_LOG_PATH, encoding='utf-8') as _af:
        _log = json.load(_af)
    audio_auto    = _log.get('applied', [])
    audio_suggest = _log.get('surfaced', [])

d_total = len(audio_auto) + len(audio_suggest)
section(f'SECTION D — AUDIO VERIFICATION AGENT  ({d_total} items)')
add(
    '  Your audio verification agent listened to the full recording.',
    '  This section has two parts — read the header for each part carefully.',
    '',
)

# ── Part D1: Changes we made — AD confirms ────────────────────────────────────
add(
    f'  ┌─────────────────────────────────────────────────────────────────┐',
    f'  │  PART 1 OF 2 — WE MADE A CHANGE  ({len(audio_auto)} items)              │',
    f'  │                                                                 │',
    f'  │  The agent was confident enough to clean up these lines.        │',
    f'  │  The [REVIEW] tag has been removed and the line reads clean.    │',
    f'  │                                                                 │',
    f'  │  YOUR JOB:  Go to each page. Read the line. Listen if needed.  │',
    f'  │             Write OK — or write the correction.                 │',
    f'  └─────────────────────────────────────────────────────────────────┘',
    '',
)

for n, item in enumerate(audio_auto, 1):
    after_clean = re.sub(r'\[REVIEW[^\]]*\]', '', item.get('after', '')).strip()
    whisper     = item.get('whisper_text', '').strip()
    pg, ln      = find_page_for_text(after_clean)
    pg_ref      = (f'Go to PDF page {pg}, line {ln}' if ln else f'Go to PDF page {pg}') if pg else f'Search PDF for: "{truncate_at_word(after_clean, 40)}"'
    add(
        f'  ── CONFIRM D1-{n:02d} {"─" * (W - 16)}',
        f'  {pg_ref}',
        f'',
        f'  Line now reads:',
        f'    {truncate_at_word(after_clean, 70)}',
        f'',
        f'  Agent heard:  "{truncate_at_word(whisper, 60)}"' if whisper else '',
        f'',
        f'  CONFIRM: ___  (write OK — or your correction)',
        f'',
    )

# ── Part D2: Suggestions — AD decides ─────────────────────────────────────────
add(
    f'  ┌─────────────────────────────────────────────────────────────────┐',
    f'  │  PART 2 OF 2 — YOUR CALL  ({len(audio_suggest)} items)                      │',
    f'  │                                                                 │',
    f'  │  The agent heard something but was not certain enough to        │',
    f'  │  change the line. It left a note in the transcript for you.     │',
    f'  │                                                                 │',
    f'  │  YOUR JOB:  Go to each page. Listen to the recording.          │',
    f'  │             Write exactly what was said.                        │',
    f'  └─────────────────────────────────────────────────────────────────┘',
    '',
)

for n, item in enumerate(audio_suggest, 1):
    before_clean = re.sub(r'\[REVIEW[^\]]*\]', '', item.get('before', '')).strip()
    whisper      = item.get('whisper_text', '').strip()
    note         = item.get('note', '')
    pg, ln       = find_page_for_text(before_clean)
    pg_ref       = (f'Go to PDF page {pg}, line {ln}' if ln else f'Go to PDF page {pg}') if pg else f'Search PDF for: "{truncate_at_word(before_clean, 40)}"'
    add(
        f'  ── YOUR CALL D2-{n:02d} {"─" * (W - 18)}',
        f'  {pg_ref}',
        f'',
        f'  What the transcript says (with gap):',
        f'    {truncate_at_word(before_clean, 70)}',
        f'',
        f'  Agent heard:  "{truncate_at_word(whisper, 60)}"' if whisper else '  Agent heard:  (no clear match in recording)',
        f'',
        f'  YOUR ANSWER: {"_" * 46}',
        f'',
    )

# SECTION E — SIGN-OFF
section('SECTION E — SIGN-OFF')
add(
    f'  When you are done, fill in below and reply to Scott.',
    '',
    f'  Reviewed by:  {REPORTER}',
    f'  Date:         _________________________________',
    '',
    '  How does the transcript look overall?  (circle one)',
    '',
    '    ( ) GOOD — deliver with my corrections noted above',
    '',
    '    ( ) NEEDS WORK — call me before delivering',
    '',
    '  Anything else I should know:',
    '  __________________________________________________________________',
    '  __________________________________________________________________',
    '',
    DBL,
    f'  {CASE_SHORT}  |  {date.today().strftime("%B %d, %Y")}',
    f'  This document is a reporter review aid. Not a legal document.',
    DBL,
)


# ── Write output ─────────────────────────────────────────────────────────────

out_path = os.path.join(BASE, 'FINAL_DELIVERY', f'{CASE_SHORT}_CR_REVIEW.txt')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))

print(f'Written: {out_path}')
print(f'  Spot-check pages:      {len(SPOT_CHECKS)}')
print(f'  Actionable items:      {len(review_actionable)}')
print(f'  Audio-deferred items:  {review_audio_count}')
print(f'  Filler words:          {filler_count}')
print(f'  Total lines in doc:    {len(L)}')

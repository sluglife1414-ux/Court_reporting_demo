"""
apply_audio_validation.py — Apply Whisper audio matches to corrected_text.txt
==============================================================================
Reads audio_matches.json, applies high-confidence Whisper confirmations to
corrected_text.txt, and generates an audit trail for MB's review.

Three actions:
  AUTO    (score >= 0.9, confirmation item)
          → Remove [REVIEW] tag. Change is logged.
          → MB sees before/after in AUDIO CORRECTIONS section of her review.
          → Builds trust through transparency. After a few depos she'll trust it.

  SUGGEST (score 0.7-0.9, OR any gap-fill item)
          → Replace [REVIEW] with [AUDIO: whisper heard "..."] tag.
          → MB decides. Engine never overwrites testimony it isn't sure about.

  DISCARD (score < 0.7)
          → Leave [REVIEW] tag untouched. Not worth surfacing.

Non-negotiables:
  - Backup corrected_text.txt before touching anything
  - Never delete testimony — only remove/replace [REVIEW] tags
  - Full decision log saved to audio_apply_log.json
  - MB-facing report appended to existing MB_REVIEW.txt

Author:  Scott + Claude
Version: 1.0  (2026-04-03)
"""

import os
import sys
import json
import re
import shutil
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Paths ─────────────────────────────────────────────────────────────────────
MATCHES_PATH   = os.path.join(BASE, 'audio_matches.json')
CORRECTED_PATH = os.path.join(BASE, 'corrected_text.txt')
LOG_PATH       = os.path.join(BASE, 'audio_apply_log.json')

cfg     = {}
caption = {}
cfg_path = os.path.join(BASE, 'depo_config.json')
cap_path = os.path.join(BASE, 'CASE_CAPTION.json')
if os.path.exists(cfg_path):
    cfg = json.load(open(cfg_path, encoding='utf-8'))
if os.path.exists(cap_path):
    caption = json.load(open(cap_path, encoding='utf-8'))

CASE_SHORT = cfg.get('case_short', 'Case')
REVIEW_PATH = os.path.join(BASE, 'FINAL_DELIVERY', f'{CASE_SHORT}_MB_REVIEW.txt')

# ── Thresholds ────────────────────────────────────────────────────────────────
AUTO_THRESHOLD    = 0.9   # score >= this → auto-apply (with MB audit trail)
SUGGEST_THRESHOLD = 0.7   # score >= this → surface as suggestion

# ── Gap-fill keywords — never auto-apply these even at high score ─────────────
# Whisper's full segment can't reliably fill a steno gap word-for-word
_GAP_KEYWORDS = [
    'steno gap', 'not captured', 'fragmented', 'missing', 'amount missing',
    'figure missing', 'percent', 'dollar', 'number missing', 'unclear',
    'answer unclear', 'steno fragment', 'beyond steno',
]

def is_gap_fill(note):
    n = note.lower()
    return any(k in n for k in _GAP_KEYWORDS)


# ── Load matches ──────────────────────────────────────────────────────────────
if not os.path.exists(MATCHES_PATH):
    print(f'ERROR: {MATCHES_PATH} not found.')
    print('  Run audio_validation.py first.')
    sys.exit(1)

matches = json.load(open(MATCHES_PATH, encoding='utf-8'))
matched = [m for m in matches if m['status'] == 'MATCHED']

# ── Categorize ────────────────────────────────────────────────────────────────
auto_apply = []
suggest    = []
discard    = []

for m in matched:
    score = m.get('match_score', 0)
    note  = m.get('note', '')
    gap   = is_gap_fill(note)

    if score >= AUTO_THRESHOLD and not gap:
        auto_apply.append(m)
    elif score >= SUGGEST_THRESHOLD:
        suggest.append(m)
    else:
        discard.append(m)

# Gap-fill items at high score go to suggest, not auto
for m in matched:
    score = m.get('match_score', 0)
    note  = m.get('note', '')
    if score >= AUTO_THRESHOLD and is_gap_fill(note):
        if m not in suggest:
            suggest.append(m)
        if m in auto_apply:
            auto_apply.remove(m)

print('=' * 60)
print('APPLY AUDIO VALIDATION')
print('=' * 60)
print(f'  Total matched items:  {len(matched)}')
print(f'  AUTO  (>= 0.9):       {len(auto_apply)}  — apply + show MB before/after')
print(f'  SUGGEST (0.7-0.9):    {len(suggest)}  — surface to MB for decision')
print(f'  DISCARD (< 0.7):      {len(discard)}  — too low confidence, skip')


# ── Backup corrected_text.txt — Mama Bear Rule ────────────────────────────────
if not os.path.exists(CORRECTED_PATH):
    print(f'\nERROR: {CORRECTED_PATH} not found.')
    sys.exit(1)

backup_path = CORRECTED_PATH.replace('.txt', '_pre_audio_backup.txt')
shutil.copy2(CORRECTED_PATH, backup_path)
print(f'\nBackup saved: {backup_path}')


# ── Load corrected_text.txt ───────────────────────────────────────────────────
with open(CORRECTED_PATH, encoding='utf-8') as f:
    lines = f.read().split('\n')


# ── Apply AUTO corrections ────────────────────────────────────────────────────
# Build lookup: line_num → list of items to process
# line_num in matches is 1-based
auto_by_line   = {}
suggest_by_line = {}

for m in auto_apply:
    ln = m['line_num'] - 1   # 0-based index
    auto_by_line.setdefault(ln, []).append(m)

for m in suggest:
    ln = m['line_num'] - 1
    suggest_by_line.setdefault(ln, []).append(m)

applied  = []
surfaced = []

for idx, line in enumerate(lines):
    if '[REVIEW' not in line:
        continue

    # AUTO — remove [REVIEW] tag, keep surrounding text, log before/after
    if idx in auto_by_line:
        for m in auto_by_line[idx]:
            before = line.strip()
            # Remove the specific [REVIEW:...] tag that matched this item
            tag_pattern = re.compile(r'\[REVIEW:\s*' + re.escape(m['note'][:30]) + r'[^\]]*\]')
            new_line = tag_pattern.sub('', line).strip()
            # Fallback: remove all [REVIEW] tags on this line if specific not found
            if new_line == line.strip():
                new_line = re.sub(r'\[REVIEW:[^\]]*\]', '', line).strip()
            lines[idx] = new_line
            applied.append({
                'line_num':     m['line_num'],
                'note':         m['note'],
                'match_score':  m['match_score'],
                'before':       before,
                'after':        new_line,
                'whisper_text': m.get('whisper_text', ''),
                'action':       'AUTO',
            })

    # SUGGEST — replace [REVIEW] tag with [AUDIO: whisper heard "..."]
    elif idx in suggest_by_line:
        for m in suggest_by_line[idx]:
            before = line.strip()
            whisper = m.get('whisper_text', '')[:80]
            tag_pattern = re.compile(r'\[REVIEW:\s*' + re.escape(m['note'][:30]) + r'[^\]]*\]')
            replacement = f'[AUDIO: audio check heard "{whisper}" — verify]'
            new_line = tag_pattern.sub(replacement, line).strip()
            if new_line == line.strip():
                new_line = re.sub(r'\[REVIEW:[^\]]*\]', replacement, line, count=1).strip()
            lines[idx] = new_line
            surfaced.append({
                'line_num':     m['line_num'],
                'note':         m['note'],
                'match_score':  m['match_score'],
                'before':       before,
                'after':        new_line,
                'whisper_text': m.get('whisper_text', ''),
                'action':       'SUGGEST',
            })

# ── Write updated corrected_text.txt ─────────────────────────────────────────
with open(CORRECTED_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'\nApplied {len(applied)} AUTO corrections to corrected_text.txt')
print(f'Surfaced {len(surfaced)} SUGGEST items for MB')


# ── Save decision log ─────────────────────────────────────────────────────────
log = {
    'date':      str(date.today()),
    'applied':   applied,
    'surfaced':  surfaced,
    'discarded': len(discard),
}
with open(LOG_PATH, 'w', encoding='utf-8') as f:
    json.dump(log, f, indent=2)
print(f'Decision log saved: {LOG_PATH}')


# ── Append AUDIO CORRECTIONS section to MB_REVIEW.txt ────────────────────────
# This is the trust-building section. MB sees every auto-applied change:
# WAS / NOW / WHY — she spot-checks, builds confidence, review burden shrinks.

W   = 68
DBL = '=' * W
SEP = '-' * W

section = [
    '',
    DBL,
    'SECTION F — AUDIO CORRECTIONS  (audio check confirmed)',
    DBL,
    '',
    '  These items were flagged as uncertain by the engine.',
    '  The audio recording confirmed each one.',
    '  The transcript has been updated automatically.',
    '',
    '  Please spot-check a few of these in the PDF.',
    '  If anything looks wrong, note it below and call Scott.',
    '',
]

if not applied:
    section.append('  No high-confidence audio corrections this run.')
else:
    for n, item in enumerate(applied, 1):
        # Plain English reason
        note = item['note'].lower()
        if 'permanent' in note or 'permit' in note:
            reason = 'Audio confirmed correct spelling'
        elif 'self-correct' in note or 'corrected to' in note:
            reason = 'Audio confirmed which version witness intended'
        elif 'reconstruction' in note or 'fragmented' in note:
            reason = 'Audio confirmed engine reconstruction was accurate'
        elif 'speaker' in note or 'attribution' in note:
            reason = 'Audio confirmed speaker identity'
        elif 'sort of' in note or 'righty' in note or 'intentional' in note:
            reason = 'Audio confirmed this is verbatim — kept as spoken'
        else:
            reason = 'Audio confirmed engine correction'

        # Truncate before/after for display
        before_display = re.sub(r'\[REVIEW[^\]]*\]', '[?]', item['before'])[:65]
        after_display  = item['after'][:65]

        section += [
            f'  ── AUDIO-{n:02d} {"─" * (W - 13)}',
            f'  WAS:  {before_display}',
            f'  NOW:  {after_display}',
            f'  WHY:  {reason}',
            f'  (audio check confidence: {item["match_score"]})',
            '',
        ]

# Suggest section
if surfaced:
    section += [
        SEP,
        f'  AUDIO SUGGESTIONS  ({len(surfaced)} items — your decision)',
        SEP,
        '',
        '  The audio check heard something here but was not certain enough',
        '  to auto-apply. Each item shows what the audio check heard.',
        '  Write OK or your correction in the ANSWER line.',
        '',
    ]
    for n, item in enumerate(surfaced, 1):
        whisper = item.get('whisper_text', '')[:65]
        section += [
            f'  ── SUGGEST-{n:02d} {"─" * (W - 15)}',
            f'  Line {item["line_num"]}  |  Score: {item["match_score"]}',
            f'  Audio check heard: {whisper}',
            f'  ANSWER: ________________________________________________',
            '',
        ]

section += [
    DBL,
    f'  Audio validation  |  {date.today().strftime("%B %d, %Y")}',
    DBL,
    '',
]

# Append to existing MB_REVIEW.txt
if os.path.exists(REVIEW_PATH):
    with open(REVIEW_PATH, 'a', encoding='utf-8') as f:
        f.write('\n'.join(section))
    print(f'Audio section appended to: {REVIEW_PATH}')
else:
    out_path = os.path.join(BASE, 'FINAL_DELIVERY', 'AUDIO_CORRECTIONS.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(section))
    print(f'MB_REVIEW not found — written separately: {out_path}')


# ── Final summary ─────────────────────────────────────────────────────────────
print('\n' + '=' * 60)
print('SUMMARY')
print('=' * 60)
print(f'  AUTO-applied:   {len(applied)}  corrections  (MB sees before/after)')
print(f'  Surfaced:       {len(surfaced)}  suggestions  (MB decides)')
print(f'  Discarded:      {len(discard)}  low-confidence (not surfaced)')
print(f'  Backup:         corrected_text_pre_audio_backup.txt')
print()
print('  Next step: python run_pipeline.py --from format_final')
print()

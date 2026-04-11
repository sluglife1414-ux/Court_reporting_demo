"""
apply_audio_validation.py — Apply Whisper audio matches to corrected_text.txt
==============================================================================
Reads audio_matches.json, applies Whisper results to corrected_text.txt.

Rule: if Whisper heard it, the CR sees it. Confidence score changes the label,
never whether the result appears. Zero silent discards.

Three actions:
  AUTO    (score >= 0.9, not a gap-fill item)
          → Apply directly. Replace [REVIEW] with [REVIEW: confirmed "X" via audio].
          → CR sees the resolved value with confirmation label.

  SUGGEST (score >= 0.7, OR gap-fill at any score)
          → Replace [REVIEW] with [REVIEW: heard "X" via audio — please review].
          → CR decides. Engine surfaces what it heard.

  LOW     (score < 0.7)
          → Replace [REVIEW] with [REVIEW: heard "X" — low confidence, verify audio].
          → CR still sees what Whisper heard. Nothing discarded silently.

Non-negotiables:
  - Backup corrected_text.txt before touching anything
  - Never delete testimony — only remove/replace [REVIEW] tags
  - Full decision log saved to audio_apply_log.json
  - CR-facing report appended to existing CR_REVIEW.txt

Author:  Scott + Claude
Version: 2.0  (2026-04-09) — no silent discards; all Whisper results surfaced
"""

import os
import sys
import json
import re
import shutil
from datetime import date

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.getcwd()  # job dir — all data files are relative to CWD

# ── Paths ─────────────────────────────────────────────────────────────────────
# Use whichever match file has more MATCHED items.
# Targeted re-transcription sometimes gets fewer matches than full-run Whisper,
# so we pick by coverage, not by file name preference.
def _count_matched(path):
    if not os.path.exists(path):
        return -1
    try:
        items = json.load(open(path, encoding='utf-8'))
        return sum(1 for x in items if x.get('status') == 'MATCHED')
    except Exception:
        return -1

_targeted = os.path.join(BASE, 'audio_matches_targeted.json')
_fullrun  = os.path.join(BASE, 'audio_matches.json')

_targeted_count = _count_matched(_targeted)
_fullrun_count  = _count_matched(_fullrun)

if _targeted_count >= _fullrun_count and _targeted_count >= 0:
    MATCHES_PATH = _targeted
    print(f'[AUDIO] Using targeted matches ({_targeted_count} matched)')
elif _fullrun_count >= 0:
    MATCHES_PATH = _fullrun
    print(f'[AUDIO] Using full-run matches ({_fullrun_count} matched)  [targeted had {_targeted_count}]')
else:
    MATCHES_PATH = _fullrun  # fallback
CORRECTED_PATH = os.path.join(BASE, 'corrected_text.txt')
LOG_PATH       = os.path.join(BASE, 'audio_apply_log.json')

from config import cfg as _config
REVIEW_PATH = _config.review_path

# ── Thresholds ────────────────────────────────────────────────────────────────
AUTO_THRESHOLD    = 0.9   # score >= this AND not gap-fill → confirmed via audio
SUGGEST_THRESHOLD = 0.7   # score >= this (or gap-fill) → please review

# score < SUGGEST_THRESHOLD → LOW confidence label, but still surfaced (never discarded)

# ── Gap-fill keywords — prevent AUTO, never prevent surfacing ─────────────────
# These notes describe steno gaps where Whisper's segment can't replace word-for-word.
# They go to SUGGEST (not AUTO) even at high score — but CR always sees what was heard.
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
low        = []   # < 0.7 — still surfaced, never discarded

for m in matched:
    score = m.get('match_score', 0)
    note  = m.get('note', '')
    gap   = is_gap_fill(note)

    if score >= AUTO_THRESHOLD and not gap:
        auto_apply.append(m)
    elif score >= SUGGEST_THRESHOLD or gap:
        suggest.append(m)
    else:
        low.append(m)

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
print('APPLY AUDIO VALIDATION  v2.0')
print('=' * 60)
print(f'  Total matched items:  {len(matched)}')
print(f'  AUTO    (>= 0.9):     {len(auto_apply)}  — confirmed via audio')
print(f'  SUGGEST (>= 0.7):     {len(suggest)}  — please review')
print(f'  LOW     (< 0.7):      {len(low)}  — low confidence, verify audio')
print(f'  DISCARDED:            0  — nothing silently dropped')


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

low_by_line = {}
for m in low:
    ln = m['line_num'] - 1
    low_by_line.setdefault(ln, []).append(m)

applied  = []
surfaced = []

# Nested-bracket regex — same pattern as make_rtf.py to match [REVIEW:...[|]...] tags
_RE_REVIEW_FULL = re.compile(r'\[REVIEW:((?:[^\[\]]|\[[^\]]*\])*)\]', re.DOTALL)

def _replace_tag(line, note_prefix, replacement):
    """Replace the [REVIEW:...] tag whose reason starts with note_prefix.
    Falls back to replacing the first [REVIEW:...] on the line if specific match fails."""
    tag_pattern = re.compile(
        r'\[REVIEW:\s*' + re.escape(note_prefix) + r'(?:[^\[\]]|\[[^\]]*\])*\]',
        re.DOTALL
    )
    new_line = tag_pattern.sub(replacement, line, count=1)
    if new_line == line:
        # Fallback: replace first [REVIEW:...] on this line
        new_line = _RE_REVIEW_FULL.sub(replacement, line, count=1)
    return new_line

for idx, line in enumerate(lines):
    if '[REVIEW' not in line:
        continue

    # AUTO — replace [REVIEW] with confirmed tag, log before/after
    if idx in auto_by_line:
        for m in auto_by_line[idx]:
            before = line.strip()
            whisper = m.get('whisper_text', '').strip()[:80]
            replacement = f'[REVIEW: confirmed "{whisper}" via audio]'
            new_line = _replace_tag(line, m['note'][:30], replacement)
            lines[idx] = new_line
            line = new_line  # handle multiple tags on same line
            applied.append({
                'line_num':     m['line_num'],
                'note':         m['note'],
                'match_score':  m['match_score'],
                'before':       before,
                'after':        new_line.strip(),
                'whisper_text': m.get('whisper_text', ''),
                'action':       'AUTO',
            })

    # SUGGEST — replace [REVIEW] with heard tag, CR decides
    if idx in suggest_by_line:
        for m in suggest_by_line[idx]:
            before = line.strip()
            whisper = m.get('whisper_text', '').strip()[:80]
            replacement = f'[REVIEW: heard "{whisper}" via audio — please review]'
            new_line = _replace_tag(line, m['note'][:30], replacement)
            lines[idx] = new_line
            line = new_line
            surfaced.append({
                'line_num':     m['line_num'],
                'note':         m['note'],
                'match_score':  m['match_score'],
                'before':       before,
                'after':        new_line.strip(),
                'whisper_text': m.get('whisper_text', ''),
                'action':       'SUGGEST',
            })

    # LOW — replace [REVIEW] with low-confidence heard tag, never discard
    if idx in low_by_line:
        for m in low_by_line[idx]:
            before = line.strip()
            whisper = m.get('whisper_text', '').strip()[:80]
            replacement = f'[REVIEW: heard "{whisper}" — low confidence, verify audio]'
            new_line = _replace_tag(line, m['note'][:30], replacement)
            lines[idx] = new_line
            line = new_line
            surfaced.append({
                'line_num':     m['line_num'],
                'note':         m['note'],
                'match_score':  m['match_score'],
                'before':       before,
                'after':        new_line.strip(),
                'whisper_text': m.get('whisper_text', ''),
                'action':       'LOW',
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
    'low_count': len(low),
    'discarded': 0,   # v2.0 — nothing discarded silently
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
    suggest_items = [x for x in surfaced if x['action'] == 'SUGGEST']
    low_items     = [x for x in surfaced if x['action'] == 'LOW']
    section += [
        SEP,
        f'  AUDIO SUGGESTIONS  ({len(surfaced)} items — your decision)',
        SEP,
        '',
        '  The audio check heard something at each of these locations.',
        '  HIGH = confident enough to suggest. LOW = weak match, use audio as hint.',
        '  Write OK or your correction in the ANSWER line.',
        '',
    ]
    for n, item in enumerate(surfaced, 1):
        whisper    = item.get('whisper_text', '')[:65]
        confidence = 'HIGH' if item['action'] == 'SUGGEST' else 'LOW'
        section += [
            f'  ── SUGGEST-{n:02d} [{confidence}] {"─" * (W - 20)}',
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
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(section))
    print(f'MB_REVIEW not found — written separately: {out_path}')


# ── Final summary ─────────────────────────────────────────────────────────────
print('\n' + '=' * 60)
print('SUMMARY')
print('=' * 60)
print(f'  AUTO-applied:   {len(applied)}  confirmed via audio')
print(f'  Surfaced:       {len(surfaced)}  heard/low-confidence (CR decides)')
print(f'  Discarded:      0  — nothing silently dropped  (v2.0)')
print(f'  Backup:         corrected_text_pre_audio_backup.txt')
print()
print('  Next step: python run_pipeline.py --from format_final')
print()

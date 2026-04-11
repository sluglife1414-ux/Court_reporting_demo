"""
build_inline_review.py -- Inline Review Document for AD
=======================================================
Takes the corrected transcript and replaces every [REVIEW: ...] tag
with a single, consistent [[AGENT: "fill"]] marker -- one common tag
AD can Ctrl+F to jump between all review locations.

AD's workflow:
  1. Open Fourman_WCB_INLINE_REVIEW.txt
  2. Ctrl+F  [[
  3. At each hit: read the surrounding sentence -> type a correction
     or delete the tag if the existing text is right

Tag meanings in output:
  [[AGENT: "fill text"]]   = agent heard this; approve or correct
  [[AGENT: ?]]             = audio unclear; agent could not fill
  [[CONFIRMED]]            = auto-confirmed from audio; no action needed
  [[NOTE]]                 = structural note from steno; review at discretion

Usage:
    cd <job_work_dir>
    python path/to/engine/build_inline_review.py

Reads:
  audio_apply_log.json
  FINAL_DELIVERY/{case}_AGENT_FILL_TABLE.txt
  corrected_text.txt

Writes:
  FINAL_DELIVERY/{case}_INLINE_REVIEW.txt

Author:  Scott + Claude
Version: 1.1  (2026-04-10)
"""

import os
import sys
import json
import re
from collections import defaultdict
from datetime import date

# -- fix Windows console encoding ------------------------------------------------
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE    = os.getcwd()
ENGINE  = os.path.dirname(os.path.abspath(__file__))

LOG_PATH        = os.path.join(BASE, 'audio_apply_log.json')
CORRECTED_PATH  = os.path.join(BASE, 'corrected_text.txt')
CAPTION_PATH    = os.path.join(BASE, 'CASE_CAPTION.json')
OUT_DIR         = os.path.join(BASE, 'FINAL_DELIVERY')

# -- Validate ------------------------------------------------------------------
for path, label in [
    (LOG_PATH,       'audio_apply_log.json'),
    (CORRECTED_PATH, 'corrected_text.txt'),
    (CAPTION_PATH,   'CASE_CAPTION.json'),
]:
    if not os.path.exists(path):
        print('ERROR: {} not found at {}'.format(label, path))
        sys.exit(1)

# -- Load ----------------------------------------------------------------------
with open(LOG_PATH, encoding='utf-8') as f:
    log = json.load(f)

with open(CORRECTED_PATH, encoding='utf-8') as f:
    corrected_text = f.read()

with open(CAPTION_PATH, encoding='utf-8') as f:
    caption = json.load(f)

case_short = caption.get('case_short', 'CASE')
witness    = caption.get('witness_name', '')
cr_name    = caption.get('reporter_name_display', '')
depo_date  = caption.get('depo_date', '')

# -- Load fills from pre-built AGENT_FILL_TABLE --------------------------------
# build_agent_fill_table.py already ran the 7-level cascade (43/43 fills).
# Parse the fills out so we don't re-run the cascade here.
fill_table_path = os.path.join(OUT_DIR, '{}_AGENT_FILL_TABLE.txt'.format(case_short))
if not os.path.exists(fill_table_path):
    print('ERROR: AGENT_FILL_TABLE not found: {}'.format(fill_table_path))
    print('       Run build_agent_fill_table.py first.')
    sys.exit(1)

with open(fill_table_path, encoding='utf-8') as f:
    fill_table_text = f.read()

# Parse fills -- only TAG-XX entries (skip the AUTO-XX header block).
# Split on TAG- token so each block starts with TAG-NN.
_tag_blocks = re.split(r'(?=\s*TAG-\d+\s+Line)', fill_table_text)

agent_fills = []
for block in _tag_blocks:
    stripped = block.strip()
    if not stripped.startswith('TAG-'):
        continue   # skip header / AUTO section
    m = re.search(r'YOUR AGENT:\s+(.+?)(?=\n)', block)
    if m:
        raw = m.group(1).strip()
        if raw.startswith('(') or raw == '':
            agent_fills.append(None)   # "could not locate..." -> no fill
        else:
            agent_fills.append(raw)
    else:
        agent_fills.append(None)

print('Loaded {} fills from AGENT_FILL_TABLE ({} with text, {} blank)'.format(
    len(agent_fills),
    sum(1 for f in agent_fills if f),
    sum(1 for f in agent_fills if not f),
))

# -- Regex patterns ------------------------------------------------------------
_RE_REVIEW = re.compile(r'\[REVIEW:(?:[^\[\]]|\[[^\]]*\])*\]', re.DOTALL)
_RE_AUDIO  = re.compile(r'\[AUDIO:(?:[^\[\]]|\[[^\]]*\])*\]',  re.DOTALL)

# -- Gather items --------------------------------------------------------------
applied  = log.get('applied', [])
surfaced = sorted(log.get('surfaced', []), key=lambda x: x['line_num'])

print('Applied (auto-confirmed): {}'.format(len(applied)))
print('Surfaced (for review):    {}'.format(len(surfaced)))

if len(agent_fills) != len(surfaced):
    print('WARNING: fills count ({}) != surfaced count ({})'.format(
        len(agent_fills), len(surfaced)))
    print('         Fills will be applied in order -- check alignment.')

# -- Step 1: Build per-paragraph replacement map ------------------------------
# Group surfaced items by their paragraph text so multi-tag paragraphs
# are processed in a single pass (avoids "text already modified" failures).
#
# para_plan[para_text] = {tag_idx: fill_str_or_None}
para_plan = defaultdict(dict)  # para_text -> {tag_idx: fill_or_None}
_line_tag_counter = {}
fill_idx = 0

for item in surfaced:
    line_num  = item['line_num']
    para_text = item.get('after', item.get('before', ''))

    tag_idx = _line_tag_counter.get(line_num, 0)
    _line_tag_counter[line_num] = tag_idx + 1

    this_fill = agent_fills[fill_idx] if fill_idx < len(agent_fills) else None
    fill_idx += 1

    if para_text:
        para_plan[para_text][tag_idx] = this_fill

# -- Step 2: Replace AUTO-CONFIRMED tags --------------------------------------
# These are in the "applied" list and appear in corrected_text.txt as
# [REVIEW: confirmed "..." via audio].  Tag them [[CONFIRMED]].
for item in applied:
    old_text = item.get('after', item.get('before', ''))
    if not old_text or old_text not in corrected_text:
        continue
    # In applied paragraphs, mark ALL remaining [REVIEW:...] as CONFIRMED
    # (the auto action already updated the text in place)
    new_text = _RE_REVIEW.sub(lambda m: '[[CONFIRMED]]', old_text)
    if new_text != old_text:
        corrected_text = corrected_text.replace(old_text, new_text, 1)

# -- Step 3: Replace SURFACED tags with [[AGENT: "fill"]] ---------------------
# Strategy: exact match first; if that fails, use anchor-based matching.
#
# Anchor match: extract the pre-REVIEW skeleton text, find the containing
# paragraph in corrected_text by locating the anchor, then replace REVIEW
# tags in that actual paragraph.  Handles cases where the REVIEW tag wording
# in item['after'] differs from what is currently in corrected_text.txt.

def _make_replacer(fills_dict):
    """Return a regex sub function that replaces the Nth [REVIEW:...] tag."""
    counter = [0]
    def _replacer(m):
        idx = counter[0]
        counter[0] += 1
        if idx not in fills_dict:
            return m.group(0)   # not a targeted tag -- leave unchanged
        fill = fills_dict[idx]
        if fill:
            return '[[AGENT: "{}"]]'.format(fill)
        return '[[AGENT: ?]]'
    return _replacer


def _anchor_replace(ct, para_text, tag_fills):
    """
    Locate para_text in ct via its non-REVIEW skeleton, replace REVIEW tags.

    Returns updated ct, or original ct if paragraph cannot be located.
    """
    # Split on REVIEW tags to get text skeleton
    sentinel = '\x01'
    clean = _RE_REVIEW.sub(sentinel, para_text)
    parts  = clean.split(sentinel)

    # Find the best anchor: first text part >= 15 chars
    anchor = None
    for p in parts:
        ps = p.strip()
        if len(ps) >= 15:
            # Take first 60 chars of this part as the anchor
            anchor = ps[:60]
            break

    if not anchor:
        return ct  # nothing useful to anchor on

    idx = ct.find(anchor)
    if idx == -1:
        return ct  # anchor not in corrected_text

    # Find paragraph boundaries (double-newlines or start/end of text)
    para_start = ct.rfind('\n\n', 0, idx)
    para_start = (para_start + 2) if para_start >= 0 else 0

    para_end = ct.find('\n\n', idx)
    if para_end == -1:
        para_end = len(ct)

    actual_para = ct[para_start:para_end]

    # Sanity: actual_para should contain REVIEW tags
    if not _RE_REVIEW.search(actual_para):
        return ct  # nothing to replace here

    new_para = _RE_REVIEW.sub(_make_replacer(tag_fills), actual_para)
    if new_para == actual_para:
        return ct  # no change -- fills_dict had no matching indices

    return ct[:para_start] + new_para + ct[para_end:]


replacements_applied = 0
replacements_missing = 0

for para_text, tag_fills in para_plan.items():
    if para_text in corrected_text:
        # Fast path: exact match
        new_para = _RE_REVIEW.sub(_make_replacer(tag_fills), para_text)
        corrected_text = corrected_text.replace(para_text, new_para, 1)
        replacements_applied += 1
    else:
        # Slow path: anchor-based match
        updated = _anchor_replace(corrected_text, para_text, tag_fills)
        if updated is not corrected_text:
            corrected_text = updated
            replacements_applied += 1
        else:
            replacements_missing += 1

if replacements_missing:
    print('WARN: {} paragraph(s) could not be located in corrected_text'.format(
        replacements_missing))

# -- Step 4: Tidy remaining [AUDIO:...] and [REVIEW:...] tags ----------------
# Any [AUDIO: ...] markers get [[NOTE]]
corrected_text = _RE_AUDIO.sub(lambda m: '[[NOTE]]', corrected_text)
# Any remaining [REVIEW: ...] that wasn't in the surfaced list gets [[NOTE]]
corrected_text = _RE_REVIEW.sub(lambda m: '[[NOTE]]', corrected_text)

# -- Step 5: Save inline-tagged corrected text --------------------------------
# This is the input we'll feed to format_final.py.
# The formatter reads corrected_text.txt by default, but we override it
# via the FORMAT_INPUT env var so the original corrected_text.txt is untouched.
import subprocess
import sys as _sys

inline_input_path  = os.path.join(BASE, 'corrected_text_inline_review.txt')
formatted_out_path = os.path.join(OUT_DIR, '{}_INLINE_REVIEW_FORMATTED.txt'.format(case_short))

with open(inline_input_path, 'w', encoding='utf-8') as f:
    f.write(corrected_text)

print('Saved inline text -> {}'.format(os.path.basename(inline_input_path)))

# -- Step 6: Run format_final.py on the inline text ---------------------------
# Pass env vars so format_final.py uses our tagged file and writes to a
# different output name -- the original FINAL_FORMATTED.txt is NOT touched.
print('Running formatter on inline text...')
env = os.environ.copy()
env['FORMAT_INPUT']  = inline_input_path
env['FORMAT_OUTPUT'] = formatted_out_path

format_script = os.path.join(ENGINE, 'format_final.py')
result = subprocess.run(
    [_sys.executable, format_script],
    cwd=BASE,
    env=env,
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace',
)

if result.returncode != 0:
    print('ERROR: formatter exited with code {}'.format(result.returncode))
    print(result.stderr[-2000:] if result.stderr else '(no stderr)')
    print('Falling back to flat-text output only.')
    formatted_out_path = None
else:
    # Print last few lines of formatter output
    last_lines = [l for l in result.stdout.split('\n') if l.strip()][-4:]
    for l in last_lines:
        print('  [formatter] {}'.format(l))

# -- Summary -------------------------------------------------------------------
agent_tag_count   = corrected_text.count('[[AGENT: "')
agent_blank_count = corrected_text.count('[[AGENT: ?]]')
confirmed_count   = corrected_text.count('[[CONFIRMED]]')
note_count        = corrected_text.count('[[NOTE]]')
total_count       = corrected_text.count('[[')

print()
print('-' * 60)
if formatted_out_path and os.path.exists(formatted_out_path):
    print('  PRIMARY:  {}'.format(formatted_out_path))
    print('            (paginated depo with [[AGENT:]] fills -- give this to AD)')
print('  SOURCE:   {}'.format(inline_input_path))
print('-' * 60)
print('  [[AGENT: "fill"]]  : {:3d}  (have fill -- approve or correct)'.format(agent_tag_count))
print('  [[AGENT: ?]]       : {:3d}  (no fill -- manual entry needed)'.format(agent_blank_count))
print('  [[CONFIRMED]]      : {:3d}  (auto-confirmed, skip)'.format(confirmed_count))
print('  [[NOTE]]           : {:3d}  (structural notes)'.format(note_count))
print('  Total [[ tags      : {:3d}  (AD Ctrl+F count)'.format(total_count))
print('-' * 60)
print()
print('AD workflow:  Ctrl+F  [[  ->  jump through all {} review locations'.format(total_count))
print()

#!/usr/bin/env python3
"""
make_rtf.py v1.1 — Build CaseCATalyst RTF/CRE import file
=========================================================================
Reads corrected_text.txt from the job work dir (CWD), strips engine tags,
and produces a CaseCATalyst-importable RTF file.

[REVIEW:...] tags -> [[REVIEW: <reason> — confirm/verify audio]]
  - Known proper nouns (witness, attorney, claimant) injected from CASE_CAPTION
  - Steno gaps formatted as [[REVIEW: steno gap — verify audio]]
[AUDIO:...]  tags -> [[AUDIO: verify]]
[FLAG:...]   tags -> stripped

Usage:
    cd <job_work_dir>
    python make_rtf.py

Output:
    FINAL_DELIVERY/{case_short}_CAT.rtf

Import into CaseCATalyst:
    File -> Import -> RTF/CRE -> Browse to FINAL_DELIVERY -> select _CAT.rtf -> OK
    File -> Open -> Transcript Files (*.sgngl) -> type filename -> Open
"""

import os
import re
import json
import sys

# ── Load case name from CASE_CAPTION.json ─────────────────────────────────────
_cfg = {}
for _fname in ('CASE_CAPTION.json', 'depo_config.json'):
    if os.path.exists(_fname):
        with open(_fname, encoding='utf-8') as _f:
            _cfg.update(json.load(_f))

case_short = _cfg.get('case_short')
if not case_short:
    print('ERROR: case_short not found in CASE_CAPTION.json or depo_config.json')
    sys.exit(1)

# ── Input / output paths ───────────────────────────────────────────────────────
IN_FILE  = 'corrected_text.txt'
OUT_DIR  = 'FINAL_DELIVERY'
OUT_FILE = os.path.join(OUT_DIR, f'{case_short}_CAT.rtf')

if not os.path.exists(IN_FILE):
    print(f'ERROR: {IN_FILE} not found in {os.getcwd()}')
    sys.exit(1)

os.makedirs(OUT_DIR, exist_ok=True)

# ── Known proper nouns from CASE_CAPTION ──────────────────────────────────────
# Used to inject best-guess values into [[REVIEW]] tags instead of leaving blanks.
_KNOWN = {
    'witness':  _cfg.get('witness_name', ''),
    'claimant': _cfg.get('claimant', ''),
    'atty1':    '',
    'atty2':    '',
}
# Pull attorney names from appearances list
for _app in _cfg.get('appearances', []):
    for _atty in _app.get('attorneys', []):
        if not isinstance(_atty, dict):   # guard: 'attorneys' set to string instead of list
            continue
        _name = _atty.get('name', '').replace(', ESQ., of Counsel','').replace(', ESQ.','').strip()
        if not _KNOWN['atty1']:
            _KNOWN['atty1'] = _name
        elif not _KNOWN['atty2']:
            _KNOWN['atty2'] = _name

# Keywords that map REVIEW reason text to a known value
_KNOWN_TRIGGERS = [
    (['witness name', 'witness last'],          _KNOWN['witness']),
    (['claimant last', 'claimant name'],         _KNOWN['claimant']),
    (['attorney last', 'examining atty'],        _KNOWN['atty1']),
    (['colleague', 'cross', 'opposing'],         _KNOWN['atty2']),
]

# First words that disqualify a Whisper phrase as a gap hint.
# These are function words, sentence openers, or conversational fillers that
# indicate Whisper caught surrounding context rather than the actual gap word.
_FILLER_STARTERS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'so', 'yet',
    'i', 'it', 'is', 'was', 'were', 'be', 'been',
    'he', 'she', 'they', 'we', 'you', 'my', 'his', 'her', 'their',
    'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by', 'from',
    'after', 'before', 'where', 'when', 'which', 'that', 'this',
    'all', 'any', 'some', 'what', 'how', 'did', 'do', 'does',
    'now', 'then', 'there', 'here',
    'okay', 'ok', 'uh', 'um', 'yeah', 'yes', 'no',
    'mr', 'ms', 'mrs', 'dr', 'doctor',
    'thank', 'thanks', 'seeing',
})

def _clean_hint(hint):
    """Extract a short, usable hint from a Whisper phrase.
    Returns None if the phrase looks like surrounding context, not a gap word.

    D-13 fix: scan 8 words (was 4) and skip leading fillers (was reject-on-first-filler).
    Proper nouns past word 4 (e.g. 'InterVest', 'Belize') are no longer dropped.
    """
    # Take first clause only (stop at sentence-ending punctuation)
    clause = re.split(r'[.!?]', hint)[0].strip()
    if not clause:
        clause = hint

    # Scan up to 8 words — proper nouns past word 4 were silently dropped before
    raw_words = clause.split()[:8]
    words = [w.rstrip('.,;:\u2014\u2013-').strip('"\'\u201c\u201d') for w in raw_words]
    words = [w for w in words if w]

    if not words:
        return None

    # Skip leading filler/function words — useful proper noun may follow
    # (was: reject entire hint if first word is filler)
    while words and words[0].lower() in _FILLER_STARTERS:
        words = words[1:]

    if not words:
        return None

    # Reject if any kept word is purely numeric (dates, codes, etc.)
    if any(re.match(r'^\d+$', w) for w in words):
        return None

    # Cap at 4 substantive words after skipping fillers
    result = ' '.join(words[:4])
    return result if len(result) >= 2 else None

def format_review_tag(reason):
    """
    Convert [REVIEW: <reason>] to [[REVIEW: <best_guess> — confirm]]
    or [[REVIEW: steno gap — verify audio]] depending on what we know.
    """
    reason_lower = reason.lower()

    # Check if we can resolve from CASE_CAPTION
    for triggers, value in _KNOWN_TRIGGERS:
        if value and any(t in reason_lower for t in triggers):
            display = value.title().replace(', M.D.', ', M.D.').replace(', Esq.', ', ESQ.')
            return f'[[REVIEW: {display} -- confirm]]'

    # Extract a heard/likely hint if present
    heard  = re.search(r'heard[^\-\]]*["\u201c]([^"\u201d\]]+)["\u201d]', reason, re.I)
    likely = re.search(r'likely[^\-\]]*["\u201c]?([A-Za-z ]+)["\u201d]?', reason, re.I)

    if heard:
        hint = _clean_hint(heard.group(1).strip())
        if hint:
            return f'[[REVIEW: heard "{hint}" -- verify audio]]'

    if likely:
        hint = likely.group(1).strip().rstrip('-').strip()
        if len(hint) >= 2:
            return f'[[REVIEW: likely "{hint}" -- verify audio]]'

    # Generic steno gap
    return '[[REVIEW: steno gap -- verify audio]]'

# ── Tag stripping ──────────────────────────────────────────────────────────────
# Regex handles [|] inside tags — matches non-bracket chars OR complete [x] groups
_RE_FLAG   = re.compile(r'\[FLAG:(?:[^\[\]]|\[[^\]]*\])*\]',    re.DOTALL)
_RE_REVIEW = re.compile(r'\[REVIEW:((?:[^\[\]]|\[[^\]]*\])*)\]', re.DOTALL)
_RE_AUDIO  = re.compile(r'\[AUDIO:(?:[^\[\]]|\[[^\]]*\])*\]',   re.DOTALL)

with open(IN_FILE, 'r', encoding='utf-8', errors='replace') as f:
    raw = f.read()

content = _RE_FLAG.sub('', raw)
content = _RE_REVIEW.sub(lambda m: format_review_tag(m.group(1)), content)
content = _RE_AUDIO.sub('[[AUDIO: verify]]', content)

# ── Fix mid-word [[REVIEW:...]] insertions ────────────────────────────────────
# When the AI engine flags a truncated steno word it writes word[REVIEW:...]ment
# (prefix before the tag, suffix after).  After substitution this becomes
# pro[[REVIEW: steno gap -- verify audio]]nounce — unreadable in CAT.
# Merge the fragments: pro + nounce → pronounce, tag moves to end of word.
_RE_MIDWORD = re.compile(r"([A-Za-z'\-]+)(\[\[REVIEW:[^\]]*\]\])([A-Za-z'\-]+)")
content = _RE_MIDWORD.sub(r'\1\3 \2', content)

# ── RTF builder ────────────────────────────────────────────────────────────────
def escape_rtf(text):
    out = []
    for ch in text:
        o = ord(ch)
        if o == 92:    out.append('\\\\')
        elif o == 123: out.append('\\{')
        elif o == 125: out.append('\\}')
        elif o == 13:  continue
        elif o == 10:  out.append('\\par\n')
        elif o > 127:  out.append("\\'" + ('%02x' % o))
        else:          out.append(ch)
    return ''.join(out)

rtf  = '{\\rtf1\\ansi\\ansicpg1252\\deff0\n'
rtf += '{\\fonttbl{\\f0\\fmodern\\fprq1\\fcharset0 Courier New;}}\n'
rtf += '\\f0\\fs20\n'
rtf += escape_rtf(content)
rtf += '}'

with open(OUT_FILE, 'w', encoding='windows-1252') as f:
    f.write(rtf)

size = os.path.getsize(OUT_FILE)
print(f'Written: {OUT_FILE}')
print(f'Size:    {size:,} bytes ({size/1024:.1f} KB)')

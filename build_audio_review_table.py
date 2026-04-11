"""
build_audio_review_table.py — Audio Review Table for CR walk-through
=====================================================================
Reads audio_apply_log.json + corrected_text.txt + audio_transcript.txt.
Outputs a plain-text table of all audio-flagged items for the CR to review.

For each flagged item:
  - Numbered tag (TAG-01, TAG-02, ...)
  - Line # in corrected_text.txt
  - Context: surrounding lines with [REVIEW] tags shown as [___]
  - Gap note: what the engine flagged
  - AGENT: what our agent fill cascade heard  (v4: full 7-level cascade)
  - VERDICT: blank line for CR to fill in

v2 change: AUDIO line now shows agent fill (7-level cascade) not raw Whisper.
           Falls back to raw whisper_text if transcript not available.

Output: FINAL_DELIVERY/{case_short}_AUDIO_REVIEW_TABLE.txt

Usage:
    cd /path/to/job/work/
    python path/to/engine/build_audio_review_table.py

Author:  Scott + Claude
Version: 2.0  (2026-04-10)
"""

import os
import sys
import json
import re
from datetime import date

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.getcwd()

# ── Paths ─────────────────────────────────────────────────────────────────────
LOG_PATH        = os.path.join(BASE, 'audio_apply_log.json')
CORRECTED_PATH  = os.path.join(BASE, 'corrected_text.txt')
CAPTION_PATH    = os.path.join(BASE, 'CASE_CAPTION.json')
TRANSCRIPT_PATH = os.path.join(BASE, 'audio_transcript.txt')
OUT_DIR         = os.path.join(BASE, 'FINAL_DELIVERY')

# ── Validate required inputs ──────────────────────────────────────────────────
for path, label in [(LOG_PATH,       'audio_apply_log.json'),
                    (CORRECTED_PATH, 'corrected_text.txt'),
                    (CAPTION_PATH,   'CASE_CAPTION.json')]:
    if not os.path.exists(path):
        print(f'ERROR: {label} not found at {path}')
        print('  Run apply_audio_validation.py first.')
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

# ── Load transcript (optional — enables agent fill cascade) ───────────────────
_transcript_ready = False
transcript_full = transcript_norm = transcript_pnorm = ''

if os.path.exists(TRANSCRIPT_PATH):
    with open(TRANSCRIPT_PATH, encoding='utf-8') as f:
        _tlines = [ln.rstrip('\n') for ln in f]
    transcript_full  = ' '.join(_tlines)
    transcript_norm  = re.sub(r'\s+', ' ', transcript_full.lower()).strip()
    transcript_pnorm = re.sub(r'[^\w\s]', ' ', transcript_full)
    transcript_pnorm = re.sub(r'\s+', ' ', transcript_pnorm.lower()).strip()
    _transcript_ready = True

# ── Collect items ─────────────────────────────────────────────────────────────
applied         = log.get('applied', [])
surfaced        = log.get('surfaced', [])
surfaced_sorted = sorted(surfaced, key=lambda x: x['line_num'])

# ── Layout ────────────────────────────────────────────────────────────────────
W      = 70
SEP    = '─' * W
DBLSEP = '═' * W

# ── Regex ─────────────────────────────────────────────────────────────────────
_RE_REVIEW = re.compile(r'\[REVIEW:(?:[^\[\]]|\[[^\]]*\])*\]', re.DOTALL)

# ── Stop words ────────────────────────────────────────────────────────────────
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'is', 'was', 'are', 'were', 'be', 'been', 'have',
    'has', 'had', 'do', 'did', 'does', 'that', 'this', 'it', 'he', 'she',
    'they', 'we', 'you', 'my', 'his', 'her', 'their', 'its', 'our',
    'not', 'no', 'so', 'as', 'if', 'up', 'out', 'then', 'than', 'when',
    'what', 'who', 'how', 'all', 'any', 'can', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'from', 'into', 'through', 'about',
    'just', 'also', 'very', 'well', 'back', 'there', 'here', 'now', 'said',
    'yes', 'see', 'one', 'two', 'its', 'per',
}

# ─────────────────────────────────────────────────────────────────────────────
# FILL CASCADE — identical logic to build_agent_fill_table.py v4
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s):
    return re.sub(r'\s+', ' ', s.lower().strip())

def _word_clean(w):
    return re.sub(r'[^a-z]', '', w.lower())

def strip_review_tags(text):
    return _RE_REVIEW.sub('[___]', text)

def get_context_split(tagged_text, tag_index=0):
    sentinel = '\x00'
    clean = _RE_REVIEW.sub(sentinel, tagged_text)
    parts = clean.split(sentinel)
    if tag_index >= len(parts) - 1:
        tag_index = 0
    before_text = _norm(' '.join(parts[:tag_index + 1]))
    after_text  = _norm(' '.join(parts[tag_index + 1:])) if tag_index + 1 < len(parts) else ''
    before_text = _RE_REVIEW.sub('', before_text).strip()
    after_text  = _RE_REVIEW.sub('', after_text).strip()
    return before_text, after_text

def build_candidates(before_text, after_text, max_left_words=20):
    right_bookend = None
    for w in after_text.split():
        clean = _word_clean(w)
        if len(clean) > 3 and clean not in STOP_WORDS:
            right_bookend = clean
            break
    before_words = before_text.split()
    candidates, seen = [], set()
    for n in range(min(max_left_words, len(before_words)), 0, -1):
        phrase_words = list(before_words[-n:])
        while phrase_words and len(_word_clean(phrase_words[-1])) <= 3:
            phrase_words.pop()
        if not phrase_words:
            continue
        phrase = ' '.join(phrase_words)
        if len(phrase) < 4 or phrase in seen:
            continue
        seen.add(phrase)
        candidates.append((phrase, right_bookend))
    for skip in (1, 2):
        temp = list(before_words)
        dropped = 0
        while temp and dropped < skip:
            if len(_word_clean(temp[-1])) > 3 and _word_clean(temp[-1]) not in STOP_WORDS:
                dropped += 1
            temp.pop()
        if len(temp) < 2:
            continue
        phrase_words = temp[-6:]
        while phrase_words and len(_word_clean(phrase_words[-1])) <= 3:
            phrase_words.pop()
        if not phrase_words:
            continue
        phrase = ' '.join(phrase_words)
        if len(phrase) < 4 or phrase in seen:
            continue
        seen.add(phrase)
        candidates.append((phrase, right_bookend))
    return candidates

def find_with_bookends(left_anchor, right_bookend, tag_pos, max_fill_words=6, window=0.25):
    if not left_anchor or len(left_anchor) < 4:
        return None, None, None
    tlen = len(transcript_norm)
    if tlen == 0:
        return None, None, None
    needle = re.sub(r'\s*[-\u2013\u2014]+\s*', ' ', left_anchor)
    needle = re.sub(r'\s+', ' ', needle.lower()).strip()
    all_hits, use_pnorm = [], False
    start = 0
    while True:
        idx = transcript_norm.find(needle, start)
        if idx == -1: break
        all_hits.append((idx, idx / tlen))
        start = idx + 1
    if not all_hits:
        needle_np = re.sub(r'[^\w\s]', ' ', needle)
        needle_np = re.sub(r'\s+', ' ', needle_np).strip()
        if needle_np:
            plen = len(transcript_pnorm)
            start = 0
            while True:
                idx = transcript_pnorm.find(needle_np, start)
                if idx == -1: break
                all_hits.append((idx, idx / plen if plen else 0.0))
                start = idx + 1
            if all_hits:
                use_pnorm = True
    if not all_hits:
        return None, None, None
    all_hits.sort(key=lambda h: abs(h[1] - tag_pos))
    best = next((h for h in all_hits if abs(h[1] - tag_pos) <= window), None)
    if best is None:
        return None, None, None
    best_idx = best[0]
    in_window_count = sum(1 for _, hp in all_hits if abs(hp - tag_pos) <= window)
    work_t   = transcript_pnorm if use_pnorm else transcript_full
    ref_norm = transcript_pnorm if use_pnorm else transcript_norm
    needle_used = (re.sub(r'[^\w\s]', ' ', needle) if use_pnorm else needle)
    needle_used = re.sub(r'\s+', ' ', needle_used).strip()
    fill_start = best_idx + len(needle_used)
    if fill_start < len(ref_norm) and ref_norm[fill_start] not in ' \t\n':
        while fill_start > 0 and ref_norm[fill_start] not in ' \t\n':
            fill_start -= 1
    while fill_start < len(work_t) and work_t[fill_start] in ' \t\n':
        fill_start += 1
    fill_words_raw = work_t[fill_start:fill_start + 300].split()
    trimmed, found_bookend = [], False
    for w in fill_words_raw:
        wc = _word_clean(w)
        if right_bookend and len(right_bookend) > 3:
            if wc == right_bookend or (len(right_bookend) >= 5 and wc.startswith(right_bookend[:5])):
                found_bookend = True
                break
        trimmed.append(w)
        if len(trimmed) >= max_fill_words:
            break
    fill = ' '.join(trimmed).strip(' .,;:\u2014-')
    if not fill:
        return None, None, None
    if found_bookend and in_window_count == 1:   conf = 'HIGH'
    elif found_bookend or in_window_count == 1:  conf = 'MED'
    else:                                         conf = 'LOW'
    return fill, conf, best_idx

def find_with_right_anchor(after_text, tag_pos, max_right_words=8, max_fill_words=6, window=0.25):
    if not after_text:
        return None, None, None
    after_words = after_text.split()
    seen = set()
    for skip_start in (0, 1, 2):
        words_slice = after_words[skip_start:]
        if len(words_slice) < 2:
            continue
        for n in range(min(max_right_words, len(words_slice)), 1, -1):
            phrase_words = list(words_slice[:n])
            while phrase_words and len(_word_clean(phrase_words[0])) < 3:
                phrase_words.pop(0)
            if not phrase_words:
                continue
            phrase = ' '.join(phrase_words)
            if len(phrase) < 4 or phrase in seen:
                continue
            seen.add(phrase)
            needle = re.sub(r'\s*[-\u2013\u2014]+\s*', ' ', phrase.lower())
            needle = re.sub(r'\s+', ' ', needle).strip()
            all_hits = []
            for search_t in (transcript_norm, transcript_pnorm):
                ns = needle if search_t is transcript_norm else re.sub(r'[^\w\s]', ' ', needle)
                ns = re.sub(r'\s+', ' ', ns).strip()
                start = 0
                while True:
                    idx = search_t.find(ns, start)
                    if idx == -1: break
                    all_hits.append((idx, idx / len(search_t) if len(search_t) else 0.0, search_t))
                    start = idx + 1
                if all_hits:
                    break
            if not all_hits:
                continue
            all_hits.sort(key=lambda h: abs(h[1] - tag_pos))
            best = next((h for h in all_hits if abs(h[1] - tag_pos) <= window), None)
            if best is None:
                continue
            best_idx, _, best_t = best
            pre_words = best_t[max(0, best_idx - 200):best_idx].split()
            fill = ' '.join(pre_words[-max_fill_words:]).strip(' .,;:\u2014-')
            if not fill:
                continue
            in_window = sum(1 for h in all_hits if abs(h[1] - tag_pos) <= window)
            conf = 'HIGH' if in_window == 1 else 'MED'
            return fill, conf, best_idx
    return None, None, None

def find_forward_sequential(before_ctx, after_ctx, min_idx, tag_pos, max_fill_words=6, window=0.25):
    if min_idx <= 0:
        return None, None, None
    tlen_n = len(transcript_norm)
    tlen_p = len(transcript_pnorm)

    def _try_left(needle):
        n = re.sub(r'\s*[-\u2013\u2014]+\s*', ' ', needle.lower())
        n = re.sub(r'\s+', ' ', n).strip()
        if len(n) < 3: return None, None, None
        for sfn, tlen, wt in ((transcript_norm, tlen_n, transcript_full),
                               (transcript_pnorm, tlen_p, transcript_pnorm)):
            np_ = re.sub(r'[^\w\s]', ' ', n) if sfn is transcript_pnorm else n
            np_ = re.sub(r'\s+', ' ', np_).strip()
            idx = sfn.find(np_, min_idx)
            if idx == -1: continue
            fs = idx + len(np_)
            if fs < len(sfn) and sfn[fs] not in ' \t\n':
                while fs > 0 and sfn[fs] not in ' \t\n': fs -= 1
            while fs < len(wt) and wt[fs] in ' \t\n': fs += 1
            fill = ' '.join(wt[fs:fs+200].split()[:max_fill_words]).strip(' .,;:\u2014-')
            if fill: return fill, 'LOW', idx
        return None, None, None

    def _try_right(needle):
        n = re.sub(r'\s*[-\u2013\u2014]+\s*', ' ', needle.lower())
        n = re.sub(r'\s+', ' ', n).strip()
        if len(n) < 3: return None, None, None
        for sfn, tlen in ((transcript_norm, tlen_n), (transcript_pnorm, tlen_p)):
            np_ = re.sub(r'[^\w\s]', ' ', n) if sfn is transcript_pnorm else n
            np_ = re.sub(r'\s+', ' ', np_).strip()
            idx = sfn.find(np_, min_idx)
            if idx == -1: continue
            fill = ' '.join(sfn[max(0, idx-200):idx].split()[-max_fill_words:]).strip(' .,;:\u2014-')
            if fill: return fill, 'LOW', idx
        return None, None, None

    seen = set()
    if before_ctx:
        bw = before_ctx.split()
        for i in range(len(bw) - 1):
            p = ' '.join(bw[i:i+2]).lower()
            if p not in seen:
                seen.add(p)
                f, c, fi = _try_left(p)
                if f: return f, c, fi
        for w in reversed(bw):
            wc = _word_clean(w)
            if len(wc) >= 3 and wc not in STOP_WORDS and wc not in seen:
                seen.add(wc)
                f, c, fi = _try_left(wc)
                if f: return f, c, fi
    if after_ctx:
        aw = after_ctx.split()
        for i in range(len(aw) - 1):
            p = ' '.join(aw[i:i+2]).lower()
            if p not in seen:
                seen.add(p)
                f, c, fi = _try_right(p)
                if f: return f, c, fi
        for i in range(len(aw) - 2):
            w1  = _word_clean(aw[i])
            mid = _word_clean(aw[i+1])
            w2  = _word_clean(aw[i+2])
            if (len(w1) >= 3 and w1 not in STOP_WORDS and
                    (len(mid) <= 2 or mid in STOP_WORDS) and
                    len(w2) >= 3 and w2 not in STOP_WORDS):
                p = f'{w1} {w2}'
                if p not in seen:
                    seen.add(p)
                    f, c, fi = _try_right(p)
                    if f: return f, c, fi
        for w in aw:
            wc = _word_clean(w)
            if len(wc) >= 3 and wc not in STOP_WORDS and wc not in seen:
                seen.add(wc)
                f, c, fi = _try_right(wc)
                if f: return f, c, fi
    return None, None, None

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def context_lines(line_num, n_before=1, n_after=1):
    """Return context lines around line_num (1-based). Strips [REVIEW] tags."""
    idx   = line_num - 1
    start = max(0, idx - n_before)
    end   = min(len(corrected_lines) - 1, idx + n_after)
    result = []
    for i in range(start, end + 1):
        raw     = corrected_lines[i].strip()
        if not raw:
            continue
        cleaned = strip_review_tags(raw)
        marker  = '>>>' if i == idx else '   '
        prefix  = f'  {marker} '
        wrap_w  = W - len(prefix)
        words   = cleaned.split()
        line_buf = ''
        for word in words:
            if line_buf and len(line_buf) + 1 + len(word) > wrap_w:
                result.append(f'{prefix}{line_buf}')
                prefix   = '       '
                line_buf = word
            else:
                line_buf = (line_buf + ' ' + word).strip()
        if line_buf:
            result.append(f'{prefix}{line_buf}')
    return result

def wrap_text(text, width=64, indent='         '):
    words = text.split()
    lines, current = [], ''
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + ' ' + word).strip()
    if current:
        lines.append(current)
    return ('\n' + indent).join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# BUILD OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, f'{case_short}_AUDIO_REVIEW_TABLE.txt')

_total_source_lines = max((item['line_num'] for item in surfaced_sorted), default=1)
_line_tag_counter   = {}
last_found_idx      = 0

lines_out = []

def emit(s=''):
    lines_out.append(s)

# ── Header ────────────────────────────────────────────────────────────────────
fill_source = 'agent fill cascade v4' if _transcript_ready else 'raw Whisper (no transcript found)'
emit(DBLSEP)
emit(f'  {case_short.upper()} — AUDIO REVIEW TABLE')
emit(f'  Witness:   {witness}')
emit(f'  Depo date: {depo_date}')
emit(f'  Reporter:  {cr_name}')
emit(f'  Generated: {date.today().strftime("%B %d, %Y")}')
emit(f'  Fill source: {fill_source}')
emit(DBLSEP)
emit()
emit('  HOW TO USE THIS FILE')
emit('  ─────────────────────────────────────────────────────────')
emit('  Your agent listened to the same audio you recorded.')
emit('  For each gap below:')
emit('    • Read the CONTEXT line (your steno with [___] gaps)')
emit('    • Check the AGENT line — that is what was said')
emit('    • VERDICT: leave blank to accept, or write your correction')
emit()
emit(f'  {len(applied)} auto-confirmed  |  {len(surfaced_sorted)} for your review')
emit()

# ── AUTO-confirmed ────────────────────────────────────────────────────────────
if applied:
    emit(SEP)
    emit(f'  AUTO-CONFIRMED  ({len(applied)} — no action needed)')
    emit(SEP)
    emit()
    for n, item in enumerate(applied, 1):
        emit(f'  AUTO-{n:02d}  Line {item["line_num"]}  [score: {item["match_score"]}]')
        for ctx_line in context_lines(item['line_num']):
            emit(ctx_line)
        emit(f'  GAP:     {item["note"][:70]}')
        emit(f'  AGENT:   "{item["whisper_text"][:65]}"')
        emit(f'  ACTION:  Applied automatically ✓')
        emit()

# ── Surfaced items ─────────────────────────────────────────────────────────────
emit(DBLSEP)
emit(f'  FOR YOUR REVIEW  ({len(surfaced_sorted)} items)')
emit(DBLSEP)
emit()

filled_count = 0

for n, item in enumerate(surfaced_sorted, 1):
    line_num = item['line_num']
    action   = item['action']
    score    = item['match_score']
    note     = item.get('note', '')
    whisper  = item.get('whisper_text', '')
    tagged   = item.get('after', item.get('before', ''))

    tag_idx = _line_tag_counter.get(line_num, 0)
    _line_tag_counter[line_num] = tag_idx + 1
    tag_pos = line_num / _total_source_lines

    # ── Run fill cascade ─────────────────────────────────────────────────────
    agent_fill, conf, found_idx = None, None, None

    if _transcript_ready:
        before_ctx, after_ctx = get_context_split(tagged, tag_index=tag_idx)
        candidates = build_candidates(before_ctx, after_ctx)

        # Levels 1-4: bookend candidates
        for left_anchor, right_bookend in candidates:
            agent_fill, conf, found_idx = find_with_bookends(left_anchor, right_bookend, tag_pos)
            if agent_fill:
                break

        # Levels 5-6: right-side anchor
        if not agent_fill:
            agent_fill, conf, found_idx = find_with_right_anchor(after_ctx, tag_pos)

        # Level 7: sequential forward
        if not agent_fill:
            agent_fill, conf, found_idx = find_forward_sequential(
                before_ctx, after_ctx, last_found_idx, tag_pos
            )

        if found_idx is not None:
            last_found_idx = found_idx

    # Fall back to raw whisper_text if cascade found nothing
    display_fill = agent_fill or whisper or '(not found in audio)'
    conf_label   = f'[{conf}]' if conf else '[raw]' if (not agent_fill and whisper) else '[--]'

    if agent_fill:
        filled_count += 1

    # ── Format entry ──────────────────────────────────────────────────────────
    emit(SEP)
    emit(f'  TAG-{n:02d}  Line {line_num}')
    emit()
    for ctx_line in context_lines(line_num):
        emit(ctx_line)
    emit()
    emit(f'  AGENT {conf_label}:  {wrap_text(display_fill, width=60, indent="              ")}')
    emit()
    emit(f'  VERDICT:  ___________________________________________________')
    emit(f'            (leave blank to accept  |  write correction above)')
    emit()

# ── Footer ────────────────────────────────────────────────────────────────────
emit(DBLSEP)
emit(f'  SUMMARY')
emit(f'  Total for review:  {len(surfaced_sorted)}')
emit(f'  Agent filled:      {filled_count}  ({round(filled_count/len(surfaced_sorted)*100) if surfaced_sorted else 0}%)')
emit(f'  Review complete — sign and return to Scott.')
emit(DBLSEP)

# ── Write ──────────────────────────────────────────────────────────────────────
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines_out))

print(f'Audio review table written: {out_path}')
print(f'  Fill source:     {fill_source}')
print(f'  AUTO-confirmed:  {len(applied)}')
print(f'  For CR review:   {len(surfaced_sorted)}')
print(f'  Agent filled:    {filled_count}/{len(surfaced_sorted)}')

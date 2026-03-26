"""
build_mb_review.py
Generates MB_REVIEW.txt — a clean, readable correction report for MB's review.

Two sections:
  PART 1 — CHANGES MADE (HIGH confidence, auto-applied)
  PART 2 — YOUR CALL   (MEDIUM + LOW, need MB decision)
"""

import json
import os
import re

LOG_FILE    = 'correction_log.json'
OUTPUT_FILE = 'FINAL_DELIVERY/MB_REVIEW.txt'
MAX_REASON  = 180   # chars to show for reason before truncating


def fix_encoding(text):
    """Fix UTF-8 em dash stored as latin-1 artifact (â€" → —)."""
    if isinstance(text, str):
        try:
            return text.encode('latin-1').decode('utf-8')
        except Exception:
            return text
    return text


def short_reason(reason, max_len=MAX_REASON):
    """Trim reason to a readable length."""
    reason = fix_encoding(reason)
    # Strip leading [REVIEW: ...] tag for Part 2 — we surface that separately
    reason = re.sub(r'^\[REVIEW:[^\]]*\]\s*', '', reason).strip()
    if len(reason) > max_len:
        return reason[:max_len].rstrip() + '...'
    return reason


def confidence_label(conf):
    if conf == 'MEDIUM':
        return 'MEDIUM — verify before final'
    if conf == 'LOW':
        return 'LOW — reporter judgment required'
    return conf


def wrap(text, width=80, indent='       '):
    """Word-wrap a string to width, with indent on continuation lines."""
    text = str(text).replace('\n', ' ').strip()
    words = text.split()
    lines = []
    current = ''
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = (current + ' ' + word).strip()
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return ('\n' + indent).join(lines)


def build_report(corrections, meta):
    applied  = [c for c in corrections if c['confidence'] == 'HIGH']
    review   = [c for c in corrections if c['confidence'] in ('MEDIUM', 'LOW')]

    lines = []

    # ── Header ───────────────────────────────────────────────────────────────
    lines.append('=' * 80)
    lines.append('MB REVIEW REPORT')
    lines.append('AI Correction Pass — For Reporter Review Only — Not a Legal Document')
    lines.append('=' * 80)
    lines.append(f"Engine:   {fix_encoding(meta.get('engine', ''))}")
    lines.append(f"Input:    {fix_encoding(meta.get('input_file', ''))}")
    lines.append(f"Applied:  {len(applied)} changes (HIGH confidence — auto-applied)")
    lines.append(f"Review:   {len(review)} items (need your decision before final)")
    lines.append('')

    # ── Part 1 — Changes Made ────────────────────────────────────────────────
    lines.append('=' * 80)
    lines.append(f'PART 1 — CHANGES MADE  ({len(applied)} corrections auto-applied)')
    lines.append('Scan and flag anything that looks wrong. Otherwise these are done.')
    lines.append('=' * 80)
    lines.append('')

    for i, c in enumerate(applied, 1):
        orig = fix_encoding(c.get('original', '')).replace('\n', ' ↵ ')
        corr = fix_encoding(c.get('corrected', '')).replace('\n', ' ↵ ')
        reason = short_reason(c.get('reason', ''))
        line_num = c.get('line_approx', '?')

        lines.append(f"  #{i:<4}  LINE {line_num}")
        lines.append(f"       BEFORE:  {wrap(orig)}")
        lines.append(f"       AFTER:   {wrap(corr)}")
        lines.append(f"       WHY:     {wrap(reason)}")
        lines.append('')

    # ── Part 2 — Your Call ───────────────────────────────────────────────────
    lines.append('=' * 80)
    lines.append(f'PART 2 — YOUR CALL  ({len(review)} items need your decision)')
    lines.append('These were flagged but NOT applied. Your call on each before final delivery.')
    lines.append('=' * 80)
    lines.append('')

    for i, c in enumerate(review, 1):
        orig   = fix_encoding(c.get('original', '')).replace('\n', ' ↵ ')
        corr   = fix_encoding(c.get('corrected', '')).replace('\n', ' ↵ ')
        conf   = confidence_label(c.get('confidence', ''))
        reason = short_reason(c.get('reason', ''))
        line_num = c.get('line_approx', '?')

        lines.append(f"  #{i:<4}  LINE {line_num}   [{conf}]")
        lines.append(f"       ORIGINAL:  {wrap(orig)}")
        lines.append(f"       SUGGESTED: {wrap(corr)}")
        lines.append(f"       WHY:       {wrap(reason)}")
        lines.append('')

    # ── Footer ───────────────────────────────────────────────────────────────
    lines.append('=' * 80)
    lines.append('END OF REPORT')
    lines.append(f"Total corrections reviewed: {len(corrections)}")
    lines.append(f"  Applied (HIGH):  {len(applied)}")
    lines.append(f"  Your call:       {len(review)}")
    lines.append('=' * 80)

    return '\n'.join(lines)


def main():
    if not os.path.exists(LOG_FILE):
        print(f'[ERROR] {LOG_FILE} not found. Run ai_engine.py first.')
        return

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    corrections = data.get('corrections', [])
    meta = {k: v for k, v in data.items() if k != 'corrections'}

    print(f'Loaded {len(corrections)} corrections from {LOG_FILE}')

    report = build_report(corrections, meta)

    os.makedirs('FINAL_DELIVERY', exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)

    applied = sum(1 for c in corrections if c['confidence'] == 'HIGH')
    review  = sum(1 for c in corrections if c['confidence'] in ('MEDIUM', 'LOW'))

    print(f'Written: {OUTPUT_FILE}')
    print(f'  Part 1 — Changes made:  {applied}')
    print(f'  Part 2 — Your call:     {review}')
    char_count = len(report)
    print(f'  File size:              {char_count:,} chars  ({char_count // 1000}KB approx)')


if __name__ == '__main__':
    main()

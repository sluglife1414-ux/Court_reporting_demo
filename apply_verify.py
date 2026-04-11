"""
apply_verify.py — Pass 2 apply step.

Reads verify_log.json and re-tags DISAGREE items in corrected_text.txt
by appending a [REVIEW: ...] marker inline. This surfaces them as
reporter-review items in the final PDF — identical behavior to steno gaps.

Must run AFTER verify_agent.py and BEFORE format_final.py.

Usage:
    python apply_verify.py
    python apply_verify.py --verify verify_log.json --text corrected_text.txt
"""

import json
import os
import sys
import argparse

VERIFY_LOG    = 'verify_log.json'
CORRECTED_TXT = 'corrected_text.txt'
REVIEW_TAG    = '[REVIEW: verify-agent flag — reporter confirm this correction]'


def apply_disagree_tags(verify_log_path, corrected_path):
    # ── Load verify log ────────────────────────────────────────────────────────
    if not os.path.exists(verify_log_path):
        print(f'[SKIP] {verify_log_path} not found — no verify log to apply. Skipping.')
        sys.exit(0)
    if not os.path.exists(corrected_path):
        print(f'[ERROR] {corrected_path} not found.')
        sys.exit(1)

    with open(verify_log_path, encoding='utf-8') as f:
        vlog = json.load(f)

    results = vlog.get('results', [])
    disagreed = [r for r in results if r.get('verdict') == 'DISAGREE']

    print(f'\n{"="*60}')
    print(f'APPLY VERIFY — Tag DISAGREE items')
    print(f'{"="*60}')
    print(f'Total verify results:  {len(results)}')
    print(f'DISAGREE items to tag: {len(disagreed)}')

    if not disagreed:
        print('[OK] No DISAGREE items — corrected_text.txt unchanged.')
        print(f'{"="*60}\n')
        return

    # ── Load corrected text ────────────────────────────────────────────────────
    with open(corrected_path, encoding='utf-8') as f:
        text = f.read()

    tagged   = 0
    skipped  = 0
    modified = text

    for item in disagreed:
        corrected_str = item.get('corrected', '').strip()
        verify_note   = item.get('verify_note', '')
        line_approx   = item.get('line_approx', '?')

        if not corrected_str:
            skipped += 1
            continue

        # Build the inline [REVIEW] tag — include verify note if available
        if verify_note:
            tag = f'[REVIEW: verify-agent flag — {verify_note} — reporter confirm]'
        else:
            tag = REVIEW_TAG

        # Try exact match first
        if corrected_str in modified:
            # Replace first occurrence only (most conservative)
            modified = modified.replace(corrected_str, f'{corrected_str} {tag}', 1)
            tagged += 1
            print(f'  [TAGGED]  line~{line_approx}: {repr(corrected_str[:60])}')
        else:
            # Fallback: try case-insensitive match on first 40 chars
            search_key = corrected_str[:40].lower()
            lower_mod  = modified.lower()
            idx = lower_mod.find(search_key)
            if idx != -1:
                # Find end of this segment in original-case text
                end = idx + len(corrected_str)
                segment = modified[idx:end]
                modified = modified[:idx] + segment + ' ' + tag + modified[end:]
                tagged += 1
                print(f'  [TAGGED~] line~{line_approx}: {repr(corrected_str[:60])} (fuzzy match)')
            else:
                skipped += 1
                print(f'  [SKIP]    line~{line_approx}: {repr(corrected_str[:60])} — not found in text')

    # ── Save ───────────────────────────────────────────────────────────────────
    if tagged > 0:
        with open(corrected_path, 'w', encoding='utf-8') as f:
            f.write(modified)
        print(f'\nResult: {tagged} items tagged, {skipped} skipped')
        print(f'corrected_text.txt updated — DISAGREE items now carry [REVIEW] flags.')
    else:
        print(f'\nResult: 0 items tagged ({skipped} skipped — no matches found in text)')

    print(f'{"="*60}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Apply verify-agent DISAGREE tags to corrected_text.txt')
    parser.add_argument('--verify', default=VERIFY_LOG,    help=f'Path to verify_log.json (default: {VERIFY_LOG})')
    parser.add_argument('--text',   default=CORRECTED_TXT, help=f'Path to corrected_text.txt (default: {CORRECTED_TXT})')
    args = parser.parse_args()
    apply_disagree_tags(args.verify, args.text)

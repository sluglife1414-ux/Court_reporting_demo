"""
acceptance_test.py — Output quality acceptance tests for MB engine.

Runs pattern-based checks against the formatted output file and reports
pass/fail per defect. Run this between every fix to verify the defect
count drops to zero and no regressions appear.

Usage:
    python acceptance_test.py                  # auto-find output in FINAL_DELIVERY/
    python acceptance_test.py path/to/out.txt  # explicit path

Exit code: 0 if all checks pass, 1 if any fail.
"""

import re
import sys
from pathlib import Path

# ── Locate output file ────────────────────────────────────────────────────────

def find_output():
    delivery = Path.cwd() / 'FINAL_DELIVERY'
    for pattern in ('*_FINAL_FORMATTED.txt', '*_FINAL_TRANSCRIPT.txt', '*_FINAL.txt'):
        candidates = list(delivery.glob(pattern))
        if candidates:
            return candidates[0]
    print('ERROR: No output file found in FINAL_DELIVERY/')
    sys.exit(1)

if len(sys.argv) == 2:
    out_path = Path(sys.argv[1])
else:
    out_path = find_output()

text = out_path.read_text(encoding='utf-8', errors='replace')
lines = text.splitlines()

print(f'File : {out_path.name}')
print(f'Lines: {len(lines):,}')
print()

# ── Check definitions ─────────────────────────────────────────────────────────
# Each check: (defect_id, description, regex_pattern, target_count)
# target_count = 0 means "must be zero to pass"
# target_count = None means "informational only — show count, no pass/fail"

CHECKS = [
    # DEF-011 — *REPORTER CHECK HERE* in output
    (
        'DEF-011',
        '*REPORTER CHECK HERE* in output',
        r'\*REPORTER CHECK HERE\*',
        0,
    ),

    # DEF-004 — empty [] brackets
    (
        'DEF-004a',
        'Empty [] brackets',
        r'\[\s*\]',
        0,
    ),

    # DEF-004 — [|] pipe bracket variants
    (
        'DEF-004b',
        '[|] / [||] / [||||] bracket variants',
        r'\[\|+\]',
        0,
    ),

    # DEF-004 — bare unclosed [ that are steno artifacts
    # Exclude legitimate uses: [sic], [REVIEW:, [[AGENT:
    (
        'DEF-004c',
        "Bare steno [ artifacts (not [sic] or tag openers)",
        r'\[(?!sic\b|\[?(?:REVIEW|AGENT|AUDIO|CONFIRMED|NOTE|CHANGED|SUGGEST|FLAG|CORRECTED):)',
        None,  # informational — legitimate brackets exist; review count manually
    ),

    # DEF-005 / DEF-012 — unmatched ]] closing tags (reasoning leaked through)
    (
        'DEF-012a',
        'Unmatched ]] closing tag (reasoning bleed)',
        r'(?<!\])\]\](?!\])',
        0,
    ),

    # DEF-012 / DEF-013 — "Verify audio" in output
    (
        'DEF-012b',
        '"Verify audio" in output (agent note bleed)',
        r'\bVerify\s+audio\b',
        0,
    ),

    # DEF-013 — "steno artifact" in output
    (
        'DEF-013a',
        '"steno artifact" in output (token analysis bleed)',
        r'\bsteno\s+artifact\b',
        0,
    ),

    # DEF-013 — "token N" numbering in output
    (
        'DEF-013b',
        '"token N" numbering in output (token analysis bleed)',
        r'\btoken\s+\d+',
        0,
    ),

    # DEF-005 — reasoning phrases in output
    (
        'DEF-005a',
        '"likely missing clause" / "dropped steno" reasoning phrases',
        r'(?:likely missing clause|dropped steno strokes|missing clause|dropped tokens)',
        0,
    ),

    (
        'DEF-005b',
        '"high confidence" / "low confidence" in output',
        r'\b(?:high|low)\s+confidence\b',
        0,
    ),

    # DEF-009 — double Q/A labels
    (
        'DEF-009a',
        'Double Q label (Q.Q. or Q. Q.)',
        r'Q\.\s*Q\.',
        0,
    ),

    (
        'DEF-009b',
        'Double A label (A.A. or A. A.)',
        r'A\.\s*A\.',
        0,
    ),

    # Page count — informational
    (
        'INFO-pages',
        'Approximate page count (target: ~357)',
        r'^\s{20,}\d{1,3}\s*$',   # right-justified page numbers
        None,
    ),
]

# ── Run checks ────────────────────────────────────────────────────────────────

W = 70
PASS  = 'PASS'
FAIL  = 'FAIL'
INFO  = 'INFO'

results = []
any_fail = False

for defect_id, description, pattern, target in CHECKS:
    matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
    count = len(matches)

    if target is None:
        status = INFO
    elif count <= target:
        status = PASS
    else:
        status = FAIL
        any_fail = True

    results.append((defect_id, description, count, target, status, matches))

# ── Print report ──────────────────────────────────────────────────────────────

print('=' * W)
print('  ACCEPTANCE TEST REPORT')
print(f'  {out_path.name}')
print('=' * W)
print()
print(f'  {"ID":<12} {"STATUS":<6} {"COUNT":>6}  {"TARGET":>6}  DESCRIPTION')
print(f'  {"-"*12} {"-"*6} {"-"*6}  {"-"*6}  {"-"*35}')

for defect_id, description, count, target, status, matches in results:
    target_str = str(target) if target is not None else '—'
    print(f'  {defect_id:<12} {status:<6} {count:>6}  {target_str:>6}  {description}')

print()

# Print sample hits for any FAILing check (first 3 matches)
for defect_id, description, count, target, status, matches in results:
    if status == FAIL and matches:
        print(f'  {defect_id} — first hits:')
        for m in matches[:3]:
            snippet = m.strip()[:80]
            print(f'    >>> {snippet}')
        if count > 3:
            print(f'    ... and {count - 3} more')
        print()

print('=' * W)
if any_fail:
    print(f'  RESULT: FAIL — {sum(1 for *_, s, _ in results if s == FAIL)} check(s) failing')
else:
    print('  RESULT: PASS — all checks clean')
print('=' * W)

sys.exit(1 if any_fail else 0)

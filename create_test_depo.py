"""
create_test_depo.py — Truncate the current depo for fast end-to-end pipeline testing.

Keeps ALL header sections intact (caption, index, appearances, stipulation).
Truncates only the testimony section so the AI engine runs fast.

Default: 30% of testimony → ~20 chunks → ~18 min AI run instead of 56 min.

USAGE:
    python create_test_depo.py              # 30% testimony (default)
    python create_test_depo.py --pct 40    # 40% testimony (~25 min)
    python create_test_depo.py --pct 20    # 20% testimony (~12 min)
    python create_test_depo.py --restore   # restore full depo

WORKFLOW:
    python create_test_depo.py             # creates test version
    python run_pipeline.py --from ai       # tip-to-tail from AI step (~18 min)
    # review all 10 delivery files
    python create_test_depo.py --restore   # restore full depo when ready
    python run_pipeline.py --from ai       # final full run
"""

import os
import sys
import argparse
import shutil

INPUT_FILE  = 'cleaned_text.txt'
BACKUP_FILE = 'cleaned_text_FULL.txt'

# Section markers (CaseCATalyst RTF standard — spaced letters)
TESTIMONY_START_MARKERS = ('S T I P U L A T I O N',)

# These lines (and everything after) are in the testimony section
TESTIMONY_CONTENT_TRIGGERS = (
    'THE VIDEOGRAPHER:',
    'THE COURT REPORTER:',
    'THE WITNESS:',
)


def find_testimony_start(lines):
    """
    Return the line index where testimony content begins.
    Strategy: find S T I P U L A T I O N, then find first actual speech line.
    Everything before that index = headers to keep intact.
    """
    in_stip = False
    for i, line in enumerate(lines):
        s = line.strip()
        if 'S T I P U L A T I O N' in s:
            in_stip = True
        if in_stip:
            for trigger in TESTIMONY_CONTENT_TRIGGERS:
                if s.startswith(trigger):
                    return i
    # Fallback: return 80% of file start (testimony likely started)
    return len(lines) * 8 // 10


def main():
    parser = argparse.ArgumentParser(description='Create truncated test depo')
    parser.add_argument('--pct', type=int, default=30,
                        help='Percent of testimony to keep (default: 30)')
    parser.add_argument('--restore', action='store_true',
                        help='Restore full cleaned_text.txt from backup')
    args = parser.parse_args()

    if args.restore:
        if not os.path.exists(BACKUP_FILE):
            print(f"[ERROR] No backup found at {BACKUP_FILE}")
            print("        Nothing to restore.")
            sys.exit(1)
        shutil.copy2(BACKUP_FILE, INPUT_FILE)
        full_lines = open(INPUT_FILE, encoding='utf-8').readlines()
        print(f"[RESTORE] Restored {INPUT_FILE} from backup.")
        print(f"          Full depo: {len(full_lines):,} lines")
        print()
        print("Next: python run_pipeline.py --from ai")
        return

    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] {INPUT_FILE} not found. Run steno_cleanup.py first.")
        sys.exit(1)

    with open(INPUT_FILE, encoding='utf-8') as f:
        lines = f.readlines()

    total_lines = len(lines)
    testimony_start = find_testimony_start(lines)
    header_lines    = lines[:testimony_start]
    testimony_lines = lines[testimony_start:]

    keep_n = max(100, int(len(testimony_lines) * args.pct / 100))
    test_testimony = testimony_lines[:keep_n]

    test_lines = header_lines + test_testimony

    # Backup original if not already backed up
    if not os.path.exists(BACKUP_FILE):
        shutil.copy2(INPUT_FILE, BACKUP_FILE)
        print(f"[BACKUP]  Full depo backed up -> {BACKUP_FILE}")
    else:
        print(f"[BACKUP]  Backup already exists ({BACKUP_FILE}) — skipping overwrite")

    # Write truncated version
    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(test_lines)

    # Stats
    full_chunks  = (total_lines + 104) // 105
    test_chunks  = (len(test_lines) + 104) // 105
    ai_min_full  = full_chunks * 53 // 60
    ai_min_test  = test_chunks * 53 // 60

    print()
    print("=" * 55)
    print("TEST DEPO CREATED")
    print("=" * 55)
    print(f"  Header lines kept:     {len(header_lines):>6,}  (all sections intact)")
    print(f"  Testimony kept:        {keep_n:>6,} / {len(testimony_lines):,} lines ({args.pct}%)")
    print(f"  Total test file:       {len(test_lines):>6,} lines  (was {total_lines:,})")
    print()
    print(f"  Est. AI chunks:        {test_chunks} of {full_chunks}  (~{ai_min_test} min vs ~{ai_min_full} min)")
    print("=" * 55)
    print()
    print("Run tip-to-tail:")
    print("  python run_pipeline.py --from ai")
    print()
    print("When done testing, restore full depo:")
    print("  python create_test_depo.py --restore")
    print("  python run_pipeline.py --from ai")


if __name__ == '__main__':
    main()

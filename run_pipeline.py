"""
run_pipeline.py — Master runner for mb_demo_engine_v4.

Produces the full 10-file delivery package.

USAGE:
  python run_pipeline.py                 # full run (all 8 steps)
  python run_pipeline.py --skip-ai       # skip RTF extract + steno + AI (use existing corrected_text.txt)
  python run_pipeline.py --format-only   # format + build steps only (same as --skip-ai)
  python run_pipeline.py --from extract  # start from a specific step

STEPS:
  1. extract_rtf.py          -> extracted_text.txt
  2. steno_cleanup.py        -> cleaned_text.txt
  3. ai_engine.py            -> corrected_text.txt + correction_log.json   [SLOW: ~56 min]
  4. extract_config.py       -> depo_config.json
  5. format_final.py         -> FINAL_DELIVERY/*_FINAL_FORMATTED.txt
  6. build_pdf.py            -> FINAL_DELIVERY/*_FINAL.pdf
  7. build_transcript.py     -> FINAL_DELIVERY/*_FINAL_TRANSCRIPT.txt
  8. build_condensed.py      -> FINAL_DELIVERY/*_CONDENSED.txt
  9. build_summary.py        -> FINAL_DELIVERY/*_DEPOSITION_SUMMARY.txt  [Haiku, ~$0.06]
 10. build_deliverables.py   -> FINAL_DELIVERY/ analysis docs

USE --skip-ai WHEN:
  - ai_engine.py already ran and corrected_text.txt is good
  - You only changed format/build scripts and need to rebuild output
  - You killed the pipeline accidentally after AI finished
"""
import subprocess
import sys
import os
import argparse

ALL_STEPS = [
    ('extract_rtf.py',       'extract',  'Extract RTF -> raw text'),
    ('steno_cleanup.py',     'steno',    'Steno cleanup -> cleaned text'),
    ('ai_engine.py',         'ai',       'AI correction pass -> corrected text + correction log  [~56 min]'),
    ('extract_config.py',    'config',   'Auto-extract case config -> depo_config.json'),
    ('format_final.py',      'format',   'Format final -> FINAL_FORMATTED.txt'),
    ('build_pdf.py',         'pdf',      'Build PDF -> FINAL.pdf'),
    ('build_transcript.py',  'transcript','Build transcript -> FINAL_TRANSCRIPT.txt'),
    ('build_condensed.py',   'condensed',    'Build condensed -> CONDENSED.txt'),
    ('build_summary.py',     'summary',      'Build AI summary -> DEPOSITION_SUMMARY.txt  [Haiku, ~$0.06]'),
    ('build_deliverables.py','deliverables', 'Build deliverables -> analysis docs'),
]

# Steps that run after the AI pass — safe to run independently
POST_AI_STEPS = {'config', 'format', 'pdf', 'transcript', 'condensed', 'summary', 'deliverables'}


def parse_args():
    parser = argparse.ArgumentParser(
        description='MB Demo Engine v4 — full pipeline runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--skip-ai', '--format-only',
        action='store_true',
        dest='skip_ai',
        help='Skip RTF extract, steno cleanup, and AI pass. Use existing corrected_text.txt.'
    )
    parser.add_argument(
        '--from',
        dest='start_from',
        metavar='STEP',
        choices=[s[1] for s in ALL_STEPS],
        help=f'Start from a specific step. Choices: {", ".join(s[1] for s in ALL_STEPS)}'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print which steps would run without executing them.'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Run AI summary step (build_summary.py). Off by default — opt-in only.'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Determine which steps to run
    steps = ALL_STEPS[:]

    if args.skip_ai:
        steps = [(s, k, d) for s, k, d in steps if k in POST_AI_STEPS]

    if args.start_from:
        start_keys = [s[1] for s in steps]
        if args.start_from in start_keys:
            idx = start_keys.index(args.start_from)
            steps = steps[idx:]
        else:
            print(f"[ERROR] Step '{args.start_from}' is not in the selected step list.")
            print(f"        Available: {', '.join(start_keys)}")
            sys.exit(1)

    # Guard: if skipping AI, corrected_text.txt must exist and be non-empty
    if args.skip_ai:
        if not os.path.exists('corrected_text.txt'):
            print("[ERROR] --skip-ai requires corrected_text.txt to exist.")
            print("        Run ai_engine.py first, then use --skip-ai.")
            sys.exit(1)
        size = os.path.getsize('corrected_text.txt')
        if size < 50000:
            print(f"[ERROR] corrected_text.txt looks incomplete ({size:,} bytes).")
            print("        ai_engine.py may not have finished. Check the file.")
            sys.exit(1)

    print("=" * 60)
    print("MB DEMO ENGINE v4 — PIPELINE")
    print("=" * 60)
    if args.skip_ai:
        print("MODE: Post-AI only (using existing corrected_text.txt)")
    if args.start_from:
        print(f"MODE: Starting from '{args.start_from}'")
    print(f"Steps to run: {len(steps)}")
    for _, key, desc in steps:
        print(f"  [{key}]  {desc}")
    print()

    if args.dry_run:
        print("DRY RUN — no steps executed.")
        return

    for script, key, description in steps:
        # Summary is opt-in only — skip unless --summary flag passed
        if key == 'summary' and not args.summary:
            print(f"[SKIP] summary — off by default. Use --summary to enable.")
            print()
            continue

        print(f"[STEP] {description}")
        print(f"       Running {script}...")

        # extract_config runs with --force (no interactive prompt)
        cmd = [sys.executable, script]
        if key == 'config':
            cmd.append('--force')

        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            print(f"\n[ERROR] {script} failed with exit code {result.returncode}")
            print("        Pipeline stopped. Fix the error above and re-run.")
            print(f"        To resume from this step: python run_pipeline.py --from {key}")
            sys.exit(1)
        print()

    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    delivery_dir = 'FINAL_DELIVERY'
    if os.path.exists(delivery_dir):
        print(f"\nFINAL_DELIVERY/ contains:")
        for fname in sorted(os.listdir(delivery_dir)):
            fpath = os.path.join(delivery_dir, fname)
            size = os.path.getsize(fpath)
            print(f"  {fname:<50} {size:>9,} bytes")
    print()


if __name__ == '__main__':
    main()

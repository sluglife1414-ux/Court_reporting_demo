"""
run_pipeline.py — Master runner for mb_demo_engine_v4.

Produces the full 10-file delivery package.

USAGE:
  python run_pipeline.py                        # full run (all steps), CWD = engine dir
  python run_pipeline.py --job-dir path/to/job  # run against a specific job folder
  python run_pipeline.py --preflight            # extract + steno, review metadata, confirm before AI pass
  python run_pipeline.py --skip-ai              # skip input extract + steno + AI (use existing corrected_text.txt)
  python run_pipeline.py --format-only          # format + build steps only (same as --skip-ai)
  python run_pipeline.py --from extract         # start from a specific step
  python run_pipeline.py --with-audio           # include audio check steps after specialist verify

JOB FOLDER MODEL:
  Each depo runs in its own job folder. All intermediate files (extracted_text.txt,
  cleaned_text.txt, corrected_text.txt, FINAL_DELIVERY/) land in that folder.
  Two jobs can run in parallel without collision.

  Job folder must contain:
    - CASE_CAPTION.json  (required — hard stop if missing)
    - Input file (.rtf primary, .sgngl fallback)
    - cr_config.json     (optional — defaults to format_final.py if absent)

INPUT FORMAT AUTO-DETECTION (step 1):
  Pipeline detects input format automatically — no manual switching needed.
  Priority: .sgngl > .rtf
    .sgngl found (job dir or ../mb_*/ or ../*_yellowrock*/) → extract_sgngl.py
    .rtf found (job dir only)                               → extract_rtf.py
    Both found                                              → .sgngl wins, .rtf ignored (warned)
    Neither found                                           → pipeline stops with clear error

STEPS:
  1. extract_sgngl.py OR extract_rtf.py  -> extracted_text.txt  [auto-detected]
  2. steno_cleanup.py        -> cleaned_text.txt
  3. ai_engine.py            -> corrected_text.txt + correction_log.json   [SLOW: ~56 min]
  4. verify_agent.py         -> verify_log.json  (2nd-pass: Haiku reviews HIGH corrections)  [~1 min]
  5. apply_verify.py         -> corrected_text.txt updated (DISAGREE items get [REVIEW] tags)
  6. extract_config.py       -> depo_config.json
  7. format_final.py         -> FINAL_DELIVERY/*_FINAL_FORMATTED.txt
  8. build_pdf.py            -> FINAL_DELIVERY/*_FINAL.pdf
  9. build_transcript.py     -> FINAL_DELIVERY/*_FINAL_TRANSCRIPT.txt
 10. build_condensed.py      -> FINAL_DELIVERY/*_CONDENSED.txt
 11. build_summary.py        -> FINAL_DELIVERY/*_DEPOSITION_SUMMARY.txt  [Haiku, ~$0.06]
 12. build_deliverables.py   -> FINAL_DELIVERY/ analysis docs

USE --skip-ai WHEN:
  - ai_engine.py already ran and corrected_text.txt is good
  - You only changed format/build scripts and need to rebuild output
  - You killed the pipeline accidentally after AI finished
"""
import subprocess
import sys
import os
import argparse

# Absolute path to the engine directory.
# Stays valid after os.chdir() to a job folder — script paths are built from this.
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

ALL_STEPS = [
    ('extract_rtf.py',       'extract',      'Extract input -> raw text  [format auto-detected at runtime]'),
    ('steno_cleanup.py',     'steno',        'Steno cleanup -> cleaned text'),
    ('ai_engine.py',         'ai',           'AI correction pass -> corrected text + correction log  [~56 min]'),
    ('verify_agent.py',      'verify',       'Pass 2: Haiku reviews HIGH corrections -> verify_log.json  [~1 min]'),
    ('apply_verify.py',      'apply_verify', 'Apply verify: re-tag DISAGREE items as [REVIEW] in corrected_text.txt'),
    ('specialist_verify.py',      'specialist',    'Pass 3: 6-agent specialist review -> specialist_verify_log.json  [~2 min]'),
    ('audio_validation.py',       'audio_check',   'Audio check: match [REVIEW] items to recording -> audio_matches.json  [--with-audio]'),
    ('apply_audio_validation.py', 'apply_audio',   'Apply audio corrections -> corrected_text.txt + Section F in MB_REVIEW  [--with-audio]'),
    ('extract_config.py',         'config',        'Auto-extract case config -> depo_config.json'),
    ('format_final.py',      'format',       'Format final -> FINAL_FORMATTED.txt'),
    ('build_pdf.py',         'pdf',          'Build PDF -> FINAL.pdf'),
    ('build_transcript.py',  'transcript',   'Build transcript -> FINAL_TRANSCRIPT.txt'),
    ('build_condensed.py',   'condensed',    'Build condensed -> CONDENSED.txt'),
    ('build_summary.py',     'summary',      'Build AI summary -> DEPOSITION_SUMMARY.txt  [Haiku, ~$0.06]'),
    ('build_deliverables.py','deliverables', 'Build deliverables -> analysis docs'),
    ('build_mb_review_v3.py','mb_review',    'Build MB review package -> {case}_MB_REVIEW.txt'),
]

# Steps that run after the AI pass — safe to run independently
POST_AI_STEPS = {'verify', 'apply_verify', 'specialist', 'audio_check', 'apply_audio', 'config', 'format', 'pdf', 'transcript', 'condensed', 'summary', 'deliverables', 'mb_review'}


def load_cr_config():
    """Load cr_config.json from CWD (job folder). Returns {} if not found."""
    if os.path.exists('cr_config.json'):
        import json
        with open('cr_config.json', encoding='utf-8') as f:
            return json.load(f)
    return {}


def detect_input_format():
    """
    Detect available input file and return the correct extractor script.

    Priority: .sgngl > .rtf
    Mirrors the search paths used by extract_sgngl.py auto-detection.

    Returns:
        (script, description, fmt)  where fmt is 'sgngl', 'rtf', or None
    """
    import glob as _glob

    sgngl_candidates = (
        _glob.glob('*.sgngl') +
        _glob.glob('../mb_*/*.sgngl') +
        _glob.glob('../*_yellowrock*/*.sgngl')
    )
    rtf_candidates = _glob.glob('*.rtf')

    if sgngl_candidates:
        sgngl_path = sgngl_candidates[0]
        if rtf_candidates:
            print(f"[INPUT] .sgngl found: {sgngl_path}")
            print(f"[INPUT] .rtf also found: {rtf_candidates[0]} — .sgngl takes priority (remove .rtf if this is wrong)")
        else:
            print(f"[INPUT] .sgngl found: {sgngl_path}")
        return ('extract_sgngl.py', f'Extract .sgngl -> raw text  [{sgngl_path}]', 'sgngl')

    if rtf_candidates:
        rtf_path = rtf_candidates[0]
        print(f"[INPUT] .rtf found: {rtf_path}")
        return ('extract_rtf.py', f'Extract RTF -> raw text  [{rtf_path}]', 'rtf')

    return (None, None, None)


def parse_args():
    parser = argparse.ArgumentParser(
        description='MB Demo Engine v4 — full pipeline runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--job-dir',
        dest='job_dir',
        metavar='PATH',
        help='Path to job folder. All I/O (input file, intermediates, FINAL_DELIVERY/) goes here. '
             'Required for parallel runs. Defaults to CWD if omitted.'
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
        '--preflight',
        action='store_true',
        help='Run extract + steno, review extracted metadata, then confirm before AI pass.'
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
    parser.add_argument(
        '--with-audio',
        action='store_true',
        dest='with_audio',
        help='Run audio check steps after specialist verify. Requires audio_transcript.json on disk.'
    )
    return parser.parse_args()


def load_cr_config():
    """Load cr_config.json if present. Returns {} if not found."""
    if os.path.exists('cr_config.json'):
        import json
        with open('cr_config.json', encoding='utf-8') as f:
            return json.load(f)
    return {}


def main():
    args = parse_args()
    cr_cfg = load_cr_config()

    # ── CR formatter dispatch ─────────────────────────────────────────────────
    # cr_config.json owns the formatter. Default: format_final.py (MB/LA).
    formatter = cr_cfg.get('formatter', 'format_final.py')
    for i, (script, key, desc) in enumerate(ALL_STEPS):
        if key == 'format':
            ALL_STEPS[i] = (formatter, key, desc)
            if formatter != 'format_final.py':
                print(f"[CR] formatter: {formatter}  (cr_config.json)")
            break
    # ─────────────────────────────────────────────────────────────────────────

    # ── Job directory — chdir so all relative file I/O lands in the job folder ──
    if args.job_dir:
        job_dir = os.path.abspath(args.job_dir)
        if not os.path.isdir(job_dir):
            print(f"[ERROR] --job-dir '{job_dir}' does not exist.")
            sys.exit(1)
        os.chdir(job_dir)
        print(f"[JOB] Working directory: {job_dir}")

    # ── CASE_CAPTION.json hard stop — every job requires one ─────────────────
    if not os.path.exists('CASE_CAPTION.json'):
        print("[ERROR] CASE_CAPTION.json not found.")
        print("        Every job requires a CASE_CAPTION.json in the job folder.")
        print(f"        Working directory: {os.getcwd()}")
        sys.exit(1)

    # ── CR config + formatter dispatch ───────────────────────────────────────
    # cr_config.json lives in the job folder (copied from CR profile at intake).
    # Default formatter: format_final.py (MB/LA). Override via cr_config.json.
    cr_cfg = load_cr_config()
    formatter = cr_cfg.get('formatter', 'format_final.py')
    for i, (script, key, desc) in enumerate(ALL_STEPS):
        if key == 'format':
            ALL_STEPS[i] = (formatter, key, desc)
            if formatter != 'format_final.py':
                print(f"[CR] formatter: {formatter}  (cr_config.json)")
            break
    # ─────────────────────────────────────────────────────────────────────────

    # ── Step 1: detect input format and swap extractor if needed ─────────────
    # Only needed when we're actually running the extract step.
    # --skip-ai and --from <post-ai-step> both bypass extraction entirely.
    needs_extract = (
        not args.skip_ai and
        (not args.start_from or args.start_from in ('extract', 'steno'))
    )
    steps_list = ALL_STEPS[:]
    if needs_extract:
        script, desc, fmt = detect_input_format()
        if script is None:
            print("[ERROR] No input file found.")
            print("        Need a .sgngl (job dir or ../mb_*/) or a .rtf (job dir).")
            print("        Copy the input file here, or run with --skip-ai if AI is already done.")
            sys.exit(1)
        # Swap step 1 with the detected extractor
        steps_list[0] = (script, 'extract', desc)
    # ─────────────────────────────────────────────────────────────────────────

    # Determine which steps to run
    steps = steps_list[:]

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
        if size < 1000:
            print(f"[ERROR] corrected_text.txt looks empty ({size:,} bytes).")
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

    # PREFLIGHT: extract + steno → review metadata → confirm before AI
    if args.preflight:
        print("=" * 60)
        print("PREFLIGHT MODE — review metadata before AI pass")
        print("=" * 60)
        for script, key, desc in steps_list:
            if key not in ('extract', 'steno'):
                continue
            print(f"[STEP] {desc}")
            print(f"       Running {script}...")
            result = subprocess.run([sys.executable, os.path.join(ENGINE_DIR, script)], capture_output=False)
            if result.returncode != 0:
                print(f"\n[ERROR] {script} failed. Fix above and retry.")
                sys.exit(1)
            print()
        print("[PREFLIGHT] Running extract_config.py --review ...")
        print("            Review the extracted values below.")
        print("            If anything is UNKNOWN, Ctrl+C now and fill in case_info manually.")
        print()
        result = subprocess.run([sys.executable, os.path.join(ENGINE_DIR, 'extract_config.py'), '--review'], capture_output=False)
        if result.returncode != 0:
            print("\n[PREFLIGHT] Metadata review failed or rejected. Pipeline stopped.")
            print("            Fix depo_config.json manually, then run: python run_pipeline.py --from ai")
            sys.exit(1)
        confirm = input("\n[PREFLIGHT] Metadata confirmed. Proceed to AI pass? (y/n): ").strip().lower()
        if confirm != 'y':
            print("[PREFLIGHT] Stopped. Run 'python run_pipeline.py --from ai' when ready.")
            sys.exit(0)
        steps = [(s, k, d) for s, k, d in steps_list if k not in ('extract', 'steno')]
        print()

    for script, key, description in steps:
        # Summary is opt-in only — skip unless --summary flag passed
        if key == 'summary' and not args.summary:
            print(f"[SKIP] summary — off by default. Use --summary to enable.")
            print()
            continue

        # Audio check is opt-in only — skip unless --with-audio flag passed
        if key in ('audio_check', 'apply_audio') and not args.with_audio:
            print(f"[SKIP] {key} — off by default. Use --with-audio to enable.")
            print()
            continue

        # Audio check guard — targeted mode requires audio_transcript.json on disk
        if key == 'audio_check' and args.with_audio:
            if not os.path.exists('audio_transcript.json'):
                print(f"[WARN] audio_transcript.json not found — skipping audio check.")
                print(f"       Run full transcription first:")
                print(f"         python audio_validation.py --full-run")
                print()
                continue

        print(f"[STEP] {description}")
        print(f"       Running {script}...")

        # extract_config runs with --force (no interactive prompt)
        cmd = [sys.executable, os.path.join(ENGINE_DIR, script)]
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

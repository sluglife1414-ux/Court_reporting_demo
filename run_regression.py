"""
run_regression.py — Two-CR regression harness for mb_demo_engine_v4.

Runs --skip-ai on each specified job folder, checks all delivery files,
verifies CR isolation, and prints a PASS/FAIL report.

USAGE:
  python run_regression.py --mb-job  "path/to/easley/work"
  python run_regression.py --ad-job  "path/to/fourman/work"
  python run_regression.py --mb-job  "path/to/easley/work"  --ad-job "path/to/fourman/work"

PASS/FAIL CRITERIA (per job):
  [ ] corrected_text.txt exists and > 50KB
  [ ] CASE_CAPTION.json exists (hard stop — pipeline won't run without it)
  [ ] cr_config.json exists and has correct formatter key
  [ ] --skip-ai pipeline completes without error
  [ ] FINAL_DELIVERY/ contains all expected files, all non-empty
  [ ] FINAL_FORMATTED.txt contains witness name (basic sanity)
  [ ] FINAL.pdf > 10KB (not an empty shell)
  [ ] CR isolation: MB job formatter = format_final.py
                    AD job formatter = format_final_ny_wcb.py

MB-ONLY (if approved_pdf_path in CASE_CAPTION.json):
  [ ] compare_accuracy.py score >= ACCURACY_FLOOR (97.3%)

WHAT THIS DOES NOT TEST:
  - The AI pass (ai_engine.py) — use tip-to-tail run for that
  - Audio validation steps
  - Network / API connectivity

SETUP REQUIREMENTS:
  Each job folder (work/) must contain:
    - corrected_text.txt   (AI output — PRECIOUS)
    - CASE_CAPTION.json    (real data, no TODO placeholders)
    - cr_config.json       (injected by intake.py)
"""
# ──────────────────────────────────────────────────────────────
# v1.0  2026-04-05  initial — two-CR regression harness
# ──────────────────────────────────────────────────────────────

import argparse
import json
import os
import subprocess
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

# Minimum corrected_text.txt size — below this the AI pass probably didn't finish
# 10KB floor: catches empty/aborted runs without penalizing short depos (Fourman = 20KB)
CORRECTED_TEXT_MIN_BYTES = 10_000

# Accuracy floor for MB jobs (compare_accuracy.py score)
ACCURACY_FLOOR = 97.3

# Expected formatter per CR type
EXPECTED_FORMATTER = {
    'mb': 'format_final.py',
    'ad': 'format_final_ny_wcb.py',
}

# Delivery files we expect in FINAL_DELIVERY/ (suffix patterns)
EXPECTED_DELIVERY_SUFFIXES = [
    '_FINAL.pdf',
    '_FINAL_FORMATTED.txt',
    '_FINAL_TRANSCRIPT.txt',
    '_CONDENSED.txt',
    '_CR_REVIEW.txt',
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def check(label, passed, detail=''):
    """Print a single check result. Returns True if passed."""
    icon = 'PASS' if passed else 'FAIL'
    line = f"  [{icon}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    return passed


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def find_delivery_file(delivery_dir, suffix):
    """Find a file in FINAL_DELIVERY/ that ends with the given suffix."""
    if not os.path.isdir(delivery_dir):
        return None
    for fname in os.listdir(delivery_dir):
        if fname.endswith(suffix):
            return os.path.join(delivery_dir, fname)
    return None


def parse_accuracy_score(output):
    """
    Parse the overall accuracy score from compare_accuracy.py output.
    Looks for: 'OVERALL  97.3%' or 'Overall accuracy: 97.3'
    Returns float or None.
    """
    import re
    for line in output.splitlines():
        m = re.search(r'OVERALL.*?(\d+\.\d+)\s*%', line, re.IGNORECASE)
        if m:
            return float(m.group(1))
        m = re.search(r'[Oo]verall.*?(\d+\.\d+)', line)
        if m:
            return float(m.group(1))
    return None


# ── Per-job regression runner ─────────────────────────────────────────────────

def run_job_regression(label, work_dir, cr_type):
    """
    Run full regression checks for one job.
    cr_type: 'mb' or 'ad'
    Returns (passed_count, total_count, failures).
    """
    print()
    print(f"{'=' * 60}")
    print(f"  {label.upper()}")
    print(f"  Job dir: {work_dir}")
    print(f"{'=' * 60}")

    passed = 0
    total  = 0
    failures = []

    def chk(label, ok, detail=''):
        nonlocal passed, total
        total += 1
        result = check(label, ok, detail)
        if result:
            passed += 1
        else:
            failures.append(f"{label}: {detail}" if detail else label)
        return result

    # ── Pre-run checks ────────────────────────────────────────────────────────
    if not os.path.isdir(work_dir):
        print(f"  [FAIL] Job folder not found: {work_dir}")
        return 0, 1, [f"Job folder missing: {work_dir}"]

    # corrected_text.txt
    ct_path  = os.path.join(work_dir, 'corrected_text.txt')
    ct_exists = os.path.exists(ct_path)
    ct_size   = os.path.getsize(ct_path) if ct_exists else 0
    chk('corrected_text.txt exists',   ct_exists, '' if ct_exists else 'Run AI pass first')
    chk('corrected_text.txt > 10KB',   ct_size >= CORRECTED_TEXT_MIN_BYTES,
        f"{ct_size:,} bytes" if ct_exists else 'file missing')

    # CASE_CAPTION.json
    cap_path = os.path.join(work_dir, 'CASE_CAPTION.json')
    cap_ok   = os.path.exists(cap_path)
    chk('CASE_CAPTION.json exists', cap_ok, '' if cap_ok else 'Copy real caption before running')
    if cap_ok:
        cap = load_json(cap_path)
        has_todos = any('TODO' in str(v) for v in cap.values())
        chk('CASE_CAPTION.json has no TODO placeholders', not has_todos,
            'Fill in all TODO values before running' if has_todos else '')

    # cr_config.json
    cfg_path = os.path.join(work_dir, 'cr_config.json')
    cfg_ok   = os.path.exists(cfg_path)
    chk('cr_config.json exists', cfg_ok, '' if cfg_ok else 'Run intake.py to inject cr_config')
    expected_formatter = EXPECTED_FORMATTER[cr_type]
    if cfg_ok:
        cfg = load_json(cfg_path)
        actual_formatter = cfg.get('formatter', 'format_final.py')
        formatter_ok = actual_formatter == expected_formatter
        chk('Correct formatter in cr_config.json', formatter_ok,
            f"{actual_formatter}" + ('' if formatter_ok else f" (expected {expected_formatter})"))

    # Stop pre-run if critical files missing
    if not ct_exists or not cap_ok or not cfg_ok:
        print()
        print("  Pre-run checks failed — skipping pipeline run.")
        return passed, total, failures

    # ── Run pipeline --from config ────────────────────────────────────────────
    # Use --from config (not --skip-ai) so we skip all AI/verify passes that
    # need an API key. Regression tests the formatting pipeline only.
    print()
    print(f"  Running pipeline --from config ...")
    cmd = [sys.executable, os.path.join(ENGINE_DIR, 'run_pipeline.py'),
           '--job-dir', work_dir, '--from', 'config']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    pipeline_ok = result.returncode == 0
    chk('Pipeline --from config completed without error', pipeline_ok,
        '' if pipeline_ok else f"exit code {result.returncode}")
    if not pipeline_ok:
        print()
        print("  Pipeline stderr:")
        for line in result.stderr.splitlines()[-10:]:
            print(f"    {line}")
        return passed, total, failures

    # ── Delivery file checks ──────────────────────────────────────────────────
    delivery_dir = os.path.join(work_dir, 'FINAL_DELIVERY')
    for suffix in EXPECTED_DELIVERY_SUFFIXES:
        fpath = find_delivery_file(delivery_dir, suffix)
        exists = fpath is not None
        size   = os.path.getsize(fpath) if exists else 0
        chk(f"FINAL_DELIVERY/*{suffix} exists and non-empty",
            exists and size > 0,
            f"{size:,} bytes" if exists else 'NOT FOUND')

    # FINAL.pdf sanity
    pdf_path = find_delivery_file(delivery_dir, '_FINAL.pdf')
    if pdf_path:
        pdf_size = os.path.getsize(pdf_path)
        chk('FINAL.pdf > 10KB', pdf_size > 10_000, f"{pdf_size:,} bytes")

    # FINAL_FORMATTED.txt contains witness name
    fmt_path = find_delivery_file(delivery_dir, '_FINAL_FORMATTED.txt')
    if fmt_path and cap_ok:
        witness_last = cap.get('witness_last', '')
        with open(fmt_path, encoding='utf-8') as f:
            fmt_text = f.read(5000)
        witness_found = witness_last.upper() in fmt_text.upper()
        chk(f"FINAL_FORMATTED.txt contains witness name ({witness_last})",
            witness_found, '' if witness_found else 'Name not found in first 5000 chars')

    # ── MB-only: accuracy score ───────────────────────────────────────────────
    if cr_type == 'mb' and cap_ok:
        approved_pdf = cap.get('approved_pdf_path', '')
        if approved_pdf and os.path.exists(approved_pdf):
            print()
            print(f"  Running compare_accuracy.py against approved PDF ...")
            acc_cmd = [sys.executable, os.path.join(ENGINE_DIR, 'compare_accuracy.py')]
            acc_result = subprocess.run(acc_cmd, capture_output=True, text=True,
                                        encoding='utf-8', errors='replace', cwd=work_dir)
            score = parse_accuracy_score(acc_result.stdout + acc_result.stderr)
            if score is not None:
                chk(f"Accuracy score >= {ACCURACY_FLOOR}%",
                    score >= ACCURACY_FLOOR, f"{score:.1f}%")
            else:
                chk('Accuracy score parseable', False, 'Could not parse score from output')
        else:
            print(f"  [SKIP] Accuracy check — no approved_pdf_path in CASE_CAPTION.json")
            print(f"         Add 'approved_pdf_path' to CASE_CAPTION.json to enable this check.")

    return passed, total, failures


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description='Two-CR regression harness',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--mb-job', metavar='PATH',
                        help='Path to MB (Louisiana) job work/ folder')
    parser.add_argument('--ad-job', metavar='PATH',
                        help='Path to AD (NY WCB) job work/ folder')
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.mb_job and not args.ad_job:
        print("[ERROR] Specify at least one job: --mb-job and/or --ad-job")
        print("        python run_regression.py --help")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  MB DEMO ENGINE v4 — REGRESSION TEST")
    print("=" * 60)

    jobs    = []
    results = []

    if args.mb_job:
        jobs.append(('Easley (MB / Louisiana)', os.path.abspath(args.mb_job), 'mb'))
    if args.ad_job:
        jobs.append(('Fourman (AD / NY WCB)',   os.path.abspath(args.ad_job), 'ad'))

    for label, work_dir, cr_type in jobs:
        passed, total, failures = run_job_regression(label, work_dir, cr_type)
        results.append((label, passed, total, failures))

    # ── CR isolation check (only meaningful when both jobs ran) ───────────────
    if args.mb_job and args.ad_job:
        print()
        print(f"{'=' * 60}")
        print(f"  CR ISOLATION CHECK")
        print(f"{'=' * 60}")
        mb_cfg_path = os.path.join(os.path.abspath(args.mb_job), 'cr_config.json')
        ad_cfg_path = os.path.join(os.path.abspath(args.ad_job), 'cr_config.json')
        isolation_pass = True
        if os.path.exists(mb_cfg_path):
            mb_fmt = load_json(mb_cfg_path).get('formatter', '')
            ok = mb_fmt == EXPECTED_FORMATTER['mb']
            check('MB job used format_final.py (not NY WCB)', ok, mb_fmt)
            isolation_pass = isolation_pass and ok
        if os.path.exists(ad_cfg_path):
            ad_fmt = load_json(ad_cfg_path).get('formatter', '')
            ok = ad_fmt == EXPECTED_FORMATTER['ad']
            check('AD job used format_final_ny_wcb.py (not MB)', ok, ad_fmt)
            isolation_pass = isolation_pass and ok
        check('No CR cross-loading detected', isolation_pass)

    # ── Final report ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  REGRESSION REPORT")
    print("=" * 60)
    overall_pass = True
    for label, passed, total, failures in results:
        status = 'PASS' if passed == total else 'FAIL'
        if passed != total:
            overall_pass = False
        print(f"  [{status}] {label}  {passed}/{total} checks passed")
        for f in failures:
            print(f"         !! {f}")

    print()
    if overall_pass:
        print("  OVERALL: PASS — engine output matches expectations.")
    else:
        print("  OVERALL: FAIL — fix issues above before delivering to CR.")
    print("=" * 60)
    print()

    sys.exit(0 if overall_pass else 1)


if __name__ == '__main__':
    main()

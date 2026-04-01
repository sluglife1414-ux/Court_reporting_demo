"""
test_regression.py
PURPOSE: Regression test suite for the mb_demo_engine_v4 master pipeline.
         Run after any change to format_final.py, build_mb_review_v2.py,
         or build_pdf.py to catch silent breakage before it reaches MB.

USAGE:
    python test_regression.py              # run against current output
    python test_regression.py --rebuild    # re-run format_final + mb_review first

EXIT: 0 = all pass, 1 = one or more failures

GROUND TRUTH: fixtures captured 2026-03-27, Easley depo (203 pages).
"""

import sys
import os
import json
import re
import subprocess
import argparse

BASE = os.path.dirname(os.path.abspath(__file__))

PASS = "PASS"
FAIL = "FAIL"

results = []


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def record(name, passed, detail=""):
    mark = PASS if passed else FAIL
    msg = f"  [{mark}]  {name}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((name, passed, detail))


def load_json(path):
    full = os.path.join(BASE, path)
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    full = os.path.join(BASE, path)
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8") as f:
        return f.read()


def parse_pages(text):
    """Return dict {page_num: [line_strings]} from FINAL_FORMATTED.txt content."""
    pages = {}
    cur = None
    cur_lines = []
    for ln in text.split("\n"):
        s = ln.strip()
        if s.isdigit() and int(s) >= 1:
            if cur is not None:
                pages[cur] = cur_lines
            cur = int(s)
            cur_lines = []
        elif cur is not None:
            cur_lines.append(ln)
    if cur is not None:
        pages[cur] = cur_lines
    return pages


def get_case_short():
    """Detect case_short by finding the FINAL_FORMATTED.txt in FINAL_DELIVERY/."""
    import glob
    pattern = os.path.join(BASE, "FINAL_DELIVERY", "*_FINAL_FORMATTED.txt")
    matches = glob.glob(pattern)
    if matches:
        fname = os.path.basename(matches[0])
        return fname.replace("_FINAL_FORMATTED.txt", "")
    # Fallback: read from depo_config.json
    cfg = load_json("depo_config.json") or {}
    return cfg.get("case_short", "Easley_YellowRock")


# ─────────────────────────────────────────────
# Optional rebuild step
# ─────────────────────────────────────────────

def rebuild():
    print("\nRebuilding format_final.py + build_mb_review_v2.py ...")
    for script in ("format_final.py", "build_mb_review_v2.py"):
        r = subprocess.run(
            [sys.executable, os.path.join(BASE, script)],
            capture_output=True, text=True, cwd=BASE
        )
        if r.returncode != 0:
            print(f"  ERROR running {script}:\n{r.stderr[-800:]}")
            sys.exit(1)
        print(f"  {script} OK")


# ─────────────────────────────────────────────
# TEST SUITE
# ─────────────────────────────────────────────

def run_tests():

    case_short = get_case_short()

    print("\n" + "=" * 60)
    print(f"REGRESSION TESTS  |  {case_short.replace('_', ' v. ')}")
    print("=" * 60)

    # ── 1. FILES EXIST ───────────────────────────────────────
    print("\n[1] Required output files")
    required = [
        f"FINAL_DELIVERY/{case_short}_FINAL_FORMATTED.txt",
        f"FINAL_DELIVERY/{case_short}_FINAL.pdf",
        f"FINAL_DELIVERY/{case_short}_FINAL_TRANSCRIPT.txt",
        f"FINAL_DELIVERY/{case_short}_CONDENSED.txt",
        "FINAL_DELIVERY/MB_REVIEW.txt",
        "FINAL_DELIVERY/review_locations.json",
        "FINAL_DELIVERY/DEPOSITION_SUMMARY.txt",
        "FINAL_DELIVERY/EXHIBIT_INDEX.txt",
        "FINAL_DELIVERY/MEDICAL_TERMS_LOG.txt",
        "FINAL_DELIVERY/QA_FLAGS.txt",
    ]
    for f in required:
        exists = os.path.exists(os.path.join(BASE, f))
        record(f"exists: {os.path.basename(f)}", exists,
               "" if exists else f"MISSING: {f}")

    # ── 2. PAGE COUNT ─────────────────────────────────────────
    print("\n[2] Page count")
    formatted = load_text(f"FINAL_DELIVERY/{case_short}_FINAL_FORMATTED.txt")
    pages = {}
    if formatted:
        pages = parse_pages(formatted)
        page_count = max(pages.keys()) if pages else 0
        # Easley baseline: 203. Allow ±5 pages for minor format tweaks.
        in_range = 198 <= page_count <= 208
        record(
            f"page count {page_count} (expected 198-208)",
            in_range,
            "" if in_range else f"GOT {page_count} — outside ±5 of baseline 203"
        )
    else:
        record("page count", False, "FINAL_FORMATTED.txt not found")

    # ── 3. SECTION HEADERS ────────────────────────────────────
    print("\n[3] Section headers present")
    if formatted:
        checks = [
            ("Caption page 1",       r"STATE OF LOUISIANA"),
            ("Index page 2",         r"I N D E X"),
            ("Appearances present",  r"APPEARANCES"),
            ("Stipulation present",  r"STIPULATION"),
            ("Examination header",   r"EXAMINATION"),
            ("Reporter cert",        r"REPORTER'S CERTIFICATE"),
            ("Witness cert",         r"WITNESS'S CERTIFICATE"),
        ]
        for name, pattern in checks:
            found = bool(re.search(pattern, formatted, re.IGNORECASE))
            record(name, found, "" if found else f"Pattern not found: {pattern}")

    # ── 4. Q/A INDENTATION ───────────────────────────────────
    print("\n[4] Q/A indentation (no flush-left continuation lines)")
    if formatted:
        bad = []
        lines = formatted.split("\n")
        prev_qa = False
        for i, ln in enumerate(lines):
            if re.match(r"^\s+[QA]\.\s", ln):
                prev_qa = True
            elif prev_qa and ln and not ln[0].isspace() and re.match(r"^[a-z]", ln):
                bad.append(f"line {i+1}: {repr(ln[:60])}")
                prev_qa = False
            else:
                prev_qa = False
        record(
            "no flush-left continuation lines",
            len(bad) == 0,
            "; ".join(bad[:3]) if bad else ""
        )

    # ── 5. SIDECAR COVERAGE ───────────────────────────────────
    print("\n[5] review_locations.json sidecar")
    locs = load_json("FINAL_DELIVERY/review_locations.json")
    log  = load_json("correction_log.json")

    if locs and log:
        corrections = log.get("corrections", [])
        low_na_count = sum(
            1 for c in corrections if c.get("confidence") in ("LOW", "N/A")
        )
        record(
            f"sidecar covers all {low_na_count} LOW/N/A items",
            len(locs) == low_na_count,
            f"sidecar has {len(locs)}, expected {low_na_count}"
        )

        exact   = sum(1 for v in locs.values() if v and not v.startswith("~") and v != "location unknown")
        unknown = sum(1 for v in locs.values() if v == "location unknown")

        # Easley baseline: 45 exact. Fail if we lose more than 5.
        record(
            f"exact locations >= 40 (baseline 45, got {exact})",
            exact >= 40,
            "Dropped below threshold — check inject_anchors() or build_review_locations()"
        )
        # Unknown should stay <= 3 (baseline 1 for Easley)
        record(
            f"location unknown <= 5 (baseline 1, got {unknown})",
            unknown <= 5,
            "Too many unknowns — anchor injection or text-search fallback may be broken"
        )
        # No double-tilde from neighbor chaining
        double_tilde = [k for k, v in locs.items() if v and v.startswith("~~")]
        record(
            "no double-tilde (~~) locations",
            len(double_tilde) == 0,
            f"Found {len(double_tilde)} double-tilde entries: {double_tilde[:5]}"
        )
    else:
        record("sidecar exists and correction_log present", False,
               "Could not load one or both files")

    # ── 6. ANCHOR FIXTURE CHECK ───────────────────────────────
    print("\n[6] Known item locations (hand-verified fixtures)")
    # Format: (correction_log_index, expected_page, expected_line, description)
    # Page tolerance: ±1, Line tolerance: ±3
    FIXTURES = [
        (  27,  17, 11, "ITEM 001 — all of the responses being actually"),
        ( 130,  30,  1, "ITEM 005 — REV rent possibly get some portion"),
        ( 335,  59,  2, "ITEM 010 — The parties mentioned in this Donelon"),
        ( 533,  85, 17, "ITEM 020 — And Sunny Solar nor Luminus nor Mr."),
        ( 714, 110, 17, "ITEM 030 — put additional N and they wanted to"),
        (1083, 169,  5, "ITEM 040 — Reading this E-mail, read do you read"),
    ]
    PAGE_TOL = 1
    LINE_TOL = 3

    if locs:
        for cl_idx, exp_page, exp_line, desc in FIXTURES:
            loc = locs.get(str(cl_idx))
            if loc is None:
                record(desc, False, f"idx {cl_idx} not in sidecar")
                continue
            if loc == "location unknown":
                record(desc, False, f"location unknown (was p.{exp_page} l.{exp_line})")
                continue
            m = re.match(r"~?p\.(\d+)\s+l\.(\d+)", loc)
            if not m:
                record(desc, False, f"unparseable location: {loc!r}")
                continue
            got_page, got_line = int(m.group(1)), int(m.group(2))
            page_ok = abs(got_page - exp_page) <= PAGE_TOL
            line_ok = abs(got_line - exp_line) <= LINE_TOL
            passed  = page_ok and line_ok
            detail  = ""
            if not passed:
                detail = (f"expected p.{exp_page} l.{exp_line}, "
                          f"got {loc} (page_diff={got_page-exp_page}, "
                          f"line_diff={got_line-exp_line})")
            record(desc, passed, detail)
    else:
        record("fixtures (sidecar not available)", False, "")

    # ── 7. MB_REVIEW STRUCTURE ────────────────────────────────
    print("\n[7] MB_REVIEW.txt structure")
    mb_review = load_text("FINAL_DELIVERY/MB_REVIEW.txt")
    if mb_review:
        for section in ["SECTION 1", "SECTION 2", "SECTION 3", "SECTION 4"]:
            record(f"MB_REVIEW has {section}",
                   section in mb_review,
                   "" if section in mb_review else f"{section} missing from MB_REVIEW")

        if log:
            corrections = log.get("corrections", [])
            low_count = sum(1 for c in corrections if c.get("confidence") == "LOW")
            item_matches = re.findall(r"ITEM \d+\s+\|", mb_review)
            record(
                f"Section 3 has {low_count} ITEM entries (got {len(item_matches)})",
                len(item_matches) == low_count,
                f"Expected {low_count}, found {len(item_matches)}"
            )

        double_tilde_lines = [ln for ln in mb_review.split("\n") if "~~p." in ln]
        record(
            "no ~~ in MB_REVIEW location refs",
            len(double_tilde_lines) == 0,
            "; ".join(double_tilde_lines[:3]) if double_tilde_lines else ""
        )

        # MB_REVIEW footer date should be present (generated at runtime)
        from datetime import date
        today_str = date.today().strftime('%Y-%m-%d')
        record(
            "MB_REVIEW footer has today's date",
            today_str in mb_review,
            f"Expected {today_str} in footer — may be running on stale cached output"
        )
    else:
        record("MB_REVIEW.txt exists", False, "File not found")

    # ── 8. COARSE METRICS vs MB GROUND TRUTH ─────────────────
    # Principle: coarsest check first. Pages/words/chars must roughly match
    # MB's approved PDF before any line-by-line accuracy work is meaningful.
    # TOLERANCES: ±3 pages, ±3% words, ±5% chars (formatting differences
    # account for some char delta even when content is correct).
    # Ground truth: MB Easley final — 031326yellowrock-FINAL.pdf (223 pages)
    print("\n[8] Coarse metrics vs MB ground truth (pages / words / chars)")
    MB_APPROVED_PDF = r"C:\Users\scott\Downloads\031326yellowrock-FINAL.pdf"
    our_pdf = os.path.join(BASE, "FINAL_DELIVERY", "FINAL.pdf")

    PAGE_TOLERANCE  = 3      # pages
    WORD_TOLERANCE  = 0.03   # 3%
    CHAR_TOLERANCE  = 0.05   # 5%

    def extract_metrics(pdf_path):
        """Return (pages, words, chars) from a PDF."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pages = len(pdf.pages)
                text = "".join(p.extract_text() or "" for p in pdf.pages)
            words = len(text.split())
            chars = len(text)
            return pages, words, chars
        except Exception as e:
            return None, None, str(e)

    if not os.path.exists(MB_APPROVED_PDF):
        record("MB approved PDF found for coarse metrics", False,
               f"Not found: {MB_APPROVED_PDF}")
    elif not os.path.exists(our_pdf):
        record("our FINAL.pdf found for coarse metrics", False,
               f"Not found: {our_pdf}")
    else:
        mb_pages, mb_words, mb_chars = extract_metrics(MB_APPROVED_PDF)
        our_pages, our_words, our_chars = extract_metrics(our_pdf)

        if mb_pages is None:
            record("coarse metrics: MB PDF readable", False, str(mb_chars))
        elif our_pages is None:
            record("coarse metrics: our PDF readable", False, str(our_chars))
        else:
            page_diff = abs(our_pages - mb_pages)
            word_pct  = abs(our_words - mb_words) / max(mb_words, 1)
            char_pct  = abs(our_chars - mb_chars) / max(mb_chars, 1)

            record(
                f"page count within ±{PAGE_TOLERANCE} (ours={our_pages} mb={mb_pages} diff={our_pages - mb_pages:+d})",
                page_diff <= PAGE_TOLERANCE,
                f"off by {page_diff} pages — structural issue likely" if page_diff > PAGE_TOLERANCE else ""
            )
            record(
                f"word count within ±{int(WORD_TOLERANCE*100)}% (ours={our_words:,} mb={mb_words:,} diff={our_words - mb_words:+,})",
                word_pct <= WORD_TOLERANCE,
                f"{word_pct:.1%} off — AI may have dropped or added content" if word_pct > WORD_TOLERANCE else ""
            )
            record(
                f"char count within ±{int(CHAR_TOLERANCE*100)}% (ours={our_chars:,} mb={mb_chars:,} diff={our_chars - mb_chars:+,})",
                char_pct <= CHAR_TOLERANCE,
                f"{char_pct:.1%} off — formatting drift likely" if char_pct > CHAR_TOLERANCE else ""
            )

    # ── 9. APPEARANCES BY: LINES FLAGGED (KB-017) ────────────
    print("\n[9] Appearances BY: lines carry REVIEW flag (KB-017)")
    corrected = load_text("corrected_text.txt")
    if corrected:
        lines = corrected.split("\n")
        in_app = False
        by_lines_unflagged = []
        for line in lines:
            s = line.strip()
            if "A P P E A R A N C E S" in s:
                in_app = True
                continue
            if in_app and "S T I P U L A T I O N" in s:
                break
            if in_app and s.startswith("BY:") and "NOT PRESENT" not in s:
                if "[REVIEW:" not in s:
                    by_lines_unflagged.append(s[:80])
        record(
            "all appearances BY: lines carry [REVIEW:] flag (KB-017)",
            len(by_lines_unflagged) == 0,
            f"{len(by_lines_unflagged)} unflagged BY: lines: "
            + "; ".join(by_lines_unflagged[:3])
            if by_lines_unflagged else ""
        )
    else:
        record("corrected_text.txt exists for KB-017 check", False, "File not found")

    # ─────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    total   = len(results)
    passing = sum(1 for _, p, _ in results if p)
    failing = total - passing

    if failing == 0:
        print(f"  [PASS]  ALL {total} TESTS PASSED")
    else:
        print(f"  [FAIL]  {failing}/{total} TESTS FAILED")
        print("\n  Failed tests:")
        for name, passed, detail in results:
            if not passed:
                print(f"    - {name}")
                if detail:
                    print(f"      {detail}")

    print("=" * 60 + "\n")
    return failing


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Re-run format_final.py and build_mb_review_v2.py before testing"
    )
    args = parser.parse_args()

    os.chdir(BASE)

    if args.rebuild:
        rebuild()

    failures = run_tests()
    sys.exit(1 if failures else 0)

"""
compare_metrics.py
PURPOSE: Coarse sanity check — compare our FINAL.pdf against MB's approved PDF
         on pages, words, and characters before running detailed accuracy scoring.

USAGE:
    python compare_metrics.py
    python compare_metrics.py --ours FINAL_DELIVERY/FINAL.pdf --mb path/to/approved.pdf

PRINCIPLE: Coarsest check first. If pages/words/chars don't roughly match,
           line-by-line accuracy work is premature.
"""

import argparse
import os
import sys

def _find_our_pdf():
    """Find the FINAL.pdf in FINAL_DELIVERY — filename includes case_short prefix."""
    delivery = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FINAL_DELIVERY")
    if os.path.isdir(delivery):
        for f in os.listdir(delivery):
            if f.endswith("_FINAL.pdf") or f == "FINAL.pdf":
                return os.path.join(delivery, f)
    return os.path.join(delivery, "FINAL.pdf")  # fallback — will produce clear error

DEFAULT_OURS = _find_our_pdf()
DEFAULT_MB   = r"C:\Users\scott\Downloads\031326yellowrock-FINAL.pdf"

PAGE_TOLERANCE = 3     # pages
WORD_TOLERANCE = 0.03  # 3%
CHAR_TOLERANCE = 0.05  # 5%


def extract_metrics(pdf_path):
    """Return (pages, words, chars) from a PDF via pdfplumber."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)
        text  = "".join(p.extract_text() or "" for p in pdf.pages)
    words = len(text.split())
    chars = len(text)
    return pages, words, chars


def pct(a, b):
    return abs(a - b) / max(b, 1)


def run(ours_path, mb_path):
    for label, path in [("ours", ours_path), ("MB approved", mb_path)]:
        if not os.path.exists(path):
            print(f"[ERROR] {label} PDF not found: {path}")
            sys.exit(1)

    print(f"\nComparing:")
    print(f"  OURS : {ours_path}")
    print(f"  MB   : {mb_path}\n")

    our_pages, our_words, our_chars = extract_metrics(ours_path)
    mb_pages,  mb_words,  mb_chars  = extract_metrics(mb_path)

    results = []

    # Pages
    page_diff = our_pages - mb_pages
    page_ok   = abs(page_diff) <= PAGE_TOLERANCE
    results.append((
        "Pages",
        our_pages, mb_pages, f"{page_diff:+d}",
        f"±{PAGE_TOLERANCE}", page_ok,
        "structural issue likely" if not page_ok else ""
    ))

    # Words
    word_diff = our_words - mb_words
    word_ok   = pct(our_words, mb_words) <= WORD_TOLERANCE
    results.append((
        "Words",
        f"{our_words:,}", f"{mb_words:,}", f"{word_diff:+,}",
        f"±{int(WORD_TOLERANCE*100)}%", word_ok,
        "AI may have dropped or added content" if not word_ok else ""
    ))

    # Chars
    char_diff = our_chars - mb_chars
    char_ok   = pct(our_chars, mb_chars) <= CHAR_TOLERANCE
    results.append((
        "Chars",
        f"{our_chars:,}", f"{mb_chars:,}", f"{char_diff:+,}",
        f"±{int(CHAR_TOLERANCE*100)}%", char_ok,
        "formatting drift likely" if not char_ok else ""
    ))

    # Print table
    print(f"{'Metric':<8}  {'Ours':>10}  {'MB':>10}  {'Delta':>8}  {'Tolerance':<10}  Result")
    print("-" * 72)
    all_pass = True
    for metric, ours, mb, delta, tol, ok, note in results:
        status = "OK" if ok else "FAIL"
        if not ok:
            all_pass = False
        line = f"{metric:<8}  {str(ours):>10}  {str(mb):>10}  {str(delta):>8}  {tol:<10}  {status}"
        if note:
            line += f"  -- {note}"
        print(line)

    print()
    if all_pass:
        print("  [PASS] All coarse metrics within tolerance. Safe to run accuracy scorer.")
    else:
        print("  [FAIL] Fix structural issues above before running line-by-line accuracy.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coarse PDF metrics comparison")
    parser.add_argument("--ours", default=DEFAULT_OURS, help="Path to our FINAL.pdf")
    parser.add_argument("--mb",   default=DEFAULT_MB,   help="Path to MB approved PDF")
    args = parser.parse_args()
    sys.exit(run(args.ours, args.mb))

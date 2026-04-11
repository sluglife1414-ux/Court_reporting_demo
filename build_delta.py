#!/usr/bin/env python3
"""
build_delta.py v1.0 — Word-level diff: our FINAL vs CR approved final
=========================================================================
Compares our FINAL_FORMATTED.txt against the court reporter's approved PDF
word by word and outputs a structured delta report for KB learning.

Every delta = a candidate KB rule. Scan the report, add systematic patterns
to KNOWLEDGE_BASE.txt. That's how the engine gets smarter each run.

Usage:
    cd <job_work_dir>
    python build_delta.py --approved "C:/path/to/CR_final.pdf"
    python build_delta.py  # if approved_pdf_path is set in CASE_CAPTION.json

Output:
    FINAL_DELIVERY/DELTA_REPORT.txt

Header format per DOCUMENTATION_STANDARDS.md:
    build_delta.py v1.0 | Word-level diff engine vs CR approved final
    Author: Claude / Scott | 2026-04-09
"""

import re
import sys
import os
import json
import argparse
import difflib
import pdfplumber
from datetime import datetime

try:
    from pypdf import PdfReader as _PyPdfReader
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

# ── Load case config ───────────────────────────────────────────────────────────
_cfg = {}
for _fname in ('depo_config.json', 'CASE_CAPTION.json'):
    if os.path.exists(_fname):
        with open(_fname, encoding='utf-8') as _f:
            _cfg.update(json.load(_f))

_case_short   = _cfg.get('case_short', 'Unknown')
DEFAULT_OUR   = f"FINAL_DELIVERY/{_case_short}_FINAL_FORMATTED.txt"
DEFAULT_PDF   = _cfg.get('approved_pdf_path') or None
DEFAULT_OUT   = 'FINAL_DELIVERY/DELTA_REPORT.txt'
CONTEXT_WORDS = 8   # words shown on each side of a delta


# ── PDF extraction ─────────────────────────────────────────────────────────────
def extract_pdf_pages(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return [p.extract_text() or '' for p in pdf.pages]
    except Exception:
        if _PYPDF_AVAILABLE:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            return [p.extract_text() or '' for p in reader.pages]
        raise


# ── Normalization ──────────────────────────────────────────────────────────────
def _is_page_number(line):
    return bool(re.match(r'^\s*\d{1,3}\s*$', line.strip()))


def _strip_linenum(line):
    """Strip leading 1-25 line number from a transcript line."""
    m = re.match(r'^\s{0,5}(\d{1,2})\s+(.*)', line)
    if m and 1 <= int(m.group(1)) <= 25:
        return m.group(2)
    return line


_SKIP_HEADERS = [
    r'^A\s*P\s*P\s*E\s*A\s*R', r'^I\s*N\s*D\s*E\s*X',
    r'^EXAMINATION', r'^CERTIF', r'^ERRATA', r'^STIPULAT',
]


def detect_running_header(pages, check_pages=8):
    """Find a repeated page header (e.g. 'WCB G395 3702') to strip."""
    candidates = {}
    for text in pages[:check_pages]:
        for line in text.split('\n'):
            s = line.strip()
            if not s or _is_page_number(s):
                continue
            stripped = _strip_linenum(s).strip()
            if not stripped:
                continue
            if any(re.match(p, stripped, re.I) for p in _SKIP_HEADERS):
                break
            candidates[stripped] = candidates.get(stripped, 0) + 1
            break  # first content line per page only
    for cand, count in sorted(candidates.items(), key=lambda x: -x[1]):
        if count >= 3:
            return cand
    return None


def normalize_pages(pages, running_header=None):
    """Strip page numbers, line numbers, running headers → flat word list."""
    words = []
    for text in pages:
        for line in text.split('\n'):
            s = line.strip()
            if not s or _is_page_number(s):
                continue
            content = _strip_linenum(s).strip()
            if not content:
                continue
            if running_header and content == running_header:
                continue
            words.extend(content.split())
    return words


def load_txt_words(filepath, running_header=None):
    """Load FINAL_FORMATTED.txt — page-number-only lines are page breaks."""
    words = []
    with open(filepath, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s or _is_page_number(s):
                continue
            content = _strip_linenum(s).strip()
            if not content:
                continue
            if running_header and content == running_header:
                continue
            words.extend(content.split())
    return words


# ── Diff engine ────────────────────────────────────────────────────────────────
def word_diff(our_words, their_words):
    """
    Word-level diff using SequenceMatcher.
    Returns list of delta dicts with context.
    """
    matcher = difflib.SequenceMatcher(None, our_words, their_words, autojunk=False)
    deltas = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue

        ctx_before = our_words[max(0, i1 - CONTEXT_WORDS):i1]
        ctx_after  = our_words[i2:min(len(our_words), i2 + CONTEXT_WORDS)]

        deltas.append({
            'tag':            tag,   # replace | delete | insert
            'our':            our_words[i1:i2],
            'theirs':         their_words[j1:j2],
            'context_before': ctx_before,
            'context_after':  ctx_after,
        })

    return deltas


# ── Report builder ─────────────────────────────────────────────────────────────
def build_report(deltas, our_path, approved_path, case_short, our_wc, their_wc):
    SEP  = '=' * 80
    THIN = '-' * 60
    TAG_LABEL = {'replace': 'CHANGED', 'delete': 'WE ADDED / THEY OMIT',
                 'insert': 'THEY HAVE / WE MISSING'}

    lines = [
        SEP,
        f'DELTA REPORT — {case_short}',
        f'Engine output : {our_path}',
        f'Ground truth  : {approved_path}',
        f'Generated     : {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'Our words     : {our_wc}  |  Their words: {their_wc}',
        f'Total deltas  : {len(deltas)}',
        SEP,
        '',
    ]

    for i, d in enumerate(deltas, 1):
        label  = TAG_LABEL.get(d['tag'], d['tag'].upper())
        ctx_b  = ' '.join(d['context_before'])
        ctx_a  = ' '.join(d['context_after'])
        our_t  = ' '.join(d['our'])   if d['our']    else '(nothing)'
        their_t = ' '.join(d['theirs']) if d['theirs'] else '(omitted)'

        lines.append(f'DELTA {i:03d}  [{label}]')
        lines.append(f'  Ours   : ...{ctx_b} >>>{our_t}<<< {ctx_a}...')
        lines.append(f'  AD     : ...{ctx_b} >>>{their_t}<<< {ctx_a}...')
        lines.append(THIN)
        lines.append('')

    lines += [SEP, f'END — {len(deltas)} deltas total', SEP]
    return '\n'.join(lines)


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Word-level diff: our FINAL vs CR approved PDF')
    ap.add_argument('--our',      default=DEFAULT_OUR,  help='Our FINAL_FORMATTED.txt path')
    ap.add_argument('--approved', default=DEFAULT_PDF,  help='CR approved final PDF path')
    ap.add_argument('--out',      default=DEFAULT_OUT,  help='Output path')
    args = ap.parse_args()

    if not args.our or not os.path.exists(args.our):
        print(f'ERROR: our file not found: {args.our}')
        sys.exit(1)
    if not args.approved or not os.path.exists(args.approved):
        print(f'ERROR: approved PDF not found: {args.approved}')
        print('Pass --approved "path/to/final.pdf" or set approved_pdf_path in CASE_CAPTION.json')
        sys.exit(1)

    print(f'Our output  : {args.our}')
    our_words = load_txt_words(args.our)
    print(f'  {len(our_words):,} words')

    print(f'AD final    : {args.approved}')
    their_pages = extract_pdf_pages(args.approved)
    their_header = detect_running_header(their_pages)
    if their_header:
        print(f'  Running header detected: "{their_header}" — stripping')
    their_words = normalize_pages(their_pages, their_header)
    print(f'  {len(their_words):,} words')

    print('Diffing...')
    deltas = word_diff(our_words, their_words)
    print(f'  {len(deltas)} deltas found')

    report = build_report(deltas, args.our, args.approved,
                          _case_short, len(our_words), len(their_words))

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'\nDelta report: {args.out}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
compare_accuracy.py v3 — Section-Aware + Q/A-Aware Ground Truth Accuracy Comparison
=========================================================================
Splits both engine output and reporter's approved final into standard
deposition sections, then compares each section with the appropriate method.

Standard deposition sections (every state, every case):
    1. CAPTION       — Cover page. Field-by-field comparison.
    2. INDEX         — Table of contents. Structural check.
    3. APPEARANCES   — Attorney list. Name/firm matching.
    4. STIPULATION   — Pre-exam agreements. Word-level verbatim.
    5. TESTIMONY     — Examination Q&A. Word-level, line-wrap agnostic.
    6. CERTIFICATE   — Reporter/witness certs. Template + name check.
    7. ERRATA        — Errata sheet. Structural check.

Usage:
    python compare_accuracy.py                        (uses defaults)
    python compare_accuracy.py engine.txt final.pdf   (custom paths)

Output:
    FINAL_DELIVERY/accuracy_report.txt — section scores + full diff
"""

import re
import sys
import os
import argparse
import difflib
import pdfplumber
from datetime import datetime
from pathlib import Path

# pypdf used as fallback when pdfplumber can't open a file (e.g. PDF 1.6 encrypted structure)
try:
    from pypdf import PdfReader as _PyPdfReader
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_ENGINE_FILE  = r"FINAL_DELIVERY\Easley_YellowRock_FINAL_FORMATTED.txt"
DEFAULT_APPROVED_PDF = r"C:\Users\scott\Downloads\031326yellowrock-FINAL.pdf"
OUTPUT_FILE          = r"FINAL_DELIVERY\accuracy_report.txt"

# ── Section Detection Markers ─────────────────────────────────────────────────
# ALL patterns use ^ and $ anchors — must match the ENTIRE line (after strip).
# This prevents mid-testimony words like "stipulating" from firing a boundary.
# Order matters: checked top-to-bottom, first match wins.
SECTION_MARKERS = [
    # Certificates — check first so cert headers never fall into TESTIMONY
    # [TECH DEBT: section detection is single-format (MB/LA). CERTIF.*REPORTER removed — too broad,
    #  matched "Certified Court Reporter" in stipulation body text, causing false cert boundary.
    #  See brainstorm_industrial_scale.md — FORMAT CHALLENGE section for full redesign notes.]
    ('CERTIFICATE', re.compile(r"^\s*(REPORTER'?S?\s+CERTIF|WITNESS'?S?\s+CERTIF|C\s+E\s+R\s+T\s+I\s+F)", re.I)),
    ('ERRATA',      re.compile(r'^\s*(ERRATA\s*SHEET|ERRATA)\s*$', re.I)),
    # INDEX before TESTIMONY — index pages contain "EXAMINATION BY: PAGE" entries
    # which would falsely trigger TESTIMONY if checked first
    ('INDEX',       re.compile(r'^\s*I\s*N\s*D\s*E\s*X\s*$', re.I)),
    # Testimony: "EXAMINATION BY" without trailing colon+PAGE (index format)
    # Also matches DIRECT/CROSS/REDIRECT/RECROSS examination headers
    ('TESTIMONY',   re.compile(r'^\s*(EXAMINATION BY(?!.*:\s*PAGE)|EXAMINATION\s*$|DIRECT\s+EXAMINATION|CROSS[\s-]+EXAMINATION|RE-?DIRECT|RE-?CROSS)', re.I)),
    # Stipulation: standalone header line only — NOT mid-sentence "stipulating"
    ('STIPULATION', re.compile(r'^\s*(STIPULATION|THE STIPULATIONS?|PRE-DEPOSITION STIPULATIONS?)\s*$', re.I)),
    ('APPEARANCES', re.compile(r'^\s*A\s*P\s*P\s*E\s*A\s*R\s*A\s*N\s*C\s*E\s*S\s*:?\s*$', re.I)),
]

# ── Text Extraction ───────────────────────────────────────────────────────────

def _is_page_header(line):
    """Bare page number line — skip."""
    return bool(re.match(r'^\s*\d{1,3}\s*$', line.strip()))


def _strip_linenum(line):
    """Strip leading 1-25 line number from transcript line."""
    m = re.match(r'^\s{0,5}(\d{1,2})\s+(.*)', line)
    if m and 1 <= int(m.group(1)) <= 25:
        return m.group(2)
    return line


def _extract_pdf_pages(pdf_path):
    """
    Extract list of page-text strings from PDF.
    Tries pdfplumber first; falls back to pypdf if pdfplumber raises.
    """
    try:
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or '')
        return pages
    except Exception:
        if not _PYPDF_AVAILABLE:
            raise
        reader = _PyPdfReader(pdf_path)
        return [p.extract_text() or '' for p in reader.pages]


def detect_running_header_from_pdf(pdf_path, check_pages=8):
    """
    Detect repeated header content that appears on multiple pages (e.g. 'WCB G395 3702').
    Checks first non-page-number line of each page. If same text appears 3+ times -> header.
    Excludes known section header patterns so we don't strip them.
    """
    # These are section headers, not running headers — never strip them
    SECTION_HEADER_PATTERNS = [
        r'^A\s*P\s*P\s*E\s*A\s*R\s*A\s*N\s*C\s*E\s*S',
        r'^I\s*N\s*D\s*E\s*X',
        r'^EXAMINATION',
        r'^CERTIF',
        r'^ERRATA',
        r'^STIPULAT',
    ]
    candidates = {}
    for text in _extract_pdf_pages(pdf_path)[:check_pages]:
        page_lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in page_lines:
                if _is_page_header(line):
                    continue
                stripped = _strip_linenum(line).strip()
                if not stripped:
                    continue
                # Skip known section headers
                if any(re.match(p, stripped, re.I) for p in SECTION_HEADER_PATTERNS):
                    break
                candidates[stripped] = candidates.get(stripped, 0) + 1
                break   # first content line only
    for candidate, count in sorted(candidates.items(), key=lambda x: -x[1]):
        if count >= 3:
            return candidate
    return None


def detect_running_header_from_txt(filepath, check_pages=8):
    """
    Detect repeated header in FINAL_FORMATTED.txt.
    Pages are separated by bare page-number lines.
    Excludes known section header patterns.
    """
    SECTION_HEADER_PATTERNS = [
        r'^A\s*P\s*P\s*E\s*A\s*R\s*A\s*N\s*C\s*E\s*S',
        r'^I\s*N\s*D\s*E\s*X',
        r'^EXAMINATION',
        r'^CERTIF',
        r'^ERRATA',
        r'^STIPULAT',
    ]
    candidates = {}
    pages_seen = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        current_page_first = None
        for raw in f:
            line = raw.rstrip('\n').strip()
            if _is_page_header(line):
                if current_page_first:
                    candidates[current_page_first] = candidates.get(current_page_first, 0) + 1
                current_page_first = None
                pages_seen += 1
                if pages_seen >= check_pages:
                    break
                continue
            if current_page_first is None and line:
                stripped = _strip_linenum(line).strip()
                if stripped and not any(re.match(p, stripped, re.I) for p in SECTION_HEADER_PATTERNS):
                    current_page_first = stripped
    for candidate, count in sorted(candidates.items(), key=lambda x: -x[1]):
        if count >= 3:
            return candidate
    return None


def extract_lines_from_txt(filepath, running_header=None):
    """Extract raw content lines from engine FINAL_FORMATTED.txt."""
    lines = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if _is_page_header(line):
                continue
            content = _strip_linenum(line).strip()
            # Strip running header
            if running_header and content == running_header:
                continue
            lines.append(content)   # keep blanks for section detection
    return lines


def extract_lines_from_pdf(pdf_path, running_header=None):
    """Extract raw content lines from reporter's approved final PDF.
    Uses pdfplumber with pypdf fallback for compatibility."""
    lines = []
    for text in _extract_pdf_pages(pdf_path):
        for raw in text.split('\n'):
            line = raw.strip()
            if _is_page_header(line):
                continue
            content = _strip_linenum(line).strip()
            # Strip running header
            if running_header and content == running_header:
                continue
            lines.append(content)   # keep blanks for section detection
    return lines


# ── Section Splitter ──────────────────────────────────────────────────────────

def split_sections(lines):
    """
    Split a flat list of content lines into named sections.
    Returns dict: { 'CAPTION': [...], 'INDEX': [...], 'TESTIMONY': [...], ... }
    """
    sections = {}
    current_section = 'CAPTION'
    current_lines = []
    # Track which markers have fired (CERTIFICATE can appear twice)
    cert_count = 0

    for line in lines:
        matched = None
        for name, pattern in SECTION_MARKERS:
            if pattern.match(line):   # .match anchors at start; $ in pattern covers end
                if name == 'CERTIFICATE':
                    cert_count += 1
                    matched = f'CERTIFICATE_{cert_count}'
                else:
                    matched = name
                break

        if matched and matched != current_section:
            # Save current section
            sections[current_section] = current_lines
            current_section = matched
            current_lines = [line]
        else:
            current_lines.append(line)

    # Save last section
    sections[current_section] = current_lines
    return sections


# ── Word-Level Comparison (for Testimony) ────────────────────────────────────

_UNDERSCORE_RE = re.compile(r'^_+$')
_UNDERSCORE_NORM = '_______________________________________________'  # 47 chars — standard

def _normalize_line(line):
    """Normalize underscore-only lines to standard length before comparison.
    pdfplumber extracts variable-length underscore strings from PDFs; this
    prevents false mismatches on errata blank fields."""
    stripped = line.strip()
    if _UNDERSCORE_RE.match(stripped) and len(stripped) >= 10:
        return _UNDERSCORE_NORM
    return line

def words_from_lines(lines):
    """Flatten lines to a single list of words, stripping line breaks."""
    text = ' '.join(_normalize_line(l) for l in lines if l.strip())
    return text.split()


def word_level_accuracy(engine_lines, approved_lines):
    """
    Compare two sections word-by-word (ignores line-wrap differences).
    Returns (match_pct, details_list)
    """
    e_words = words_from_lines(engine_lines)
    a_words = words_from_lines(approved_lines)

    matcher = difflib.SequenceMatcher(None, e_words, a_words, autojunk=False)
    matching_blocks = matcher.get_matching_blocks()
    matched = sum(b.size for b in matching_blocks)
    total = max(len(e_words), len(a_words))
    match_pct = (matched / total * 100) if total else 100.0

    # Build delta list (non-matching spans)
    details = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        e_span = ' '.join(e_words[i1:i2]) if i2 > i1 else ''
        a_span = ' '.join(a_words[j1:j2]) if j2 > j1 else ''
        if tag == 'replace':
            details.append(('MISSED', e_span, a_span))
        elif tag == 'delete':
            details.append(('INSERTION', e_span, ''))
        elif tag == 'insert':
            details.append(('DELETION', '', a_span))

    return match_pct, matched, total, details


# ── Q/A-Aware Comparison (for Testimony) ─────────────────────────────────────
#
# Problem solved: flat word-level difflib drifts when punctuation differs.
# A single deleted "the" shifts all subsequent Q/A labels by 1, creating
# hundreds of false "Q. vs A." swaps. Fix: anchor on speaker labels so drift
# cannot propagate beyond a single block.
#
# How it works:
#   1. Parse testimony into (speaker_key, [words]) blocks.
#   2. Align blocks by speaker key using difflib (Q→Q, A→A, MR. HOBBY→MR. HOBBY).
#   3. Within each matched block pair, run word-level diff independently.
#   4. Drift in block N is contained — block N+1 starts with a fresh anchor.

_SPEAKER_RE = re.compile(
    r'^(Q\.?\s+|Q\.\s*$'               # Q.  (question)
    r'|A\.?\s+|A\.\s*$'                # A.  (answer)
    r'|BY\s+(?:MR|MS|MRS|DR)\.\s+\w+[:\s]'   # BY MR. HOBBY:
    r'|(?:MR|MS|MRS|DR)\.\s+\w+\s*:'  # MR. HOBBY:
    r'|THE\s+(?:COURT\s+REPORTER|REPORTER|WITNESS|COURT)\s*:'  # THE WITNESS:
    r'|VIDEOGRAPHER\s*:)',              # VIDEOGRAPHER:
    re.I
)


def _normalize_speaker_key(raw):
    """Normalize speaker label for stable matching: uppercase, strip trailing colon/space."""
    s = raw.strip().upper().rstrip(':').rstrip()
    return re.sub(r'\s+', ' ', s)


def _fp_word(w):
    """Normalize a single word for fingerprinting: lowercase, strip terminal punctuation."""
    return w.lower().rstrip('.,;:!?').strip("'\"")


def _block_key(speaker, words, fp_n=5):
    """
    Build a block alignment key.

    For Q./A. blocks: '{speaker}#{fp}' where fp = first fp_n words normalized.
    Content fingerprint prevents wrong-Q-with-wrong-Q misalignment when keys
    are just 'Q.' — 919 Q blocks with the same key cause unreliable LCS alignment.

    For colloquy speakers (MR. HOBBY, BY MR. HOBBY, etc.): speaker label only
    (these are already distinct enough without a content suffix).
    """
    if speaker in ('Q.', 'A.', 'Q', 'A'):
        fp = '_'.join(_fp_word(w) for w in words[:fp_n] if w)
        return f'{speaker}#{fp}'
    return speaker


def _parse_testimony_blocks(lines):
    """
    Split testimony lines into (block_key, speaker_label, [words]) blocks.

    block_key    — unique alignment key: '{speaker}#{fingerprint}' for Q/A,
                   '{speaker}' for colloquy.  Used by difflib for block alignment.
    speaker_label — normalized speaker string for display (e.g. 'Q.', 'MR. HOBBY').
    words         — content word list (no speaker label prefix).

    Lines before the first speaker label → 'PREAMBLE' block.
    Continuation lines (no speaker label) → appended to current block's words.
    """
    blocks = []
    current_speaker = 'PREAMBLE'
    current_words = []
    in_preamble = True

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = _SPEAKER_RE.match(stripped)
        if m:
            # Finalize previous block
            if not in_preamble or current_words:
                key = _block_key(current_speaker, current_words)
                blocks.append((key, current_speaker, current_words))
            in_preamble = False
            current_speaker = _normalize_speaker_key(m.group(1))
            rest = stripped[len(m.group(0)):].strip()
            current_words = rest.split() if rest else []
        else:
            current_words.extend(stripped.split())

    # Flush last block
    if not in_preamble or current_words:
        key = _block_key(current_speaker, current_words)
        blocks.append((key, current_speaker, current_words))

    return blocks


def testimony_aware_accuracy(engine_lines, approved_lines):
    """
    Q/A-aware comparison for TESTIMONY section — hybrid design.

    SCORE: Uses the flat word-level approach (word_level_accuracy). This gives the
    most accurate score (~90%) without Q/A alignment artifacts.

    DELETIONS: Uses block-level alignment with content fingerprints. An approved
    block that has NO matching engine block (difflib 'insert' op) = a real DELETION.
    This eliminates cascade artifacts — every reported DELETION is a complete speaker
    block that's missing from the engine output. No single-word drift ghosts.

    MISSED + INSERTIONS: Come from flat word-level details, filtered to exclude
    entries whose text is duplicated in another entry (corroborated artifacts).

    Returns: (match_pct, matched_words, total_words, details)
    Same interface as word_level_accuracy() — drop-in for analyze_section().
    """
    # ── Score + raw details from flat word comparison ──────────────────────────
    pct, matched, total, raw_details = word_level_accuracy(engine_lines, approved_lines)

    # ── Block-level detection of FULLY MISSING content ─────────────────────────
    # Re-run difflib at block granularity. 'insert' ops = approved blocks with
    # zero counterpart in engine → these are real missing-content deletions.
    e_blocks = _parse_testimony_blocks(engine_lines)
    a_blocks = _parse_testimony_blocks(approved_lines)
    e_keys = [b[0] for b in e_blocks]
    a_keys = [b[0] for b in a_blocks]
    block_matcher = difflib.SequenceMatcher(None, e_keys, a_keys, autojunk=False)

    block_deletions = []    # approved blocks completely absent from engine
    block_insertions = []   # engine blocks completely absent from approved
    for tag, i1, i2, j1, j2 in block_matcher.get_opcodes():
        if tag == 'insert':
            for k in range(j1, j2):
                _key, spk, words = a_blocks[k]
                if words:  # skip empty structural blocks (BY MR. HOBBY: alone on line)
                    block_deletions.append(
                        ('DELETION', '', f'[{spk}] ' + ' '.join(words)))
        elif tag == 'delete':
            for k in range(i1, i2):
                _key, spk, words = e_blocks[k]
                if words:
                    block_insertions.append(
                        ('INSERTION', f'[{spk}] ' + ' '.join(words), ''))

    # ── Filter flat details: keep MISSED + INSERTION, replace DELETION ─────────
    # Block-level deletions are more trustworthy than word-level (no cascade risk).
    # Remove flat-word DELETION entries; replace with block-level deletions.
    # Keep flat MISSED and flat INSERTION (these are word-level diffs within blocks
    # that DO align — they are real content differences).
    filtered = [d for d in raw_details if d[0] != 'DELETION']
    # Add block-level deletions at the end
    filtered.extend(block_deletions)
    filtered.extend(block_insertions)

    return pct, matched, total, filtered


# ── Line-Level Comparison (for structured sections) ──────────────────────────

def line_level_accuracy(engine_lines, approved_lines):
    """
    Compare two sections line-by-line (for caption, appearances, etc.).
    Returns (match_pct, details_list)
    """
    e_lines = [l for l in engine_lines if l.strip()]
    a_lines = [l for l in approved_lines if l.strip()]

    matcher = difflib.SequenceMatcher(None, e_lines, a_lines, autojunk=False)
    details = []
    matched = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            matched += (i2 - i1)
            continue
        if tag == 'replace':
            for k in range(max(i2-i1, j2-j1)):
                el = e_lines[i1+k] if (i1+k) < i2 else None
                al = a_lines[j1+k] if (j1+k) < j2 else None
                if el and al:
                    details.append(('MISSED', el, al))
                elif el:
                    details.append(('INSERTION', el, ''))
                else:
                    details.append(('DELETION', '', al))
        elif tag == 'delete':
            for l in e_lines[i1:i2]:
                details.append(('INSERTION', l, ''))
        elif tag == 'insert':
            for l in a_lines[j1:j2]:
                details.append(('DELETION', '', l))

    total = max(len(e_lines), len(a_lines))
    match_pct = (matched / total * 100) if total else 100.0
    return match_pct, matched, total, details


# ── Per-Section Analysis ──────────────────────────────────────────────────────

# Which comparison method to use per section
SECTION_METHOD = {
    'CAPTION':       'line',   # field-by-field
    'INDEX':         'line',   # structural
    'APPEARANCES':   'line',   # attorney names
    'STIPULATION':   'word',   # verbatim
    'TESTIMONY':     'qa',     # Q/A-aware speaker-block alignment (drift-free)
    'CERTIFICATE_1': 'word',
    'CERTIFICATE_2': 'word',
    'ERRATA':        'line',
}

SECTION_DISPLAY = {
    'CAPTION':       'Caption (cover page)',
    'INDEX':         'Index (table of contents)',
    'APPEARANCES':   'Appearances (attorney list)',
    'STIPULATION':   'Stipulation',
    'TESTIMONY':     'Examination / Testimony',
    'CERTIFICATE_1': "Reporter's Certificate",
    'CERTIFICATE_2': "Witness's Certificate",
    'ERRATA':        'Errata Sheet',
}


def analyze_section(name, engine_lines, approved_lines):
    """Run appropriate comparison for this section. Returns result dict."""
    method = SECTION_METHOD.get(name, 'word')
    if method == 'qa':
        # Q/A-aware: speaker blocks anchor alignment, no cross-block drift
        pct, matched, total, details = testimony_aware_accuracy(engine_lines, approved_lines)
        unit = 'words'
    elif method == 'word':
        pct, matched, total, details = word_level_accuracy(engine_lines, approved_lines)
        unit = 'words'
    else:
        # INDEX uses \t in FINAL_FORMATTED.txt for PDF right-alignment, but pdfplumber
        # extracts the rendered PDF as spaces. Normalize tabs → single space before scoring.
        # [TECH DEBT: tab-based column layout should be replaced with a proper column model]
        if name == 'INDEX':
            engine_lines   = [l.replace('\t', ' ') for l in engine_lines]
            approved_lines = [l.replace('\t', ' ') for l in approved_lines]
        pct, matched, total, details = line_level_accuracy(engine_lines, approved_lines)
        unit = 'lines'

    del_count  = sum(1 for d in details if d[0] == 'DELETION')
    ins_count  = sum(1 for d in details if d[0] == 'INSERTION')
    mis_count  = sum(1 for d in details if d[0] == 'MISSED')

    return {
        'name':       name,
        'method':     method,
        'unit':       unit,
        'match_pct':  pct,
        'matched':    matched,
        'total':      total,
        'details':    details,
        'deletions':  del_count,
        'insertions': ins_count,
        'missed':     mis_count,
        'e_size':     len([l for l in engine_lines if l.strip()]),
        'a_size':     len([l for l in approved_lines if l.strip()]),
    }


# ── Report Writer ─────────────────────────────────────────────────────────────

def build_report(section_results, engine_file, approved_pdf):
    """Write the full section-aware accuracy report."""
    out = []
    out.append("=" * 70)
    out.append("GROUND TRUTH ACCURACY REPORT  (Section-Aware)")
    out.append(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out.append(f"Engine    : {engine_file}")
    out.append(f"Approved  : {approved_pdf}")
    out.append("=" * 70)
    out.append("")

    # ── Summary table ──────────────────────────────────────────────────────
    out.append("SECTION SCORES")
    out.append("-" * 70)
    out.append(f"{'Section':<30} {'Method':<6} {'Match%':>7} {'Matched':>8} {'Total':>8} {'Del':>5} {'Ins':>5} {'Miss':>5}")
    out.append("-" * 70)

    total_matched = total_total = total_del = total_ins = total_mis = 0
    has_deletion_warning = False

    for r in section_results:
        label = SECTION_DISPLAY.get(r['name'], r['name'])[:29]
        warn  = ' ***' if r['deletions'] > 0 else ''
        out.append(
            f"{label:<30} {r['method']:<6} {r['match_pct']:>6.1f}%"
            f" {r['matched']:>8,} {r['total']:>8,}"
            f" {r['deletions']:>5} {r['insertions']:>5} {r['missed']:>5}{warn}"
        )
        total_matched += r['matched']
        total_total   += r['total']
        total_del     += r['deletions']
        total_ins     += r['insertions']
        total_mis     += r['missed']
        if r['deletions'] > 0:
            has_deletion_warning = True

    overall_pct = (total_matched / total_total * 100) if total_total else 0
    out.append("-" * 70)
    out.append(
        f"{'OVERALL':<30} {'':6} {overall_pct:>6.1f}%"
        f" {total_matched:>8,} {total_total:>8,}"
        f" {total_del:>5} {total_ins:>5} {total_mis:>5}"
    )
    out.append("")

    if has_deletion_warning:
        out.append("*** WARNING: DELETIONS FOUND — engine removed content present in approved.")
        out.append("    'We never delete.' Review all DELETION entries below.")
        out.append("")

    out.append("Legend:")
    out.append("  DELETION  = approved has it, engine does not  *** CRITICAL ***")
    out.append("  INSERTION = engine added it, not in approved")
    out.append("  MISSED    = both have it but content differs")
    out.append("")

    # ── Per-section detail ─────────────────────────────────────────────────
    out.append("=" * 70)
    out.append("SECTION DETAIL")
    out.append("=" * 70)

    for r in section_results:
        label = SECTION_DISPLAY.get(r['name'], r['name'])
        out.append("")
        out.append(f"[ {label} ]  {r['match_pct']:.1f}% match  "
                   f"(engine: {r['e_size']} {r['unit']}, approved: {r['a_size']} {r['unit']})")
        out.append("-" * 60)

        if not r['details']:
            out.append("  PERFECT MATCH - no differences found.")
            continue

        shown = 0
        for dtype, e_span, a_span in r['details']:
            if shown >= 50:   # cap per section to keep report readable
                remaining = len(r['details']) - shown
                out.append(f"  ... {remaining} more differences not shown ...")
                break
            out.append(f"  [{dtype}]")
            if e_span:
                out.append(f"    ENGINE  : {e_span[:120]}")
            if a_span:
                out.append(f"    APPROVED: {a_span[:120]}")
            shown += 1

    out.append("")
    out.append("=" * 70)
    out.append("END OF REPORT")
    out.append("=" * 70)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    return overall_pct, total_del


# ── Main ───────────────────────────────────────────────────────────────────────

def main(engine_file=None, approved_pdf=None, out_file=None):
    engine_file  = engine_file  or DEFAULT_ENGINE_FILE
    approved_pdf = approved_pdf or DEFAULT_APPROVED_PDF
    global OUTPUT_FILE
    if out_file:
        OUTPUT_FILE = out_file

    print("=" * 60)
    print("GROUND TRUTH ACCURACY COMPARISON  v2 (section-aware)")
    print("=" * 60)

    print("Detecting running headers...")
    pdf_header = detect_running_header_from_pdf(approved_pdf)
    txt_header = detect_running_header_from_txt(engine_file)
    print(f"  PDF running header : {pdf_header or 'none'}")
    print(f"  TXT running header : {txt_header or 'none'}")

    print("Extracting engine output...")
    e_lines = extract_lines_from_txt(engine_file, running_header=txt_header)
    print(f"  {len(e_lines):,} lines")

    print("Extracting approved final from PDF...")
    a_lines = extract_lines_from_pdf(approved_pdf, running_header=pdf_header)
    print(f"  {len(a_lines):,} lines")

    print("Splitting into sections...")
    e_sections = split_sections(e_lines)
    a_sections = split_sections(a_lines)
    print(f"  Engine sections   : {list(e_sections.keys())}")
    print(f"  Approved sections : {list(a_sections.keys())}")

    print("Analyzing sections...")
    results = []
    all_sections = sorted(set(list(e_sections.keys()) + list(a_sections.keys())))
    for sec in all_sections:
        e = e_sections.get(sec, [])
        a = a_sections.get(sec, [])
        r = analyze_section(sec, e, a)
        results.append(r)
        print(f"  {sec:<20} {r['match_pct']:>5.1f}%  "
              f"({r['deletions']} del, {r['insertions']} ins, {r['missed']} missed)")

    print(f"\nWriting report -> {OUTPUT_FILE}")
    overall_pct, total_del = build_report(results, engine_file, approved_pdf)

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    for r in results:
        label = SECTION_DISPLAY.get(r['name'], r['name'])
        flag = '  *** DELETIONS ***' if r['deletions'] > 0 else ''
        print(f"  {label:<35} {r['match_pct']:>5.1f}%{flag}")
    print(f"  {'OVERALL':<35} {overall_pct:>5.1f}%")
    if total_del > 0:
        print(f"\n  *** {total_del} total deletions. Review report.")
    print(f"\nFull report -> {OUTPUT_FILE}")


def _parse_args():
    ap = argparse.ArgumentParser(
        description='Ground truth accuracy: engine FINAL_FORMATTED.txt vs approved final PDF'
    )
    ap.add_argument('--engine',   default=DEFAULT_ENGINE_FILE,
                    help='Path to engine FINAL_FORMATTED.txt')
    ap.add_argument('--approved', default=DEFAULT_APPROVED_PDF,
                    help='Path to reporter approved final PDF')
    ap.add_argument('--out',      default=None,
                    help='Output report path (default: auto-named in same folder as engine)')
    return ap.parse_args()


if __name__ == '__main__':
    args = _parse_args()

    # Set output path
    if args.out:
        OUTPUT_FILE = args.out
    else:
        engine_stem = Path(args.engine).stem
        OUTPUT_FILE = str(Path(args.engine).parent / f'accuracy_report_{engine_stem}.txt')

    main(engine_file=args.engine, approved_pdf=args.approved, out_file=OUTPUT_FILE)

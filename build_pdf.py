"""
build_pdf.py — Convert formatted deposition text to professional PDF.

Matches Louisiana court reporter final transcript format per:
  - Louisiana Administrative Code Title 46, §XXI-1101
  - LABCSR published sample transcript PDFs
  - Measured from real Cox/YellowRock depo PDF

Multi-state support via state_config.py (--state LA/NY/NJ)

Usage:
    python build_pdf.py              # defaults to LA
    python build_pdf.py --state NY
"""
import re
import sys
import os

# Allow running from worktree or main project dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors

import json
from state_config import get_config

# --- Load case config ---
# CASE_CAPTION.json is authoritative — overrides depo_config.json (matches format_final.py logic)
with open('depo_config.json', encoding='utf-8') as _f:
    _cfg = json.load(_f)
if os.path.exists('CASE_CAPTION.json'):
    with open('CASE_CAPTION.json', encoding='utf-8') as _cf:
        _cfg.update(json.load(_cf))
CASE_SHORT = _cfg.get('case_short', 'Unknown_Case')

# --- State selection (from depo_config or --state flag) ---
_court = _cfg.get('court', '').upper()
STATE = _cfg.get('state', 'LA').upper()  # trust explicit state field in depo_config.json
for i, arg in enumerate(sys.argv[1:]):
    if arg == '--state' and i + 1 < len(sys.argv) - 1:
        STATE = sys.argv[i + 2].upper()

CFG = get_config(STATE)

INPUT_TXT  = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL_FORMATTED.txt'
OUTPUT_PDF = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL.pdf'

# Fallback: if expected file doesn't exist, scan FINAL_DELIVERY for any *_FINAL_FORMATTED.txt
# This handles mismatches between depo_config.json case_short and format_final.py output name
if not os.path.exists(INPUT_TXT):
    import glob as _glob
    # Exclude accuracy_report_* files — those are scoring artifacts, not transcript inputs
    _candidates = [f for f in _glob.glob('FINAL_DELIVERY/*_FINAL_FORMATTED.txt')
                   if not os.path.basename(f).startswith('accuracy_report_')]
    if len(_candidates) == 1:
        INPUT_TXT = _candidates[0]
        _found_short = os.path.basename(INPUT_TXT).replace('_FINAL_FORMATTED.txt', '')
        OUTPUT_PDF = f'FINAL_DELIVERY/{_found_short}_FINAL.pdf'
        print(f"[build_pdf] WARNING: case_short mismatch — expected '{CASE_SHORT}', found '{_found_short}'")
        print(f"[build_pdf] Using: {INPUT_TXT}")
        print(f"[build_pdf] Fix: align case_short in depo_config.json with format_final.py")
    elif len(_candidates) > 1:
        print(f"[build_pdf] ERROR: Multiple FINAL_FORMATTED files found, cannot auto-resolve:")
        for c in _candidates: print(f"  {c}")
        sys.exit(1)

# --- Page geometry from config ---
PAGE_W         = CFG['page_w']
PAGE_H         = CFG['page_h']
MARGIN_TOP     = CFG['margin_top']
MARGIN_BOTTOM  = CFG['margin_bottom']
MARGIN_LEFT    = CFG['margin_left']
MARGIN_RIGHT   = CFG['margin_right']
FONT_NAME      = CFG['font']
FONT_BOLD      = CFG['font_bold']
FONT_SIZE      = CFG['font_size']
LINE_SPACING   = CFG['line_spacing']
LINENUM_X      = CFG['linenum_x']
TEXT_X         = CFG['text_x']
TEXT_RIGHT     = PAGE_W - MARGIN_RIGHT
TEXT_TOP       = PAGE_H - MARGIN_TOP
LINES_PER_PAGE = CFG['lines_per_page']
PAGENUM_Y      = PAGE_H - CFG['pagenum_from_top']   # upper right, per spec
DRAW_VERT_LINE = CFG['vert_line']


_SUBROW = '\x00'   # sentinel prefix that marks an appearances sub-row in text_lines


def parse_formatted_txt(path):
    """
    Parse the formatted .txt file into a list of pages.
    Each page is a dict: {num: int, lines: [str], doubled: bool}

    Standard pages: lines has 25 strings (one per numbered line).
    Doubled pages (appearances): lines has up to 50 strings — numbered lines
    interleaved with sub-rows.  Sub-rows are prefixed with _SUBROW so
    draw_page can render them at y - LINE_SPACING/2 below their parent line.
    """
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    raw_pages = re.split(r'\n\n+', content.strip())
    pages = []

    for block in raw_pages:
        block_lines = block.split('\n')
        if not block_lines:
            continue

        # First line is the page number
        try:
            pnum = int(block_lines[0].strip())
        except ValueError:
            continue

        text_lines = []
        for line in block_lines[1:]:
            m = re.match(r'^\s*(\d{1,2})\s{1,4}(.*)', line)
            if m:
                text_lines.append(m.group(2).rstrip())
            elif line.startswith('    ') and line.strip():
                # 4-space-indented non-numbered line = appearances sub-row
                text_lines.append(_SUBROW + line[4:].rstrip())
            else:
                text_lines.append('')

        doubled = any(l.startswith(_SUBROW) for l in text_lines)

        # Pad standard pages to LINES_PER_PAGE; doubled pages may have more rows
        if not doubled:
            while len(text_lines) < LINES_PER_PAGE:
                text_lines.append('')
            text_lines = text_lines[:LINES_PER_PAGE]

        pages.append({'num': pnum, 'lines': text_lines, 'doubled': doubled})

    return pages


def draw_page(c, page_data):
    """Draw one full page of the deposition transcript."""
    pnum  = page_data['num']
    lines = page_data['lines']

    # --- Page number: upper RIGHT, per LA spec (0.35" from top) ---
    c.setFont(FONT_NAME, FONT_SIZE)
    c.drawRightString(TEXT_RIGHT, PAGENUM_Y, str(pnum))

    # --- Vertical black line (all pages EXCEPT front matter) ---
    # MB format: double bar on testimony, certificates, and errata pages.
    # Suppressed only on caption/index/appearances/stipulation (front matter).
    FRONT_MATTER_MARKERS = (
        'STATE OF LOUISIANA',
        'I N D E X',
        'A P P E A R A N C E S',
        'S T I P U L A T I O N',
    )
    is_front_matter = any(
        any(marker in ln for marker in FRONT_MATTER_MARKERS)
        for ln in lines
    )
    is_testimony = DRAW_VERT_LINE and not is_front_matter
    if is_testimony:
        first_line_y = TEXT_TOP - LINE_SPACING
        last_line_y  = TEXT_TOP - LINE_SPACING - ((LINES_PER_PAGE - 1) * LINE_SPACING)
        y_top = first_line_y + (FONT_SIZE * 0.3)
        y_bot = last_line_y  - (FONT_SIZE * 0.3)
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.0)
        # Double vertical line — MB format standard
        line_x1 = TEXT_X - 0.10 * inch
        line_x2 = TEXT_X - 0.05 * inch
        c.line(line_x1, y_top, line_x1, y_bot)
        c.line(line_x2, y_top, line_x2, y_bot)

    def _draw_text(text, y):
        """Render one text line at the given y-coordinate (shared by main and sub-rows)."""
        if not text.strip():
            return
        c.setFont(FONT_NAME, FONT_SIZE)
        if '\t' in text:
            parts  = text.split('\t')
            label  = parts[0]
            number = parts[-1].strip()
            if label.strip():
                c.drawString(TEXT_X, y, label)
            if number:
                c.drawRightString(TEXT_RIGHT, y, number)
        else:
            qa_match = re.match(r'^(\s*)(Q\.|A\.)(\s+.*)$', text)
            if qa_match:
                prefix  = qa_match.group(1)
                label   = qa_match.group(2)
                rest    = qa_match.group(3)
                char_w  = FONT_SIZE * 0.6
                x_label = TEXT_X + len(prefix) * char_w
                c.setFont(FONT_BOLD, FONT_SIZE)
                c.drawString(x_label, y, label)
                c.setFont(FONT_NAME, FONT_SIZE)
                c.drawString(x_label + len(label) * char_w, y, rest)
            else:
                leading  = len(text) - len(text.lstrip())
                trailing = len(text) - len(text.rstrip())
                is_centered = (leading >= 8 and abs(leading - trailing) <= 2)
                if is_centered:
                    c.drawCentredString(PAGE_W / 2, y, text.strip())
                else:
                    max_chars = int((TEXT_RIGHT - TEXT_X) / (FONT_SIZE * 0.6)) + 5
                    c.drawString(TEXT_X, y, text[:max_chars])

    # --- Numbered lines (25 slots) ---
    # For doubled pages (appearances), each slot may have a sub-row rendered
    # 13pt below the main row — matching MB's two-text-row-per-slot layout.
    doubled = page_data.get('doubled', False)
    idx   = 0
    slot  = 0
    while slot < LINES_PER_PAGE and idx < len(lines):
        text = lines[idx]

        # Sub-rows in wrong position (shouldn't occur) — skip
        if text.startswith(_SUBROW):
            idx += 1
            continue

        line_y = TEXT_TOP - LINE_SPACING - (slot * LINE_SPACING)

        # Line number
        c.setFont(FONT_NAME, FONT_SIZE)
        c.drawRightString(LINENUM_X + 0.28 * inch, line_y, str(slot + 1))

        _draw_text(text, line_y)
        idx  += 1
        slot += 1

        # Peek: if next entry is a sub-row, render it 13pt below the main row
        if doubled and idx < len(lines) and lines[idx].startswith(_SUBROW):
            sub_text = lines[idx][len(_SUBROW):]
            _draw_text(sub_text, line_y - LINE_SPACING / 2)
            idx += 1


def build_pdf(pages):
    """Render all pages to PDF."""
    c = canvas.Canvas(OUTPUT_PDF, pagesize=(PAGE_W, PAGE_H))
    _witness   = _cfg.get('witness_name', 'UNKNOWN')
    _depo_date = _cfg.get('depo_date', 'UNKNOWN')
    _reporter  = _cfg.get('reporter_name', 'UNKNOWN')
    _depo_type = _cfg.get('depo_type', 'Deposition')
    c.setTitle(f"{CASE_SHORT} — {_depo_type} of {_witness}")
    c.setAuthor(_reporter)
    c.setSubject(f"{_depo_type} of {_witness} — {_depo_date}")

    for page_data in pages:
        draw_page(c, page_data)
        c.showPage()

    c.save()
    print(f"[build_pdf] PDF written: {OUTPUT_PDF}")
    print(f"[build_pdf] Total pages: {len(pages)}")
    print(f"[build_pdf] State format: {STATE}")


def main():
    print(f"[build_pdf] Reading {INPUT_TXT}...")
    pages = parse_formatted_txt(INPUT_TXT)
    print(f"[build_pdf] Parsed {len(pages)} pages")

    if not pages:
        print("ERROR: No pages parsed. Check input file.")
        return

    print(f"[build_pdf] First page: {pages[0]['num']} — '{pages[0]['lines'][0][:60]}'")
    print(f"[build_pdf] Last page:  {pages[-1]['num']}")

    build_pdf(pages)


if __name__ == '__main__':
    main()

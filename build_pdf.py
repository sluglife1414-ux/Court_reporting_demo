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

from state_config import get_config

# --- State selection ---
STATE = 'LA'
for i, arg in enumerate(sys.argv[1:]):
    if arg == '--state' and i + 1 < len(sys.argv) - 1:
        STATE = sys.argv[i + 2].upper()

CFG = get_config(STATE)

INPUT_TXT  = 'FINAL_DELIVERY/Easley_YellowRock_FINAL_FORMATTED.txt'
OUTPUT_PDF = f'FINAL_DELIVERY/Easley_YellowRock_FINAL.pdf'

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


def parse_formatted_txt(path):
    """
    Parse the formatted .txt file into a list of pages.
    Each page is a dict: {num: int, lines: [str x 25]}
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
            else:
                text_lines.append('')

        # Pad to LINES_PER_PAGE
        while len(text_lines) < LINES_PER_PAGE:
            text_lines.append('')

        pages.append({'num': pnum, 'lines': text_lines[:LINES_PER_PAGE]})

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

    # --- 25 numbered lines ---
    for i, text in enumerate(lines):
        line_num = i + 1
        line_y   = TEXT_TOP - LINE_SPACING - (i * LINE_SPACING)

        # Line number right-aligned in margin column
        c.setFont(FONT_NAME, FONT_SIZE)
        c.drawRightString(LINENUM_X + 0.28 * inch, line_y, str(line_num))

        if not text.strip():
            continue

        c.setFont(FONT_NAME, FONT_SIZE)

        if '\t' in text:
            # Tab-delimited index line: left label + right-aligned page number
            parts = text.split('\t')
            label  = parts[0]
            number = parts[-1].strip()
            if label.strip():
                c.drawString(TEXT_X, line_y, label)
            if number:
                c.drawRightString(TEXT_RIGHT, line_y, number)
        else:
            # Check for Q./A. line — draw label in bold, rest in regular
            qa_match = re.match(r'^(\s*)(Q\.|A\.)(\s+.*)$', text)
            if qa_match:
                prefix = qa_match.group(1)   # leading spaces
                label  = qa_match.group(2)   # "Q." or "A."
                rest   = qa_match.group(3)   # "   body text..."
                char_w = FONT_SIZE * 0.6     # Courier monospace char width
                x_label = TEXT_X + len(prefix) * char_w
                c.setFont(FONT_BOLD, FONT_SIZE)
                c.drawString(x_label, line_y, label)
                c.setFont(FONT_NAME, FONT_SIZE)
                c.drawString(x_label + len(label) * char_w, line_y, rest)
            else:
                # Detect pre-centered lines (balanced leading/trailing spaces, ≥8 leading)
                # and true-center them on the page rather than anchoring at TEXT_X.
                leading  = len(text) - len(text.lstrip())
                trailing = len(text) - len(text.rstrip())
                is_centered = (leading >= 8 and abs(leading - trailing) <= 2)
                if is_centered:
                    c.drawCentredString(PAGE_W / 2, line_y, text.strip())
                else:
                    # Normal line — truncate to available width (safety)
                    max_chars = int((TEXT_RIGHT - TEXT_X) / (FONT_SIZE * 0.6)) + 5
                    c.drawString(TEXT_X, line_y, text[:max_chars])


def build_pdf(pages):
    """Render all pages to PDF."""
    c = canvas.Canvas(OUTPUT_PDF, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("Easley Deposition - Yellow Rock v. Westlake")
    c.setAuthor("Marybeth E. Muir, CCR, RPR")
    c.setSubject("Videotaped Deposition of Thomas L. Easley - March 13, 2026")

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

"""
build_pdf.py — Convert formatted deposition text to professional PDF
matching Louisiana court reporter final transcript format.

Layout matches the real Cox/YellowRock depo PDF:
  - Letter size (8.5 x 11)
  - Courier 12pt (standard court reporter font)
  - Page number top right, standalone
  - Line numbers 1-25 left margin
  - 1" margins all sides
"""
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

INPUT_TXT = 'FINAL_DELIVERY/Easley_YellowRock_FINAL_FORMATTED.txt'
OUTPUT_PDF = 'FINAL_DELIVERY/Easley_YellowRock_FINAL.pdf'

# --- Page geometry (matches real depo) ---
PAGE_W, PAGE_H = letter          # 612 x 792 points
MARGIN_TOP    = 0.75 * inch
MARGIN_BOTTOM = 0.75 * inch
MARGIN_LEFT   = 1.25 * inch
MARGIN_RIGHT  = 0.75 * inch

FONT_NAME = 'Courier'
FONT_BOLD = 'Courier-Bold'
FONT_SIZE = 12
LINE_SPACING = 14.4  # points between baselines (12pt * 1.2)

# Text area
TEXT_LEFT  = MARGIN_LEFT + 0.35 * inch
TEXT_RIGHT = PAGE_W - MARGIN_RIGHT
TEXT_TOP   = PAGE_H - MARGIN_TOP
TEXT_WIDTH = TEXT_RIGHT - TEXT_LEFT

LINENUM_X  = MARGIN_LEFT  # where line numbers print
TEXT_X     = MARGIN_LEFT + 0.38 * inch  # where text starts

LINES_PER_PAGE = 25


def parse_formatted_txt(path):
    """
    Parse the formatted .txt file into a list of pages.
    Each page is a dict: {page_num: int, lines: [str, ...]}
    Lines are exactly 25 per page (the text after the line number).
    """
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split on double newline which separates pages
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

        # Remaining lines: " 1  text..." strip the line number prefix
        text_lines = []
        for line in block_lines[1:]:
            # Match " 1  content" or "25  content"
            m = re.match(r'^\s*(\d{1,2})\s{1,4}(.*)', line)
            if m:
                text_lines.append(m.group(2).rstrip())
            else:
                # blank numbered line
                text_lines.append('')

        # Pad to 25
        while len(text_lines) < 25:
            text_lines.append('')

        pages.append({'num': pnum, 'lines': text_lines[:25]})

    return pages


def draw_page(c, page_data):
    """Draw one page of the deposition transcript."""
    pnum = page_data['num']
    lines = page_data['lines']

    # --- Page number (top RIGHT, like real Marybeth depo) ---
    c.setFont(FONT_NAME, FONT_SIZE)
    c.drawRightString(PAGE_W - MARGIN_RIGHT, TEXT_TOP + 4, str(pnum))

    # --- Vertical black line left of text (standard court reporter format) ---
    # Positioned between line numbers and text, full height of text block
    line_x = TEXT_X - 0.08 * inch
    top_y = TEXT_TOP - LINE_SPACING + 4          # top of line 1
    bot_y = TEXT_TOP - LINE_SPACING - (24 * LINE_SPACING) - 4  # bottom of line 25
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.line(line_x, top_y, line_x, bot_y)

    # --- 25 numbered lines ---
    y = TEXT_TOP - LINE_SPACING  # start below page number

    for i, text in enumerate(lines):
        line_num = i + 1
        line_y = y - (i * LINE_SPACING)

        # Line number (right-aligned in margin)
        c.setFont(FONT_NAME, FONT_SIZE)
        c.drawRightString(LINENUM_X + 0.28 * inch, line_y, str(line_num))

        # Text content
        if text.strip():
            c.setFont(FONT_NAME, FONT_SIZE)
            if '\t' in text:
                # Tab-delimited: left label + right-aligned page number
                parts = text.split('\t')
                label = parts[0]
                number = parts[-1].strip()
                if label.strip():
                    c.drawString(TEXT_X, line_y, label)
                c.drawRightString(TEXT_RIGHT, line_y, number)
            else:
                c.drawString(TEXT_X, line_y, text[:95])


def build_pdf(pages):
    """Render all pages to PDF."""
    c = canvas.Canvas(OUTPUT_PDF, pagesize=letter)
    c.setTitle("Easley Deposition - Yellow Rock v. Westlake")
    c.setAuthor("Marybeth E. Muir, CCR, RPR")
    c.setSubject("Videotaped Deposition of Thomas L. Easley - March 13, 2026")

    for page_data in pages:
        draw_page(c, page_data)
        c.showPage()  # next page

    c.save()
    print(f"PDF written: {OUTPUT_PDF}")
    print(f"Pages: {len(pages)}")


def main():
    print(f"Reading {INPUT_TXT}...")
    pages = parse_formatted_txt(INPUT_TXT)
    print(f"Parsed {len(pages)} pages")

    if not pages:
        print("ERROR: No pages parsed. Check input file.")
        return

    # Quick sanity check
    print(f"First page number: {pages[0]['num']}")
    print(f"First page line 1: {pages[0]['lines'][0][:60]}")
    print(f"Last page number: {pages[-1]['num']}")

    build_pdf(pages)


if __name__ == '__main__':
    main()

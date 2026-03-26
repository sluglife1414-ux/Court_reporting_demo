"""
state_config.py — Louisiana, New York, New Jersey transcript format specifications.

Sources:
  LA: Louisiana Administrative Code Title 46, §XXI-1101 + LABCSR sample PDFs
  NY: 22 NYCRR § 108.3
  NJ: NJ Courts published transcript format spec

Usage:
    from state_config import get_config
    cfg = get_config('LA')
    LINE_SPACING = cfg['line_spacing']
"""

from reportlab.lib.units import inch

STATES = {

    # -------------------------------------------------------
    # LOUISIANA — Deposition / Freelance reporter format
    # LAC Title 46 §XXI-1101 + LABCSR measured from real PDF
    # -------------------------------------------------------
    'LA': {
        'state': 'LA',
        'paper': 'letter',           # 8.5 x 11
        'page_w': 8.5 * inch,
        'page_h': 11.0 * inch,
        'lines_per_page': 25,
        'font': 'Courier',
        'font_bold': 'Courier-Bold',
        'font_size': 12,
        'line_spacing': 26.0,        # 0.360" between baselines — measured from MB's PDF
        'margin_top': 0.75 * inch,
        'margin_bottom': 0.75 * inch,
        'margin_left': 1.129 * inch, # measured from MB's PDF
        'margin_right': 0.91 * inch, # 8.5" - 7.59" right edge = 0.91"
        'linenum_x': 0.47 * inch,    # right edge at 0.75" — measured from MB's PDF
        'text_x': 1.129 * inch,      # body text at 1.129" — measured from MB's PDF
        'pagenum_from_top': 0.35 * inch,  # page number 0.35" from top
        'pagenum_align': 'right',    # upper RIGHT
        'q_indent': 5,               # Q. + 5 spaces to text
        'a_indent': 5,
        'colloquy_indent': 15,       # speaker ≤15 spaces from left
        'colloquy_carry': 10,
        'blank_lines_body': False,   # NO blank numbered lines on body pages
        'line_width_chars': 64,      # 7.59" - 1.129" = 6.461" / 0.1" per char = 64 chars
        'vert_line': True,           # vertical line left of text on testimony pages
    },

    # -------------------------------------------------------
    # NEW YORK — 22 NYCRR § 108.3
    # -------------------------------------------------------
    'NY': {
        'state': 'NY',
        'paper': 'letter',
        'page_w': 8.5 * inch,
        'page_h': 11.0 * inch,
        'lines_per_page': 25,
        'font': 'Courier',
        'font_bold': 'Courier-Bold',
        'font_size': 12,
        'line_spacing': 26.0,
        'margin_top': 0.75 * inch,
        'margin_bottom': 0.75 * inch,
        'margin_left': 1.75 * inch,  # NY has wider left margin (1 3/4")
        'margin_right': 0.75 * inch,
        'linenum_x': 1.75 * inch,
        'text_x': 2.10 * inch,
        'pagenum_from_top': 0.35 * inch,
        'pagenum_align': 'right',
        'q_indent': 10,              # Q at 5-space indent, text at 10 spaces
        'a_indent': 10,
        'colloquy_indent': 15,
        'colloquy_carry': 10,
        'blank_lines_body': True,    # NY allows blank lines
        'line_width_chars': 56,
        'vert_line': False,
    },

    # -------------------------------------------------------
    # NEW JERSEY — NJ Courts published spec
    # -------------------------------------------------------
    'NJ': {
        'state': 'NJ',
        'paper': 'letter',
        'page_w': 8.5 * inch,
        'page_h': 11.0 * inch,
        'lines_per_page': 25,
        'font': 'Courier',
        'font_bold': 'Courier-Bold',
        'font_size': 12,
        'line_spacing': 26.0,
        'margin_top': 0.75 * inch,
        'margin_bottom': 0.75 * inch,
        'margin_left': 1.25 * inch,
        'margin_right': 0.75 * inch,
        'linenum_x': 1.35 * inch,
        'text_x': 1.65 * inch,
        'pagenum_from_top': 0.35 * inch,
        'pagenum_align': 'right',
        'q_indent': 5,               # NJ: Q at 6th space (asymmetric layout)
        'a_indent': 0,               # NJ: A at left margin, text at 6th space
        'colloquy_indent': 15,
        'colloquy_carry': 10,
        'blank_lines_body': True,
        'line_width_chars': 58,
        'vert_line': False,
    },
}


def get_config(state='LA'):
    """Return format config for given state code. Defaults to LA."""
    state = state.upper()
    if state not in STATES:
        raise ValueError(f"Unknown state '{state}'. Available: {list(STATES.keys())}")
    return STATES[state]

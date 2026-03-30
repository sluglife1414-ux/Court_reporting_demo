"""
state_config.py — Louisiana, New York, New Jersey transcript format specifications.

Sources:
  LA:       Louisiana Administrative Code Title 46, §XXI-1101 + LABCSR measured from MB's PDF
  NY:       AD's WC format — measured from Fourman reference PDF (0324Fourman2026wcbG3953702.pdf)
  NY_CIVIL: 22 NYCRR § 108.3 civil court — measured from Gotesman reference PDF
  NJ:       NJ Courts published transcript format spec

Routing:
  Workers' Comp (WCB) → state: NY       (AD's measured format)
  Civil / Supreme Court → state: NY_CIVIL (22 NYCRR § 108.3)
  Louisiana (any parish) → state: LA

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
    # NEW YORK — Workers' Compensation Board (WCB) format
    # Source: AD (Alicia D'Alotto) — measured from 0324Fourman2026wcbG3953702.pdf
    # This is the default 'NY' state — any NY WC depo uses this config.
    # -------------------------------------------------------
    'NY': {
        'state': 'NY',
        'paper': 'letter',
        'page_w': 8.5 * inch,
        'page_h': 11.0 * inch,
        'lines_per_page': 25,   # EXACT: measured from 0324Fourman2026wcbG3953702.pdf
        'font': 'Courier',
        'font_bold': 'Courier-Bold',
        'font_size': 12,
        'line_spacing': 24.93,       # EXACT: 24.931pt avg measured via pdfplumber
        'margin_top': 0.833 * inch,  # EXACT: 59.96pt from line-2 baseline in Fourman reference
        'margin_bottom': 0.75 * inch,
        'margin_left': 1.00 * inch,  # [TECH DEBT] official spec = 1.75"; measured = 1.00"
        'margin_right': 0.88 * inch, # EXACT: right edge = 548.38pt → 612-548.38=63.62pt
        'linenum_x': 1.216 * inch,   # EXACT: right edge of line nums = 107.73pt
        'text_x': 2.228 * inch,      # EXACT: 160.4pt measured from Fourman reference
        'pagenum_from_top': 0.173 * inch,  # EXACT: 12.45pt from top measured from Fourman
        'pagenum_align': 'right',    # upper RIGHT — confirmed from Fourman + AD style
        'q_indent': 10,              # Q at 5-space indent, text at 10 spaces (no period)
        'a_indent': 10,
        'colloquy_indent': 15,
        'colloquy_carry': 10,
        'blank_lines_body': True,    # NY allows blank lines
        'line_width_chars': 54,      # EXACT: (548.38-160.37)/7.2 = 53.9 chars
        'vert_line': False,          # WC does not use vertical line
    },

    # -------------------------------------------------------
    # NEW YORK CIVIL — 22 NYCRR § 108.3 (Supreme Court / civil litigation)
    # Source: Gotesman reference PDF (civil deposition)
    # Use for: NY Supreme Court, County Court, Civil Court — NOT WC/WCB depos.
    # [TECH DEBT] Gotesman margins deviate from official spec — measure real civil job when it arrives.
    # -------------------------------------------------------
    'NY_CIVIL': {
        'state': 'NY_CIVIL',
        'paper': 'letter',
        'page_w': 8.5 * inch,
        'page_h': 11.0 * inch,
        'lines_per_page': 26,        # measured from Gotesman civil reference PDF
        'font': 'Courier',
        'font_bold': 'Courier-Bold',
        'font_size': 12,
        'line_spacing': 25.0,        # measured from Gotesman
        'margin_top': 0.70 * inch,   # measured from Gotesman
        'margin_bottom': 0.75 * inch,
        'margin_left': 1.00 * inch,  # [TECH DEBT] official spec = 1.75"; Gotesman = 1.00"
        'margin_right': 0.88 * inch, # [TECH DEBT] official spec = 0.375"; Gotesman = 0.88"
        'linenum_x': 1.394 * inch,   # measured from Gotesman: right edge at 120.5pt
        'text_x': 2.228 * inch,      # measured from Gotesman: 160.4pt
        'pagenum_from_top': 0.35 * inch,  # [TECH DEBT] placeholder — measure from civil ref
        'pagenum_align': 'right',    # upper RIGHT per 22 NYCRR § 108.3
        'q_indent': 10,              # per spec: Q + 5 spaces, text at 10 spaces, no period
        'a_indent': 10,
        'colloquy_indent': 15,
        'colloquy_carry': 10,
        'blank_lines_body': True,
        'line_width_chars': 52,      # measured from Gotesman
        'vert_line': True,           # 22 NYCRR § 108.3 requires two vertical lines
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

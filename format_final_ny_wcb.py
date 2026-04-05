"""
format_final_ny_wcb.py — NY Workers' Compensation Board transcript formatter.

Spec: CR-provided finished PDF sample (AD / dalotto_ny_001)
Ref:  0324Fourman2026wcbG3953702.pdf  (pdfplumber measurements: ad_pdf_measurements.md)

Page order (confirmed from finished PDF):
  1       Caption
  2       Appearances
  3-N     Testimony  (oath → Q/A → colloquy → jurat)
  N+1     Index      (AFTER testimony)
  N+2     Certificate

Running header: WCB G395 3702  on line 1 of every page.
Effective content per page: 24 lines (lines 2-25).
"""
import re
import os
import json
import textwrap

# ── Input / output ────────────────────────────────────────────────────────────
INPUT_FILE  = 'corrected_text.txt' if os.path.exists('corrected_text.txt') else 'cleaned_text.txt'
_cfg_path   = 'CASE_CAPTION.json'

if not os.path.exists(_cfg_path):
    raise FileNotFoundError(
        "CASE_CAPTION.json not found. Required for NY WCB formatter.\n"
        "Create it from the retainer/engagement data."
    )
with open(_cfg_path, encoding='utf-8') as _f:
    _cfg = json.load(_f)

# ── Layout constants (pdfplumber: Courier 12pt, 7.2pt/char) ──────────────────
LINE_WIDTH     = 49   # content area width in chars
LINES_PER_PAGE = 25   # numbered lines per page
CONTENT_LINES  = 24   # lines 2-25 (line 1 = running header)

# Q/A: label at x=197.8 (5 chars from content), text at x=235.3 (10 chars)
Q_PREFIX = '     Q    '   # 5 spaces + Q + 4 spaces = 10 chars (x=197.8→235.3 / 7.2pt)
A_PREFIX = '     A    '   # same
QA_BODY_FIRST = LINE_WIDTH - len(Q_PREFIX)   # 39 chars first line
QA_BODY_CONT  = LINE_WIDTH                   # flush-left continuation

# Colloquy: MR. X: at x=235.3 (10 chars), continuation at x=197.8 (5 chars)
COLL_INDENT      = ' ' * 10
COLL_CONT_INDENT = ' ' * 5

# ── Config values ─────────────────────────────────────────────────────────────
WCB_CASE_NO     = _cfg.get('wcb_case_no', '')
CARRIER_CASE_NO = _cfg.get('carrier_case_no', '')
DATE_OF_ACCIDENT= _cfg.get('date_of_accident', '')
CLAIMANT        = _cfg.get('claimant', '')
CLAIMANT_ROLE   = _cfg.get('claimant_role', 'Claimant,')
EMPLOYER        = _cfg.get('employer', '')
EMPLOYER_ROLE   = _cfg.get('employer_role', 'Employer.')
WITNESS_NAME    = _cfg.get('witness_name', '')
WITNESS_LAST    = _cfg.get('witness_last', '')
DEPO_TYPE       = _cfg.get('depo_type', 'DEPOSITION')
WITNESS_ROLE    = _cfg.get('witness_role', '')
DEPO_DATE       = _cfg.get('depo_date', '')
DEPO_TIME       = _cfg.get('depo_time', '')
REPORTER_NAME   = _cfg.get('reporter_name', '')
REPORTER_ADDRESS= _cfg.get('reporter_address', '')
REPORTER_PHONE  = _cfg.get('reporter_phone', '')
REPORTER_TITLE  = _cfg.get('reporter_title', 'Notary Public of the State of New York')
EXAMINING_ATTY  = _cfg.get('examining_atty', '')
APPEARANCES     = _cfg.get('appearances', [])

RUNNING_HEADER = f'WCB {WCB_CASE_NO}'
OUTPUT_FILE    = f"FINAL_DELIVERY/{_cfg.get('case_short', 'Fourman_WCB')}_FINAL_FORMATTED.txt"


# ── Helpers ───────────────────────────────────────────────────────────────────

def center(text, width=LINE_WIDTH):
    return text.center(width)


def right_align(text, width=LINE_WIDTH):
    return text.rjust(width)


def wrap(text, width=LINE_WIDTH, indent=''):
    """Wrap text at width with hanging indent on continuation lines."""
    if len(indent) + len(text) <= width:
        return [indent + text]
    w = textwrap.TextWrapper(
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
    )
    return w.wrap(text) or [indent]


def wrap_qa(prefix, body):
    """Wrap a Q or A block. First line uses prefix, continuation is flush left."""
    first_avail = LINE_WIDTH - len(prefix)
    lines = []
    if len(body) <= first_avail:
        lines.append(prefix + body)
    else:
        cut = body.rfind(' ', 0, first_avail)
        if cut == -1:
            cut = first_avail
        lines.append(prefix + body[:cut])
        remaining = body[cut:].lstrip()
        while remaining:
            if len(remaining) <= LINE_WIDTH:
                lines.append(remaining)
                break
            cut = remaining.rfind(' ', 0, LINE_WIDTH)
            if cut == -1:
                cut = LINE_WIDTH
            lines.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()
    return lines


def wrap_colloquy(speaker, body):
    """Wrap a colloquy block. Speaker at COLL_INDENT, continuation at COLL_CONT_INDENT."""
    first_line = COLL_INDENT + speaker + '  ' + body if body else COLL_INDENT + speaker
    first_avail = LINE_WIDTH - len(COLL_INDENT) - len(speaker) - 2
    lines = []
    if not body:
        lines.append(COLL_INDENT + speaker)
        return lines
    if len(body) <= first_avail:
        lines.append(COLL_INDENT + speaker + '  ' + body)
    else:
        cut = body.rfind(' ', 0, first_avail)
        if cut == -1:
            cut = first_avail
        lines.append(COLL_INDENT + speaker + '  ' + body[:cut])
        remaining = body[cut:].lstrip()
        cont_avail = LINE_WIDTH - len(COLL_CONT_INDENT)
        while remaining:
            if len(remaining) <= cont_avail:
                lines.append(COLL_CONT_INDENT + remaining)
                break
            cut = remaining.rfind(' ', 0, cont_avail)
            if cut == -1:
                cut = cont_avail
            lines.append(COLL_CONT_INDENT + remaining[:cut])
            remaining = remaining[cut:].lstrip()
    return lines


def strip_review_flags(text):
    """Remove [REVIEW:...] and [FLAG:...] tags before formatting."""
    text = re.sub(r'\[REVIEW:[^\[]*?—\s*reporter confirm\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[REVIEW:[^\]]*\]', '', text)
    text = re.sub(r'\s*\[FLAG:[^\]]*\]', '', text)
    text = re.sub(r'\s*\[CORRECTED:[^\]]*\]', '', text)
    text = re.sub(r'  +', ' ', text)
    return text


# ── Page renderer ─────────────────────────────────────────────────────────────

def format_page(page_num, content_lines):
    """Render a page: page number + 25 numbered lines.

    Line 1 is always the running header (WCB G395 3702).
    content_lines: up to 24 items for lines 2-25.
    """
    slots = [RUNNING_HEADER.center(LINE_WIDTH)] + list(content_lines)
    # Pad or trim to exactly 25
    while len(slots) < LINES_PER_PAGE:
        slots.append('')
    slots = slots[:LINES_PER_PAGE]
    out = [str(page_num)]
    for i, line in enumerate(slots):
        out.append(f'{i+1:2d}  {line}')
    return '\n'.join(out)


def paginate(lines):
    """Split content lines into pages of CONTENT_LINES each."""
    pages = []
    for i in range(0, max(len(lines), 1), CONTENT_LINES):
        chunk = lines[i:i + CONTENT_LINES]
        while len(chunk) < CONTENT_LINES:
            chunk.append('')
        pages.append(chunk)
    return pages


# ── Section builders ──────────────────────────────────────────────────────────

def build_caption():
    """Page 1 — WCB NY caption layout (confirmed from Fourman PDF).

    Spec (pdfplumber):
      - Description: 5-char initial indent, continuation flush-left (x=160.4), width=49
      - Date/time: both at ~20-char indent (x≈302.8)
      - Reporter credit: name centered line 24, address centered line 25
      - No blank between description and asterisks (needed to fit 24 content slots)
    """
    BORDER = '-' * 46 + ' x'

    L = []
    L.append(center('WORKERS\' COMPENSATION BOARD'))
    L.append(center('STATE OF NEW YORK'))
    L.append(BORDER)
    L.append(CLAIMANT + ',')                       # delta 1: trailing comma
    L.append(right_align(CLAIMANT_ROLE))
    L.append(center('-against-'))
    L.append(EMPLOYER + ',')
    L.append(right_align(EMPLOYER_ROLE))
    L.append(f'Carrier Case No.  {CARRIER_CASE_NO}')
    L.append(f'WCB Case No.  {WCB_CASE_NO}')
    L.append(f'D/A:  {DATE_OF_ACCIDENT}')
    L.append(BORDER)
    L.append(' ' * 20 + DEPO_DATE)                # delta 4: 20-char indent (spec x≈302.8)
    L.append(' ' * 20 + DEPO_TIME)                # delta 4
    # Description: initial 5-char indent, continuation flush-left, wrap at 49
    # delta 2 (wrap fix) + delta 3 ("a Notary Public")
    intro = (
        f'{DEPO_TYPE} OF {WITNESS_NAME}, '
        f'{WITNESS_ROLE}, taken by the parties, pursuant to Workers\' '
        f'Compensation Law & Rules of Testimony and Subpoena, held via '
        f'telephone conference, on the above-mentioned date and time before '
        f'{REPORTER_NAME}, a {REPORTER_TITLE}.'
    )
    _tw = textwrap.TextWrapper(
        width=LINE_WIDTH, initial_indent='     ', subsequent_indent=''
    )
    L.extend(_tw.wrap(intro))
    # delta 5: reporter credit — name centered (line 24), full address centered (line 25)
    # No blank before asterisks — required to fit both reporter lines in 24 content slots
    L.append('*' * 50)
    L.append(center(REPORTER_NAME))
    L.append(center(REPORTER_ADDRESS))

    # Trim or pad to exactly CONTENT_LINES
    while len(L) < CONTENT_LINES:
        L.append('')
    return [L[:CONTENT_LINES]]


def build_appearances():
    """Page 2 — Appearances from CASE_CAPTION.json.

    Spec (pdfplumber):
      - Line 2: 'A P P E A R A N C E S:' at x=160.4 (left edge)
      - Firm/role: left-aligned (x=160.4)
      - Address lines: 5-char indent (x=197.8)
      - 'BY:  name' — BY: at x=160.4, name at x=197.8 (BY: is 3+2=5 chars)
    """
    lines = []
    # delta 6: APPEARANCES header
    lines.append('A P P E A R A N C E S:')
    lines.append('')
    for i, block in enumerate(APPEARANCES):
        if i > 0:
            lines.append('')
            lines.append('')
        firm = block.get('firm', '')
        role = block.get('role', '')
        csz  = block.get('city_state_zip', '')
        attorneys = block.get('attorneys', [])

        if firm:
            lines.append(firm)
        if role:
            lines.append(role)
        # delta 7: 5-char indent for address lines (spec x=197.8)
        for field in ['address_1', 'address_2', 'address_3']:
            val = block.get(field, '').strip()
            if val:
                lines.append(f'     {val}')
        if csz:
            lines.append(f'     {csz}')
        # delta 8: BY: at left edge, name follows after 2 spaces (total 5 chars)
        for atty in attorneys:
            name = atty.get('name', '') if isinstance(atty, dict) else atty
            lines.append(f'BY:  {name}')

    lines.append('')
    lines.append(center('xxxxx'))

    while len(lines) < CONTENT_LINES:
        lines.append('')
    content = lines[:CONTENT_LINES]
    return [content]


def build_index(exam_starts):
    """Page after testimony — I N D E X with witness and examining attorneys.

    exam_starts: list of (attorney_label, page_num) tuples
    e.g. [('MR. BLUM', 3), ('MR. FRIEDLICH', 7)]
    """
    lines = []
    lines.append(center('I N D E X'))
    lines.append('')
    lines.append('')
    lines.append('WITNESS')
    lines.append(WITNESS_NAME)
    # Underline for EXAMINATION BY: row
    exam_header = 'EXAMINATION BY:'
    page_label  = 'PAGE'
    gap = LINE_WIDTH - len(exam_header) - len(page_label)
    lines.append(exam_header + ' ' * gap + page_label)
    for label, pg in exam_starts:
        entry = f'     {label}'
        pg_str = str(pg)
        gap = LINE_WIDTH - len(entry) - len(pg_str)
        lines.append(entry + ' ' * max(1, gap) + pg_str)

    while len(lines) < CONTENT_LINES:
        lines.append('')
    return [lines[:CONTENT_LINES]]


def build_cert():
    """Certificate page — AD's NY WCB cert (confirmed from Fourman PDF p.21).

    Spec (pdfplumber): all cert text flush-left (x=160.4), no indent.
    delta 14: remove 5-space indent from all paragraphs.
    """
    lines = []
    lines.append(center('C E R T I F I C A T E'))
    # Spec: no blank between header and first paragraph (line 3 = paragraph 1)
    # Paragraph 1 — flush left
    cert_p1 = (
        f'I, {REPORTER_NAME}, hereby certify that the Deposition of '
        f'{WITNESS_NAME} was held before me on {DEPO_DATE}; that said witness was '
        f'duly sworn before the commencement of the testimony; that the testimony '
        f'was taken stenographically by myself and then transcribed by myself; '
        f'that the parties were represented by Counsel as appears herein;'
    )
    for line in wrap(cert_p1, width=LINE_WIDTH):
        lines.append(line)
    lines.append('')
    # Paragraph 2
    for line in wrap(
        'That the within transcript is a true record of the Deposition of said witness;',
        width=LINE_WIDTH
    ):
        lines.append(line)
    lines.append('')
    # Paragraph 3
    for line in wrap(
        'That I am not connected by blood or marriage with any of the parties; '
        'that I am not interested directly or indirectly in the outcome of this matter; '
        'that I am not in the employ of any of the Counsel.',
        width=LINE_WIDTH
    ):
        lines.append(line)
    lines.append('')
    # Closing — one blank before signature to keep both --- and name in 24 slots
    lines.append('IN WITNESS WHEREOF, I have hereunto set my')
    lines.append('hand this ______ day of _____________ 2026.')
    lines.append('')
    lines.append(center('----------------------------'))
    lines.append(center(REPORTER_NAME))

    while len(lines) < CONTENT_LINES:
        lines.append('')
    return [lines[:CONTENT_LINES]]


# ── Testimony parser ──────────────────────────────────────────────────────────

def format_testimony(text):
    """Parse corrected_text.txt and format Q/A/colloquy into numbered content lines.

    NY WCB RTF has no section markers — entire corrected_text is testimony.
    Q/A toggle fires on:  EXAMINATION BY  (line), then  MR. X:  (next line)
    Returns (content_lines, exam_starts)
      exam_starts: list of (attorney_label, content_line_index) for index page
    """
    text = strip_review_flags(text)
    raw_lines = text.split('\n')

    # Step 1: join fragment lines into logical blocks (split on blank lines)
    blocks = []
    current = []
    for line in raw_lines:
        s = line.strip()
        if not s:
            if current:
                blocks.append(' '.join(current))
                current = []
        else:
            current.append(s)
    if current:
        blocks.append(' '.join(current))

    # Step 2: label blocks
    labeled = []
    in_qa        = True    # NY WCB RTF has no section markers — all content is testimony
    qa_toggle    = 'Q'
    exam_by_next = False   # True after EXAMINATION BY — next block is attorney name

    COLLOQUY_PAT = re.compile(
        r'^((?:MR\.|MS\.|MRS\.)\s+\w+:|THE\s+(?:COURT REPORTER|WITNESS):)\s*(.*)',
        re.DOTALL
    )
    OATH_PHRASES = [
        'having been first duly sworn', 'was examined and testified',
        'follows:', 'duly sworn'
    ]

    for block in blocks:
        if not block:
            continue

        # EXAMINATION BY header — next block is attorney name
        if re.match(r'^EXAMINATION\s+BY\s*$', block, re.IGNORECASE):
            labeled.append(('exam_header', 'EXAMINATION BY'))
            exam_by_next = True
            in_qa = True
            qa_toggle = 'Q'
            continue

        # Attorney name line following EXAMINATION BY
        if exam_by_next:
            labeled.append(('exam_atty', block))
            exam_by_next = False
            continue

        # Colloquy: MR. X: / THE WITNESS: / THE COURT REPORTER:
        m = COLLOQUY_PAT.match(block)
        if m:
            labeled.append(('colloquy', (m.group(1).strip(), m.group(2).strip())))
            continue

        # Explicit Q. or A. from steno
        if block.startswith('Q.') or block.startswith('Q '):
            body = re.sub(r'^Q\.?\s+', '', block)
            labeled.append(('Q', body))
            qa_toggle = 'A'
            continue
        if block.startswith('A.') or block.startswith('A '):
            body = re.sub(r'^A\.?\s+', '', block)
            labeled.append(('A', body))
            qa_toggle = 'Q'
            continue

        # Witness intro / oath
        if (WITNESS_NAME in block or WITNESS_LAST in block or
                any(p in block.lower() for p in OATH_PHRASES)):
            labeled.append(('witness_intro', block))
            continue

        # Parenthetical / time noted
        if block.startswith('(') and block.endswith(')'):
            labeled.append(('paren', block))
            continue

        # Unlabeled in Q/A mode
        if in_qa:
            labeled.append((qa_toggle, block))
            qa_toggle = 'A' if qa_toggle == 'Q' else 'Q'
            continue

        # Default: plain text
        labeled.append(('text', block))

    # Step 2b: inject EXAMINATION BY headers (deltas 10-11)
    # NY WCB RTFs have no EXAMINATION BY markers in the steno.
    # Inject initial block from examining_atty, then detect cross-exam handoff.
    #
    # Cross-exam detection: when a colloquy by the primary examiner mentions
    # "cross-examination", the next colloquy from a different non-witness attorney
    # becomes the new examining attorney's EXAMINATION BY block, and their opening
    # statement is converted to a Q.
    _WITNESS_SPEAKERS = {'THE WITNESS', 'THE COURT REPORTER'}
    _examining = EXAMINING_ATTY   # e.g. "MR. BLUM"
    _pending_cross = False
    _injected_start = False
    new_labeled = []

    for kind, val in labeled:
        # Inject initial EXAMINATION BY + examining attorney before first real block
        if not _injected_start:
            new_labeled.append(('exam_header', 'EXAMINATION BY'))
            new_labeled.append(('exam_atty', f'{_examining}:'))
            _injected_start = True

        if kind == 'colloquy':
            speaker, body = val
            speaker_clean = speaker.rstrip(':').strip()

            # Detect cross-examination handoff signal from primary examiner
            if (speaker_clean == _examining and
                    'cross-examination' in body.lower()):
                _pending_cross = True
                new_labeled.append((kind, val))
                continue

            # After signal: next non-witness attorney starts their examination
            if _pending_cross and speaker_clean not in _WITNESS_SPEAKERS:
                new_labeled.append(('exam_header', 'EXAMINATION BY'))
                new_labeled.append(('exam_atty', f'{speaker_clean}:'))
                # Their opening statement becomes their first Q
                if body:
                    new_labeled.append(('Q', body))
                _pending_cross = False
                _examining = speaker_clean
                qa_toggle = 'A'
                continue

        new_labeled.append((kind, val))

    labeled = new_labeled

    # Step 3: merge consecutive same-type Q/A
    merged = []
    for kind, val in labeled:
        if (merged and kind in ('Q', 'A') and
                merged[-1][0] == kind and isinstance(merged[-1][1], str)):
            merged[-1] = (kind, merged[-1][1] + ' ' + val)
        else:
            merged.append([kind, val])

    # Step 4: render to content lines, tracking EXAMINATION BY positions for index
    content_lines = []
    exam_starts   = []   # (attorney_label, content_line_index)

    for kind, val in merged:
        if kind == 'witness_intro':
            for l in wrap(val, width=LINE_WIDTH - 5, indent='     '):
                content_lines.append(l)

        elif kind == 'exam_header':
            content_lines.append('EXAMINATION BY')

        elif kind == 'exam_atty':
            # Record position for index page (line index before we append)
            exam_starts.append((val.rstrip(':'), len(content_lines)))
            content_lines.append(val)

        elif kind == 'Q':
            content_lines.extend(wrap_qa(Q_PREFIX, val))

        elif kind == 'A':
            content_lines.extend(wrap_qa(A_PREFIX, val))

        elif kind == 'colloquy':
            speaker, body = val
            content_lines.extend(wrap_colloquy(speaker, body))

        elif kind == 'paren':
            content_lines.append(COLL_INDENT + val)

        elif kind == 'text':
            content_lines.extend(wrap(val, width=LINE_WIDTH))

    return content_lines, exam_starts


def build_jurat():
    """Witness signature / jurat block — appears at end of testimony (p.19)."""
    lines = []
    lines.append('')
    lines.append('')
    lines.append(right_align('_____________________________'))
    lines.append(center(WITNESS_NAME))
    lines.append('')
    lines.append('Subscribed and Sworn to before me')
    lines.append('this      day of                   20    .')
    lines.append('')
    lines.append('_' * 34)
    lines.append(center('NOTARY PUBLIC'))
    return lines


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    all_pages = []

    # Page 1: Caption
    all_pages.extend(build_caption())

    # Page 2: Appearances
    all_pages.extend(build_appearances())

    # Pages 3-N: Testimony
    testimony_start_page = len(all_pages) + 1   # page number of first testimony page
    witness_intro = [
        f'M I T C H E L L   F O U R M A N, M.D.,'.center(LINE_WIDTH) if 'FOURMAN' in WITNESS_NAME.upper()
        else '  '.join(WITNESS_NAME.upper()),
        'Having been first duly sworn before a Notary',
        'Public of the State of New York, was examined',
        'and testified as follows:',
    ]

    # Parse testimony body
    body_lines, exam_starts_raw = format_testimony(raw_text)

    # Prepend witness intro lines
    all_body = witness_intro + body_lines

    # Append jurat
    all_body.extend(build_jurat())

    # Paginate testimony
    test_pages = paginate(all_body)
    all_pages.extend(test_pages)

    # Convert exam_starts line indices to actual page numbers
    # (offset by witness_intro length, then map to pages)
    intro_offset = len(witness_intro)
    exam_page_starts = []
    for label, line_idx in exam_starts_raw:
        adjusted = line_idx + intro_offset
        page_num = testimony_start_page + (adjusted // CONTENT_LINES)
        exam_page_starts.append((label, page_num))

    # Index page
    index_pages = build_index(exam_page_starts)
    all_pages.extend(index_pages)

    # Certificate
    all_pages.extend(build_cert())

    # Render
    os.makedirs('FINAL_DELIVERY', exist_ok=True)
    output_parts = []
    for pnum, content in enumerate(all_pages, 1):
        output_parts.append(format_page(pnum, content))
        output_parts.append('\n\n')

    final = ''.join(output_parts)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f'Done. {len(all_pages)} pages -> {OUTPUT_FILE}')
    print(f'  Caption:     1')
    print(f'  Appearances: 2')
    print(f'  Testimony:   3-{testimony_start_page + len(test_pages) - 1}')
    print(f'  Index:       {testimony_start_page + len(test_pages)}')
    print(f'  Certificate: {testimony_start_page + len(test_pages) + 1}')


if __name__ == '__main__':
    main()

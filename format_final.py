"""
format_final.py — Reformats cleaned deposition text into professional
Louisiana court reporter final transcript format.

Matches the real output format from the Cox depo PDF:
  - Page number at top
  - 25 numbered lines per page
  - Sections: Caption, Index, Appearances, Stipulation, Examination,
    Reporter's Certificate, Witness's Certificate, Errata Sheets
  - Proper Q/A and colloquy indentation
  - Spaced-letter section headers
"""
import re
import textwrap
import os

# Use AI-corrected text if available, otherwise fall back to steno-cleaned text
INPUT_FILE = 'corrected_text.txt' if os.path.exists('corrected_text.txt') else 'cleaned_text.txt'

# --- Configuration ---
LINES_PER_PAGE = 25
LINE_WIDTH = 64   # measured from MB's PDF: 7.59" - 1.129" = 6.461" / 0.1" per char
# Q. and A. lines wrap narrower in CaseCATalyst format — Q. content ~40 chars,
# continuation ~52. Using 52 here (10-char Q/A prefix + 42 chars content ≈ MB's layout).
QA_LINE_WIDTH = 52

# ═══════════════════════════════════════════════════════════
# CASE CONFIG — update these for each new depo. Nothing else
# in this file needs to change between cases.
# ═══════════════════════════════════════════════════════════
WITNESS_LAST   = "EASLEY"                        # used for output filename
WITNESS_NAME   = "THOMAS L. EASLEY"              # full name as it appears in transcript
CASE_SHORT     = "Easley_YellowRock"             # used in output filenames
DEPO_DATE      = "Friday, March 13, 2026"
DEPO_DATE_SHORT = "March 13, 2026"               # used in certificates
DEPO_TIME      = "9:09 a.m."
DEPO_LOCATION_1 = "111 North Post Oak Lane"
DEPO_LOCATION_2 = "Houston, Texas  77024"
REPORTER_NAME  = "MARYBETH E. MUIR, CCR, RPR"   # MB is always MB
EXAMINING_ATTY = "MR. HOBBY"                    # primary examining attorney
PARISH         = "PARISH OF CALCASIEU"
COURT          = "14TH JUDICIAL DISTRICT"
PLAINTIFF      = "YELLOW ROCK, LLC, et al,"
PLAINTIFF_ROLE = "Plaintiffs,"
DEFENDANT      = "WESTLAKE US 2 LLC f/k/a\n  EAGLE US 2 LLC et al.,"
DEFENDANT_ROLE = "Defendants."
DOCKET         = "202-001594"
DIVISION       = "H"
CERT_YEAR      = "2026"
# ═══════════════════════════════════════════════════════════

OUTPUT_FILE = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL_FORMATTED.txt'


def center(text, width=LINE_WIDTH):
    return text.center(width)


def format_page(page_num, lines):
    """Format a page: page number header + 25 numbered lines."""
    out = [str(page_num)]
    for i in range(25):
        if i < len(lines):
            out.append(f"{i+1:2d}  {lines[i]}")
        else:
            out.append(f"{i+1:2d}")
    return '\n'.join(out)


def wrap_line(text, width=LINE_WIDTH, hang=0):
    """Wrap text, with hanging indent for continuation lines."""
    if len(text) <= width:
        return [text]
    w = textwrap.TextWrapper(width=width, initial_indent='',
                             subsequent_indent=' ' * hang)
    return w.wrap(text) or [""]


# =========================================================
# SECTION BUILDERS
# =========================================================

def build_caption():
    """Page 1 caption — all content on one page, reporter credit on page 1 per LA spec."""
    L = []
    L.append(center("STATE OF LOUISIANA"))
    L.append(center(PARISH))
    L.append(center(COURT))
    L.append(center("* * * * * * * * * * * * * * * * * * * * * * * *"))
    # Case style block — MB format: two-column, parties left / docket right
    def case_row(left, right='', width=LINE_WIDTH):
        gap = width - len(left) - len(right)
        return left + ' ' * max(1, gap) + right
    L.append(case_row(f"  {PLAINTIFF}", "Docket No."))
    L.append(case_row(f"       {PLAINTIFF_ROLE}", DOCKET))
    L.append(case_row("       v.",                f"Division \"{DIVISION}\""))
    for i, dline in enumerate(DEFENDANT.split('\n')):
        L.append(case_row(f"  {dline.strip()}"))
    L.append(case_row(f"       {DEFENDANT_ROLE}"))
    L.append("")
    L.append(center("* * * * * * * * * * * * * * * * * * * * * * * *"))
    L.append("")
    L.append(center("VIDEOTAPED DEPOSITION"))
    L.append(center("OF"))
    L.append(center(WITNESS_NAME))
    L.append(center("taken on"))
    L.append(center(DEPO_DATE))
    L.append(center(f"commencing at {DEPO_TIME}"))
    L.append(center("at"))
    L.append(center(DEPO_LOCATION_1))
    L.append(center(DEPO_LOCATION_2))
    L.append("")
    L.append(f"  Reported By:  {REPORTER_NAME}")
    L.append(center("* * * * * * * * * * * * * * * * * * * * * * * *"))
    return [L[:25]]


def build_index(app_start, stip_start, exam_start, cert_start, wcert_start, exhibit_nums=None):
    # Use TAB as delimiter between label and page number.
    # PDF builder detects \t and renders label left, number right-aligned.
    L = []
    L.append(center("I N D E X"))
    L.append("\t\tPage")          # "Page" header right-aligned
    L.append(f"  Caption\t1")
    L.append("")
    L.append(f"  Appearances\t{app_start}")
    L.append("")
    L.append(f"  Stipulation\t{stip_start}")
    L.append("")
    L.append(f"  Examination")
    L.append(f"       {EXAMINING_ATTY}\t{exam_start}")
    L.append("")
    L.append(f"  Reporter's Certificate\t{cert_start}")
    L.append("")
    L.append(f"  Witness's Certificate\t{wcert_start}")
    L.append("")
    L.append(center("* * * * * * * *"))
    L.append("")
    L.append("  EXHIBITS")
    L.append("")
    if exhibit_nums:
        for num in exhibit_nums:
            L.append(f"  Exhibit No. {num}")
    else:
        L.append("  [Exhibits to be indexed]")
    while len(L) < 25:
        L.append("")
    return L[:25]


def build_reporter_cert():
    p1 = []
    p1.append(center("C E R T I F I C A T E"))
    p1.append("")
    p1.append("     Certification is valid only for a transcript")
    p1.append("accompanied by my original signature and")
    p1.append("Original required seal on this page.")
    p1.append("")
    p1.append(f"     I, {REPORTER_NAME}, Certified Court")
    p1.append("Reporter in and for the State of Louisiana, and")
    p1.append("Registered Professional Reporter, as the officer")
    p1.append("before whom this testimony was taken, do hereby")
    p1.append(f"certify that {WITNESS_NAME}, after having been")
    p1.append("duly")
    p1.append("sworn by me upon authority of R.S. 37:2554, did")
    p1.append("testify as hereinbefore set forth in the foregoing")
    p1.append("pages; that this testimony was reported by me in")
    p1.append("the stenotype reporting method, was prepared and")
    p1.append("transcribed by me or under my personal direction and")
    p1.append("supervision, and is a true and correct transcript to")
    p1.append("the best of my ability and understanding; that the")
    p1.append("transcript has been prepared in compliance with")
    p1.append("transcript format guidelines required by statute or")
    p1.append("by rules of the board, and that I am informed about")
    p1.append("the complete arrangement, financial or otherwise,")
    p1.append("with the person or entity making arrangements for")
    p1.append("deposition services; that I have acted in compliance")
    p1.append("with the prohibition on contractual relationships,")

    p2 = []
    p2.append("as defined by Louisiana Code of Civil Procedure")
    p2.append("Article 1434 and in rules and advisory opinions of")
    p2.append("the board; that I have no actual knowledge of any")
    p2.append("prohibited employment or contractual relationship,")
    p2.append("direct or indirect, between a court reporting firm")
    p2.append("and any party litigant in this matter nor is there")
    p2.append("any such relationship between myself and a party")
    p2.append("litigant in this matter. I am not related to")
    p2.append("counsel or to the parties herein, nor am I otherwise")
    p2.append("interested in the outcome of this matter.")
    p2.append("")
    p2.append("")
    p2.append(f"This ______ day of _____________, {CERT_YEAR}.")
    p2.append("")
    p2.append("")
    p2.append("")
    p2.append(f"{'':20s}_________________________")
    p2.append(f"{'':20s}{REPORTER_NAME}")
    while len(p2) < 25:
        p2.append("")
    return [p1[:25], p2[:25]]


def build_witness_cert():
    L = []
    L.append(center("C E R T I F I C A T E"))
    L.append("")
    L.append(f"     I, {WITNESS_NAME}, do hereby certify that I have")
    L.append("read or have had read to me the foregoing transcript")
    L.append(f"of my testimony given on {DEPO_DATE_SHORT}, and find")
    L.append("same to be true and correct to the best of my")
    L.append("ability and understanding with the exceptions noted")
    L.append("on the amendment sheet;")
    L.append("")
    L.append("  CHECK ONE BOX BELOW:")
    L.append("  ( ) Without Correction.")
    L.append("  ( ) With corrections, deletions, and/or")
    L.append("      additions as reflected on the errata")
    L.append("      sheet attached hereto.")
    L.append("")
    L.append("  Dated this ___ day of ___________,")
    L.append("  2026.")
    L.append("")
    L.append("")
    L.append(f"{'':20s}_________________________")
    L.append(f"{'':20s}{WITNESS_NAME}")
    L.append("")
    L.append("")
    L.append("")
    L.append(f"  Reported by: {REPORTER_NAME}")
    return [L[:25]]


def build_errata():
    # MB format: 3 lines per entry (Page No., Reason, blank) — no extra underscore line
    # Two full pages of errata (matching MB's 2-page errata section)
    def errata_page(include_signature=False):
        L = []
        L.append("  DEPOSITION ERRATA SHEET")
        L.append("")
        entries_per_page = 7 if include_signature else 8
        for _ in range(entries_per_page):
            L.append("  Page No._____Line No._____Change to:______________")
            L.append("  Reason for change:________________________________")
            L.append("")
        if include_signature:
            while len(L) < 22:
                L.append("")
            L.append("  SIGNATURE:_______________________DATE:___________")
            L.append(f"  {WITNESS_NAME}")
        while len(L) < 25:
            L.append("")
        return L[:25]

    return [errata_page(include_signature=False), errata_page(include_signature=True)]


# =========================================================
# TEXT PARSERS
# =========================================================

def strip_review_tags(text):
    """
    Remove [REVIEW: ...] and [FLAG: ...] tags from the text before final formatting.
    These tags are internal review markers for MB_REVIEW.txt — they must NOT
    appear in the delivered PDF or formatted transcript.
    Inline tags (mid-sentence) are removed cleanly. Block-only lines are dropped.
    """
    # Remove inline [REVIEW: ...] tags — anything in brackets starting with REVIEW or FLAG
    text = re.sub(r'\s*\[REVIEW:[^\]]*\]', '', text)
    text = re.sub(r'\s*\[FLAG:[^\]]*\]', '', text)
    # Clean up any double spaces left behind
    text = re.sub(r'  +', ' ', text)
    return text


def parse_file(text):
    """Split cleaned_text.txt into raw section chunks."""
    lines = text.split('\n')
    sections = {'caption': [], 'index': [], 'appearances': [],
                'stipulation': [], 'testimony': []}
    cur = 'caption'

    for line in lines:
        s = line.strip()
        if '--- PAGE BREAK ---' in s:
            continue
        if ('I N D E X' in s) and cur == 'caption':
            cur = 'index'
            continue
        if 'A P P E A R A N C E S' in s and cur in ('index', 'caption', 'appearances'):
            cur = 'appearances'
            continue
        if 'S T I P U L A T I O N' in s:
            cur = 'stipulation'
            continue
        # Testimony starts when we see the witness name or videographer after stipulation.
        # Uses WITNESS_NAME from config — no other hardcoding needed.
        if cur == 'stipulation' and s.startswith(WITNESS_NAME):
            cur = 'testimony'
        if cur == 'stipulation' and s.startswith('THE VIDEOGRAPHER:'):
            cur = 'testimony'
        # Fallback: any colloquy line after stipulation means testimony has started
        if cur == 'stipulation' and re.match(
                r'^(MR\.|MS\.|MRS\.|THE COURT REPORTER:|THE WITNESS:)', s):
            cur = 'testimony'

        sections[cur].append(line)

    return sections


def collapse_blanks(lines):
    """Remove consecutive blank lines, keep single blanks."""
    out = []
    prev_blank = False
    for line in lines:
        if not line.strip():
            if not prev_blank:
                out.append("")
            prev_blank = True
        else:
            prev_blank = False
            out.append(line.strip())
    return out


def paginate(lines, header=None):
    """Split lines into 25-line pages. Optionally repeat header on new pages."""
    pages = []
    cur = []
    if header:
        cur.append(header)
        cur.append("")

    for line in lines:
        cur.append(line)
        if len(cur) >= 25:
            pages.append(cur[:25])
            cur = []
            if header:
                cur.append(header)
                cur.append("")

    if cur:
        while len(cur) < 25:
            cur.append("")
        pages.append(cur[:25])

    return pages


def format_appearances(raw_lines):
    """Format appearances: remove ALL blank lines from source, then
    re-insert single blanks only between attorney blocks (FOR THE...).
    Indent firm address and BY: lines under each block header."""
    # Strip blanks and headers
    stripped = [l.strip() for l in raw_lines
                if l.strip() and 'A P P E A R A N C E S' not in l.strip()]

    # Re-insert blank lines before each "FOR THE" / "ATTORNEY FOR" / "ALSO PRESENT" block
    # and indent non-header lines under their block
    cleaned = []
    in_block = False
    for line in stripped:
        if re.match(r'^(FOR THE|ATTORNEY FOR|ALSO PRESENT)', line):
            if cleaned:  # don't add blank at very start
                cleaned.append("")
            cleaned.append(line)
            in_block = True
        else:
            if in_block:
                cleaned.append(f"    {line}")
            else:
                cleaned.append(line)

    return paginate(cleaned, header="A P P E A R A N C E S:")


def format_stipulation(raw_lines):
    """Format stipulation section."""
    cleaned = collapse_blanks(raw_lines)
    cleaned = [l for l in cleaned if 'S T I P U L A T I O N' not in l]

    # Join all text into paragraphs (split on blank lines)
    paragraphs = []
    current = []
    for line in cleaned:
        if not line:
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))

    lines = [center("S T I P U L A T I O N"), ""]
    for para in paragraphs:
        if not para.strip():
            continue
        # First line indented, continuation flush left (matching real format)
        wrapped = wrap_line("        " + para, width=LINE_WIDTH, hang=0)
        lines.extend(wrapped)
        lines.append("")

    while len(lines) < 25:
        lines.append("")
    return [lines[:25]]


def format_testimony(raw_lines):
    """
    Format testimony section.

    The cleaned text has fragmented lines from steno with no Q./A. markers.
    After 'BY MR. HOBBY:' lines alternate Q and A without labels.
    Colloquy lines (MR./MS./THE VIDEOGRAPHER/etc.) are labeled.

    Strategy:
    1. Join fragmented lines into logical blocks
    2. Identify colloquy vs Q&A
    3. After 'BY MR. X:', odd unlabeled blocks = Q, even = A
    4. Wrap and paginate
    """
    # Step 1: Join fragments into blocks
    blocks = []
    current = []

    for line in raw_lines:
        s = line.strip()
        if not s:
            if current:
                blocks.append(' '.join(current))
                current = []
            blocks.append('')
            continue

        # New block starters
        is_new = False
        if re.match(r'^(MR\.|MS\.|MRS\.|THE\s+(VIDEOGRAPHER|COURT REPORTER|WITNESS))', s):
            is_new = True
        elif re.match(r'^BY\s+(MR\.|MS\.)', s):
            is_new = True
        elif re.match(r'^EXAMINATION', s):
            is_new = True
        elif s.startswith('Q.') or s.startswith('A.'):
            is_new = True
        elif s == 'witness sworn.' or s == 'witness sworn':
            is_new = True

        if is_new and current:
            blocks.append(' '.join(current))
            current = []

        current.append(s)

    if current:
        blocks.append(' '.join(current))

    # Step 2: Label blocks as Q/A/colloquy
    labeled = []
    in_qa = False
    qa_toggle = 'Q'  # starts with Q after BY line

    for block in blocks:
        if not block:
            labeled.append(('blank', ''))
            continue

        # BY line resets Q/A toggle
        if re.match(r'^BY\s+(MR\.|MS\.)', block):
            labeled.append(('by', block))
            in_qa = True
            qa_toggle = 'Q'
            continue

        if block.startswith('EXAMINATION'):
            labeled.append(('header', 'EXAMINATION'))
            continue

        # Explicit Q. or A.
        if block.startswith('Q. ') or block.startswith('Q.  '):
            labeled.append(('Q', block))
            qa_toggle = 'A'
            continue
        if block.startswith('A. ') or block.startswith('A.  '):
            labeled.append(('A', block))
            qa_toggle = 'Q'
            continue

        # Colloquy speakers
        colloquy = re.match(
            r'^((?:MR\.|MS\.|MRS\.)\s+\w+:|THE\s+(?:VIDEOGRAPHER|COURT REPORTER|WITNESS):)\s*(.*)',
            block)
        if colloquy:
            speaker = colloquy.group(1)
            content = colloquy.group(2).strip()
            # Skip empty colloquy lines (e.g. "MR. HOBBY:" with no text)
            if not content or content in ('.', ',', ''):
                continue
            labeled.append(('colloquy', block))
            continue

        # Witness info line (name, address) — use config var, not hardcoded name
        if WITNESS_NAME in block or WITNESS_LAST in block:
            labeled.append(('witness_info', block))
            continue

        if block in ('witness sworn.', 'witness sworn'):
            labeled.append(('colloquy', 'THE COURT REPORTER: (Witness sworn.)'))
            continue

        # Skip lone punctuation junk from rough steno
        if re.match(r'^[.\s,]+$', block):
            continue

        # Unlabeled block in Q/A mode
        if in_qa:
            if qa_toggle == 'Q':
                labeled.append(('Q', f'Q.  {block}'))
                qa_toggle = 'A'
            else:
                labeled.append(('A', f'A.  {block}'))
                qa_toggle = 'Q'
            continue

        # Default
        labeled.append(('text', block))

    # Step 2.5: Post-process — remove blank entries and merge consecutive
    # same-type Q/A blocks. In real transcripts, the attorney often says
    # "All right." then "Are you ready?" — that's ONE Q block, not two.
    # Also, short transitional phrases like "Okay." / "All right." / "Sure."
    # should merge with the following Q or A block.
    merged = []
    for kind, text in labeled:
        if kind == 'blank':
            continue  # blanks handled by formatting, not content
        if merged and kind in ('Q', 'A') and merged[-1][0] == kind:
            # Merge: append text to previous block
            prev_kind, prev_text = merged[-1]
            # Strip Q./A. prefix from current
            body = re.sub(r'^[QA]\.\s+', '', text)
            merged[-1] = (prev_kind, prev_text + ' ' + body)
        else:
            merged.append((kind, text))
    labeled = merged

    # Step 2.7: Reorder — move leading witness_info/text blocks to after first
    # substantive colloquy (THE VIDEOGRAPHER opening). MB's format has VIDEOGRAPHER
    # statement first, then witness name/address — opposite of raw steno order.
    first_col_idx = None
    for i, (kind, text) in enumerate(labeled):
        if kind == 'colloquy':
            cm = re.match(
                r'^((?:MR\.|MS\.|MRS\.)\s+\w+:|THE\s+(?:VIDEOGRAPHER|COURT REPORTER|WITNESS):)\s*(.*)',
                text)
            if cm and cm.group(2).strip():  # has actual content
                first_col_idx = i
                break
    if first_col_idx and first_col_idx > 0:
        pre_info = [(k, t) for k, t in labeled[:first_col_idx]
                    if k in ('witness_info', 'text')]
        if pre_info:
            other_pre = [(k, t) for k, t in labeled[:first_col_idx]
                         if k not in ('witness_info', 'text')]
            labeled = other_pre + [labeled[first_col_idx]] + pre_info + labeled[first_col_idx + 1:]

    # Step 3: Format into output lines
    # LA spec: NO blank numbered lines on body/testimony pages.
    # All transitions run continuously — no blank line separators.
    formatted = []
    prev_kind = None

    for kind, text in labeled:
        if kind == 'blank':
            continue

        # No blank lines inserted anywhere in testimony (LA rule)

        if kind == 'header':
            formatted.append(center(text))
        elif kind == 'by':
            formatted.append(text)
        elif kind == 'witness_info':
            formatted.append(text)
        elif kind == 'Q':
            body = re.sub(r'^Q\.\s+', '', text) if text.startswith('Q.') else text
            # MB format: Q. indented 5 spaces, text 3 spaces after label
            # QA_LINE_WIDTH (52) matches CaseCATalyst's narrower Q/A column layout
            wrapped = wrap_line('     Q.   ' + body, width=QA_LINE_WIDTH, hang=0)
            formatted.extend(wrapped)
        elif kind == 'A':
            body = re.sub(r'^A\.\s+', '', text) if text.startswith('A.') else text
            wrapped = wrap_line('     A.   ' + body, width=QA_LINE_WIDTH, hang=0)
            formatted.extend(wrapped)
        elif kind == 'colloquy':
            cm = re.match(r'^((?:MR\.|MS\.|MRS\.)\s+\w+:|THE\s+(?:VIDEOGRAPHER|COURT REPORTER|WITNESS):)\s*(.*)', text)
            if cm:
                speaker = cm.group(1)
                rest = cm.group(2)
                full = f"{speaker} {rest}" if rest else speaker
                # MB format: entire colloquy block indented 14 chars from TEXT_X
                # Speaker label and all continuation lines start at col 14
                # Measured from MB's PDF: continuation x0=2.499" = TEXT_X + 14*0.1"
                COLLOQUY_INDENT = 14
                full_indented = ' ' * COLLOQUY_INDENT + full
                wrapped = wrap_line(full_indented, width=LINE_WIDTH, hang=COLLOQUY_INDENT)
                formatted.extend(wrapped)
            else:
                formatted.append(text)
        else:
            wrapped = wrap_line(text, width=LINE_WIDTH, hang=0)
            formatted.extend(wrapped)

        prev_kind = kind

    # Step 4: Paginate
    return paginate(formatted)


# =========================================================
# MAIN
# =========================================================

def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        text = f.read()

    text = strip_review_tags(text)
    sections = parse_file(text)

    # Parse exhibit numbers from index section
    exhibit_nums = []
    for line in sections['index']:
        m = re.match(r'\s*Exhibit\s+No\.\s+(\d+)', line)
        if m:
            num = int(m.group(1))
            if num not in exhibit_nums:
                exhibit_nums.append(num)
    exhibit_nums.sort()

    all_pages = []

    # Caption (1 page — reporter credit included on page 1 per LA spec)
    cap = build_caption()
    all_pages.extend(cap)

    # Index placeholder
    all_pages.append(None)
    idx_pos = len(all_pages) - 1

    # Appearances
    app_start = len(all_pages) + 1
    app_pages = format_appearances(sections['appearances'])
    all_pages.extend(app_pages)

    # Stipulation
    stip_start = len(all_pages) + 1
    stip_pages = format_stipulation(sections['stipulation'])
    all_pages.extend(stip_pages)

    # Testimony
    exam_start = len(all_pages) + 1
    test_pages = format_testimony(sections['testimony'])
    all_pages.extend(test_pages)

    # Reporter's Certificate
    cert_start = len(all_pages) + 1
    all_pages.extend(build_reporter_cert())

    # Witness Certificate
    wcert_start = len(all_pages) + 1
    all_pages.extend(build_witness_cert())

    # Errata
    all_pages.extend(build_errata())

    # Fill index
    all_pages[idx_pos] = build_index(app_start, stip_start, exam_start,
                                      cert_start, wcert_start, exhibit_nums)

    # Render
    output_parts = []
    for pnum, plines in enumerate(all_pages, 1):
        output_parts.append(format_page(pnum, plines))
        output_parts.append('\n\n')

    final = ''.join(output_parts)

    os.makedirs('FINAL_DELIVERY', exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f"Done. {len(all_pages)} pages -> {OUTPUT_FILE}")
    print(f"Characters: {len(final):,}")
    print(f"\nPage map:")
    print(f"  Caption:         1")
    print(f"  Index:           {idx_pos+1}")
    print(f"  Appearances:     {app_start}-{stip_start-1}")
    print(f"  Stipulation:     {stip_start}")
    print(f"  Examination:     {exam_start}-{cert_start-1}")
    print(f"  Reporter Cert:   {cert_start}-{cert_start+1}")
    print(f"  Witness Cert:    {wcert_start}")
    print(f"  Errata:          {wcert_start+1}")


if __name__ == '__main__':
    main()

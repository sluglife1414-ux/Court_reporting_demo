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
import json

# Use AI-corrected text if available, otherwise fall back to steno-cleaned text
INPUT_FILE = 'corrected_text.txt' if os.path.exists('corrected_text.txt') else 'cleaned_text.txt'

# --- Configuration ---
LINES_PER_PAGE = 25
LINE_WIDTH = 64   # measured from MB's PDF: 7.59" - 1.129" = 6.461" / 0.1" per char
# Q. and A. lines wrap narrower in CaseCATalyst format — Q. content ~40 chars,
# continuation ~52. Using 52 here (10-char Q/A prefix + 42 chars content ≈ MB's layout).
QA_LINE_WIDTH = 52

# ═══════════════════════════════════════════════════════════
# CAPTION DATA SOURCE PRIORITY:
# 1. CASE_CAPTION.json — human-verified, authoritative (edit this file manually)
# 2. depo_config.json  — AI-extracted from steno (fallback only, may have errors)
# Rule: steno is NOT the authoritative source for legal caption data.
# Caption data should come from the retainer/engagement or MB's final.
# ═══════════════════════════════════════════════════════════

_cfg_path = 'depo_config.json'
_caption_path = 'CASE_CAPTION.json'

if not os.path.exists(_cfg_path):
    raise FileNotFoundError(
        "depo_config.json not found. Run extract_config.py first:\n"
        "  python extract_config.py"
    )

with open(_cfg_path, encoding='utf-8') as _f:
    _cfg = json.load(_f)

if os.path.exists(_caption_path):
    with open(_caption_path, encoding='utf-8') as _cf:
        _caption = json.load(_cf)
    print(f"[format_final] Caption source: CASE_CAPTION.json (human-verified, authoritative)")
    # Merge: CASE_CAPTION.json overrides depo_config.json for any key it provides
    _cfg.update({k: v for k, v in _caption.items() if not k.startswith('_')})
else:
    print(f"[format_final] Caption source: depo_config.json (AI-extracted fallback — CASE_CAPTION.json not found)")

# Zoom attendees — loaded from CASE_CAPTION.json, matched against BY: lines in appearances.
# Names stored as last name or partial match (e.g. "MADIGAN" matches "THOMAS J. MADIGAN, ESQ.")
# [REVISIT:ZOOM] Full list must be confirmed with MB — steno only captures some remote attendees.
ZOOM_ATTORNEYS  = [n.upper() for n in _cfg.get('zoom_attorneys', [])]

WITNESS_LAST    = _cfg.get('witness_last', 'UNKNOWN')
WITNESS_NAME    = _cfg.get('witness_name', 'UNKNOWN WITNESS')
CASE_SHORT      = _cfg.get('case_short', 'Unknown_Case')
DEPO_DATE       = _cfg.get('depo_date', '')
DEPO_DATE_SHORT = _cfg.get('depo_date_short', '')
DEPO_TIME       = _cfg.get('depo_time', '')
DEPO_LOCATION_0 = _cfg.get('venue_name', '')   # named venue (e.g. THE HOUSTONIAN); blank if not set
DEPO_LOCATION_1 = _cfg.get('location_1', '')
DEPO_LOCATION_2 = _cfg.get('location_2', '')
REPORTER_NAME         = _cfg.get('reporter_name', 'UNKNOWN — reporter_name required')
REPORTER_NAME_DISPLAY = _cfg.get('reporter_name_display', REPORTER_NAME)  # title case for witness cert "Reported by:" line
EXAMINING_ATTY  = _cfg.get('examining_atty', '')
PARISH          = _cfg.get('parish', '')
COURT           = _cfg.get('court', '')
PLAINTIFF       = _cfg.get('plaintiff', '')
PLAINTIFF_ROLE  = _cfg.get('plaintiff_role', 'Plaintiff,')
DEFENDANT       = _cfg.get('defendant', '')
DEFENDANT_ROLE  = _cfg.get('defendant_role', 'Defendant.')
DOCKET          = _cfg.get('docket', '')
DIVISION        = _cfg.get('division', '')
CERT_YEAR       = _cfg.get('cert_year', str(__import__('datetime').date.today().year))

# Warn on any critical unknowns
_warnings = []
if 'UNKNOWN' in REPORTER_NAME: _warnings.append(f"  reporter_name: {REPORTER_NAME}")
if WITNESS_NAME == 'UNKNOWN WITNESS': _warnings.append("  witness_name: not extracted")
if CASE_SHORT == 'Unknown_Case': _warnings.append("  case_short: not extracted")
if _warnings:
    print("[format_final] WARNING — missing fields:")
    for w in _warnings: print(w)
    print("  Fix in CASE_CAPTION.json (preferred) or depo_config.json before delivering transcript.")
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


def wrap_qa_line(prefix, body, first_width=42, cont_width=52, hang=10):
    """Two-width Q/A wrapper matching MB's measured format.

    Measured from MB's 031326yellowrock-FINAL.pdf (2026-03-30):
      - Q/A first line body: max ~40 chars  → first_width=42 (with prefix, total ~52)
      - Continuation lines:  max ~52 chars  → cont_width=52

    MB's CaseCATalyst uses narrower first lines (Q./A. label takes space)
    and wider continuation lines — standard depo transcript convention.
    TextWrapper cannot do two widths natively, so we handle manually.
    """
    indent = ' ' * hang
    lines = []
    # First line: prefix + up to first_width chars of body
    if len(body) <= first_width:
        lines.append(prefix + body)
    else:
        # Find last space within first_width
        cut = body.rfind(' ', 0, first_width)
        if cut == -1:
            cut = first_width
        lines.append(prefix + body[:cut])
        remaining = body[cut:].lstrip()
        # Continuation lines: indent + up to cont_width chars
        while remaining:
            if len(remaining) <= cont_width:
                lines.append(indent + remaining)
                break
            cut = remaining.rfind(' ', 0, cont_width)
            if cut == -1:
                cut = cont_width
            lines.append(indent + remaining[:cut])
            remaining = remaining[cut:].lstrip()
    return lines


def wrap_line(text, width=LINE_WIDTH, hang=0):
    """Wrap text, with hanging indent for continuation lines."""
    if len(text) <= width:
        return [text]
    w = textwrap.TextWrapper(width=width, initial_indent='',
                             subsequent_indent=' ' * hang)
    return w.wrap(text) or [""]


# =========================================================
# EXHIBIT EXTRACTION
# =========================================================

def extract_exhibits(text):
    """Extract exhibit numbers and descriptions from corrected transcript.

    Scans (Whereupon, Exhibit No. X, description, was marked...) parentheticals.
    Returns dict: {exhibit_number (int): description (str)}
    Missing descriptions stored as '' — caller handles [REVIEW] display.

    [TECH DEBT: build_deliverables.py has its own exhibit parsing — consolidate
    both callers to use this function when hardcoded audit runs.]
    """
    exhibits = {}
    pattern = re.compile(
        r'\(Whereupon,\s+Exhibit\s+No\.\s+(\d+)'  # exhibit number
        r'(?:,\s*([^,]+?))?\s*'                    # optional description
        r'(?:,\s*)?was\s+marked',                  # "was marked" anchor
        re.IGNORECASE
    )
    for m in pattern.finditer(text):
        num = int(m.group(1))
        desc = m.group(2).strip() if m.group(2) else ''
        if num not in exhibits:                    # first occurrence wins
            exhibits[num] = desc
    return exhibits


def find_exhibit_pages(all_pages):
    """Find formatted page number where each exhibit was first introduced.

    Scans assembled pages after testimony formatting is complete.
    Returns dict: {exhibit_number (int): page_number (int, 1-indexed)}
    """
    exhibit_pages = {}
    pattern = re.compile(r'Whereupon,\s+Exhibit\s+No\.\s+(\d+)', re.IGNORECASE)
    for page_idx, page_lines in enumerate(all_pages):
        if page_lines is None:
            continue
        for line in page_lines:
            m = pattern.search(line)
            if m:
                num = int(m.group(1))
                if num not in exhibit_pages:      # first occurrence only
                    exhibit_pages[num] = page_idx + 1
    return exhibit_pages


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
    if DEPO_LOCATION_0:
        L.append(center(DEPO_LOCATION_0))   # named venue line (e.g. THE HOUSTONIAN)
    L.append(center(DEPO_LOCATION_1))
    L.append(center(DEPO_LOCATION_2))
    L.append("")
    L.append(f"  Reported By:  {REPORTER_NAME}")
    L.append(center("* * * * * * * * * * * * * * * * * * * * * * * *"))
    return [L[:25]]


def build_index(app_start, stip_start, exam_start, cert_start, wcert_start, exhibits=None):
    """Build index — returns list of pages (may be multiple if exhibit list is long).

    Page 1: I N D E X header + section TOC + * * * * + start of exhibit list
    Page 2+: E X H I B I T S header + continuation of exhibit list

    Exhibit format: "  Exhibit No. XXX  Description............  Page"
    Right-aligns page number to LINE_WIDTH — matches MB's PDF layout.

    Source priority: CASE_CAPTION.json exhibit_list → passed exhibits param
    [REVISIT:INDEX] Confirm exhibit header format with MB (E X H I B I T S vs EXHIBITS)
    """
    # Use exhibit_list from config if available (authoritative)
    exhibit_list = _cfg.get('exhibit_list', [])
    if not exhibit_list and exhibits:
        # Fall back to steno-extracted exhibits
        exhibit_list = exhibits

    # Build TOC section (always fits on page 1 header)
    toc = []
    toc.append(center("I N D E X"))
    toc.append("\t\tPage")
    toc.append(f"  Caption\t1")
    toc.append("")
    toc.append(f"  Appearances\t{app_start}")
    toc.append("")
    toc.append(f"  Stipulation\t{stip_start}")
    toc.append("")
    toc.append(f"  Examination")
    toc.append(f"       {WITNESS_NAME}")
    toc.append(f"       {EXAMINING_ATTY}\t{exam_start}")
    toc.append("")
    toc.append(f"  Reporter's Certificate\t{cert_start}")
    toc.append("")
    toc.append(f"  Witness's Certificate\t{wcert_start}")
    toc.append("")
    toc.append(center("* * * * * * * *"))
    toc.append("")
    toc.append("  EXHIBITS")
    toc.append("")   # 20 lines used — 5 lines left on page 1 for exhibits

    # Build exhibit lines
    exhibit_lines = []
    if exhibit_list:
        for ex in exhibit_list:
            num  = ex.get('number', ex) if isinstance(ex, dict) else ex
            desc = ex.get('description', '') if isinstance(ex, dict) else ''
            pg   = str(ex.get('page', '')) if isinstance(ex, dict) else ''
            if not desc:
                desc = '[REVIEW: description not in steno]'
            label = f"  Exhibit No. {num}  {desc}"
            # Right-align page number
            if pg:
                gap = max(1, LINE_WIDTH - len(label) - len(pg))
                exhibit_lines.append(f"{label}{' ' * gap}{pg}")
            else:
                exhibit_lines.append(label)
    else:
        exhibit_lines.append("  [REVIEW: no exhibit list — add to CASE_CAPTION.json exhibit_list]")

    # Paginate: fill page 1 after TOC, then overflow pages with E X H I B I T S header
    pages = []
    page1 = toc + exhibit_lines[:5]
    while len(page1) < 25:
        page1.append("")
    pages.append(page1[:25])

    remaining = exhibit_lines[5:]
    while remaining:
        pg = [center("E X H I B I T S"), ""]
        chunk = remaining[:23]   # 25 - 2 header lines
        remaining = remaining[23:]
        pg.extend(chunk)
        while len(pg) < 25:
            pg.append("")
        pages.append(pg[:25])

    return pages


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


def build_witness_cert(exhibits=None):
    """Witness certificate — exhibit index (if any) + signature block.

    MB format: exhibit index table appears before the signature block.
    If exhibits overflow 25 lines, index spans multiple pages; signature
    always starts on its own page.

    [REVISIT:WITNESS_CERT] Exact table format (column widths, header style)
    needs MB confirmation before first production delivery.
    Owner: Scott — confirm with MB at next meeting.
    """
    pages = []

    # --- Exhibit Index (prepended per MB format) ---
    if exhibits:
        idx = []
        idx.append(center("C E R T I F I C A T E"))
        idx.append("")
        idx.append("  EXHIBIT INDEX")
        idx.append("")
        for ex in exhibits:
            num    = ex['number']
            desc   = ex['description'] if ex['description'] \
                     else f"[REVIEW: description not captured in steno]"
            pg_str = str(ex['page']) if ex.get('page') else '[REVIEW: page?]'
            label  = f"Exhibit No. {num}  {desc}"
            gap    = max(1, LINE_WIDTH - 2 - len(label) - len(pg_str))
            idx.append(f"  {label}{' ' * gap}{pg_str}")
        # Paginate exhibit index — may span multiple pages
        for i in range(0, len(idx), 25):
            pages.append(idx[i:i + 25])

    # --- Signature Block (always its own page) ---
    sig = []
    if not exhibits:                               # no index — header goes here
        sig.append(center("C E R T I F I C A T E"))
        sig.append("")
    sig.append(f"     I, {WITNESS_NAME}, do hereby certify that I have")
    sig.append("read or have had read to me the foregoing transcript")
    sig.append(f"of my testimony given on {DEPO_DATE_SHORT}, and find")
    sig.append("same to be true and correct to the best of my")
    sig.append("ability and understanding with the exceptions noted")
    sig.append("on the amendment sheet;")
    sig.append("")
    sig.append("  CHECK ONE BOX BELOW:")
    sig.append("  ( ) Without Correction.")
    sig.append("  ( ) With corrections, deletions, and/or")
    sig.append("      additions as reflected on the errata")
    sig.append("      sheet attached hereto.")
    sig.append("")
    sig.append("  Dated this ___ day of ___________,")
    sig.append("  2026.")
    sig.append("")
    sig.append("")
    sig.append(f"{'':20s}_________________________")
    sig.append(f"{'':20s}{WITNESS_NAME}")
    sig.append("")
    sig.append("")
    sig.append("")
    sig.append(f"  Reported by: {REPORTER_NAME_DISPLAY}")
    pages.append(sig[:25])

    return pages


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
            L.append(center(WITNESS_NAME))  # centered under signature line, matching MB
        while len(L) < 25:
            L.append("")
        return L[:25]

    return [errata_page(include_signature=False), errata_page(include_signature=True)]


# =========================================================
# TEXT PARSERS
# =========================================================

def inject_anchors(text):
    """
    Option B: Replace each [REVIEW:...] tag with a short anchor {R:N} where N is
    the correction_log index of that LOW/N/A item.  The anchor is tiny enough to
    survive block-joining, line-wrapping, and pagination unchanged.  After
    paginating we scan all_pages for {R:N} to get the exact p.XX l.YY for every
    flagged item, then strip anchors before writing the final file.

    Matching strategy: content-based.  For each LOW/N/A item we extract the
    [REVIEW:...] tag from its corrected field and find that exact tag in the
    source text, replacing it with {R:idx}.  This is correct even when the
    number of [REVIEW] tags in the text exceeds the number of LOW/N/A items
    (e.g. because HIGH/MEDIUM corrections also embedded [REVIEW] sub-notes).
    """
    log_path = 'correction_log.json'
    if not os.path.exists(log_path):
        return strip_review_tags(text), {}

    with open(log_path, encoding='utf-8') as f:
        data = json.load(f)

    corrections = data.get('corrections', [])
    anchor_map = {}  # correction_log_index -> anchor string

    for idx, item in enumerate(corrections):
        if item.get('confidence') not in ('LOW', 'N/A'):
            continue
        corrected = item.get('corrected', '')
        m = re.search(r'\[REVIEW:[^\]]*\]', corrected)
        if not m:
            continue
        review_tag = m.group(0)
        anchor = f'{{R:{idx}}}'

        if review_tag in text:
            text = text.replace(review_tag, anchor, 1)
            anchor_map[idx] = anchor
        else:
            # Partial match: try progressively shorter prefixes
            matched = False
            for prefix_len in (80, 60, 40, 20):
                if prefix_len >= len(review_tag):
                    continue
                prefix = review_tag[:prefix_len]
                pos = text.find(prefix)
                if pos != -1:
                    end = text.find(']', pos)
                    if end != -1:
                        text = text[:pos] + anchor + text[end + 1:]
                        anchor_map[idx] = anchor
                        matched = True
                        break

    # Strip any [REVIEW] tags that didn't match a LOW/N/A item, and all [FLAG] tags
    # Two-pass: verify-agent tags first (may contain dashes/nested text), then standard
    # [REVIEW:] and [FLAG:] tags are ENGINE-GENERATED — defined in MASTER_DEPOSITION_ENGINE_v4.1.md
    # These are NOT from MB, the CR, or CaseCATalyst. They are our internal AI uncertainty flags.
    # Format: [REVIEW: explanation — reporter confirm] (verify-agent style)
    #      or [REVIEW: explanation] (standard inline style)
    # If the tag format ever changes in the master prompt, update these regexes to match.
    # BUG HISTORY: .*? with re.DOTALL was eating 65,760 chars (34% of Easley) — fixed 2026-03-30
    #              [^\[]*? prevents regex from crossing into adjacent [REVIEW: tags
    text = re.sub(r'\[REVIEW:[^\[]*?—\s*reporter confirm\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\[REVIEW:[^\]]*\]', '', text)
    text = re.sub(r'\s*\[FLAG:[^\]]*\]', '', text)
    text = re.sub(r'  +', ' ', text)
    return text, anchor_map


def strip_anchors(pages):
    """Remove {R:N} anchors from all page lines after location capture."""
    cleaned = []
    for page_lines in pages:
        cleaned.append([re.sub(r'\{R:\d+\}', '', line).rstrip() for line in page_lines])
    return cleaned


def strip_review_tags(text):
    """
    Fallback: remove [REVIEW: ...] and [FLAG: ...] tags when no correction_log
    is available.  Normal path uses inject_anchors() instead.
    Two-pass: verify-agent tags first (may contain dashes), then standard.
    """
    # [REVIEW:] and [FLAG:] tags are ENGINE-GENERATED — defined in MASTER_DEPOSITION_ENGINE_v4.1.md
    # These are NOT from MB, the CR, or CaseCATalyst. They are our internal AI uncertainty flags.
    # Format: [REVIEW: explanation — reporter confirm] (verify-agent style)
    #      or [REVIEW: explanation] (standard inline style)
    # If the tag format ever changes in the master prompt, update these regexes to match.
    # BUG HISTORY: .*? with re.DOTALL was eating 65,760 chars (34% of Easley) — fixed 2026-03-30
    #              [^\[]*? prevents regex from crossing into adjacent [REVIEW: tags
    text = re.sub(r'\[REVIEW:[^\[]*?—\s*reporter confirm\]', '', text, flags=re.DOTALL)
    text = re.sub(r'\s*\[REVIEW:[^\]]*\]', '', text)
    text = re.sub(r'\s*\[FLAG:[^\]]*\]', '', text)
    text = re.sub(r'  +', ' ', text)
    return text


def build_review_locations(all_pages, anchor_map):
    """
    Option B: Use {R:N} anchors placed during inject_anchors() to get the
    exact p.XX l.YY for every LOW/N/A correction item.

    Items with no [REVIEW] tag (corrected field didn't embed one) never
    enter anchor_map — handled below with text search on original text.

    Fallback: if an anchor was dropped during formatting, fall back to
    text search on the original text.
    """
    if not anchor_map:
        return

    corrections = []
    if os.path.exists('correction_log.json'):
        with open('correction_log.json', encoding='utf-8') as f:
            corrections = json.load(f).get('corrections', [])

    # Build full set of LOW/N/A indices to process
    all_review_indices = set(anchor_map.keys())
    for i, c in enumerate(corrections):
        if c.get('confidence') in ('LOW', 'N/A'):
            all_review_indices.add(i)

    locations = {}
    for idx in sorted(all_review_indices):
        anchor = f'{{R:{idx}}}' if idx in anchor_map else None
        loc = None

        if anchor is not None:
            for page_idx, page_lines in enumerate(all_pages):
                for line_idx, line in enumerate(page_lines):
                    if anchor in line:
                        loc = f'p.{page_idx + 1} l.{line_idx + 1}'
                        break
                if loc:
                    break

        # Fallback: text search on original (handles dropped anchors and no-tag items)
        if not loc and idx < len(corrections):
            orig = corrections[idx].get('original', '').replace('\n', ' ').strip()
            words = orig.split()
            for phrase in [orig[-30:], orig[:30], ' '.join(words[1:5])]:
                if len(phrase) < 6:
                    continue
                for page_idx, page_lines in enumerate(all_pages):
                    for line_idx, line in enumerate(page_lines):
                        if phrase.lower() in line.lower():
                            loc = f'~p.{page_idx + 1} l.{line_idx + 1}'
                            break
                    if loc:
                        break
                if loc:
                    break

        locations[str(idx)] = loc or 'location unknown'

    out_path = os.path.join('FINAL_DELIVERY', 'review_locations.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(locations, f, indent=2)

    resolved = sum(1 for v in locations.values() if v != 'location unknown')
    print(f"[review_locations] {resolved}/{len(locations)} items located -> {out_path}")


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


def format_appearances_from_config(appearances):
    """Render appearances from CASE_CAPTION.json structured data.

    This is the authoritative path — used when 'appearances' key exists in config.
    Steno fallback is used only when config block is absent.

    Each entry in appearances list:
      role        — "ATTORNEY FOR PLAINTIFF" / "FOR THE DEFENDANT, ..."
      firm        — firm name (may wrap)
      address_1   — street
      address_2   — suite (optional)
      city_state_zip — full city/state/zip line
      phone       — phone number (optional)
      emails      — list of email addresses (optional)
      attorneys   — list of {name, zoom} dicts; OR "NOT PRESENT" string
    """
    lines = []
    for i, block in enumerate(appearances):
        if i > 0:
            lines.append("")

        # Role header — wrap long party descriptions at LINE_WIDTH
        role = block.get('role', '')
        if role and not role.rstrip().endswith(':'):
            role = role.rstrip() + ':'
        wrapped_role = wrap_line(role, width=LINE_WIDTH, hang=4)
        lines.extend(wrapped_role)

        # Firm name
        firm = block.get('firm', '')
        if firm:
            for l in wrap_line(f"    {firm}", width=LINE_WIDTH, hang=4):
                lines.append(l)

        # Address
        for field in ['address_1', 'address_2']:
            val = block.get(field, '').strip()
            if val:
                lines.append(f"    {val}")

        # City/state/zip — apply midpoint dot
        csz = block.get('city_state_zip', '').strip()
        if csz:
            csz = re.sub(r'([A-Za-z])\s+(\d{5}(?:-\d{4})?)\s*$', r'\1· \2', csz)
            lines.append(f"    {csz}")

        # Phone
        phone = block.get('phone', '').strip()
        if phone:
            lines.append(f"    {phone}")

        # Emails
        for email in block.get('emails', []):
            lines.append(f"    {email}")

        # Attorneys / NOT PRESENT
        attorneys = block.get('attorneys', [])
        if attorneys == 'NOT PRESENT' or attorneys == ['NOT PRESENT']:
            lines.append(f"    NOT PRESENT")
        elif attorneys:
            first = True
            for atty in attorneys:
                name = atty.get('name', '').strip()
                zoom = atty.get('zoom', False)
                suffix = ' (Zoom)' if zoom else ''
                if first:
                    lines.append(f"    BY: {name}{suffix}")
                    first = False
                else:
                    lines.append(f"    {name}{suffix}")

    # ALSO PRESENT block
    also_present = _cfg.get('also_present', [])
    if also_present:
        lines.append("")
        lines.append("    ALSO PRESENT:")
        for person in also_present:
            lines.append(f"    {person}")

    return paginate(lines, header="A P P E A R A N C E S:")


def format_appearances(raw_lines):
    """Format appearances — config-first, steno fallback.

    If CASE_CAPTION.json has an 'appearances' block, use it (authoritative).
    Otherwise fall back to steno-parsed appearances with a [REVIEW] flag.
    """
    # Config-first path — authoritative
    if _cfg.get('appearances'):
        return format_appearances_from_config(_cfg['appearances'])

    # Steno fallback — flag for CR review
    # [TECH DEBT: steno appearances is incomplete — Zoom attendees may not announce]
    raw_lines = list(raw_lines)
    raw_lines.insert(0, '[REVIEW: appearances sourced from steno only — verify list is complete, Zoom attendees may not have announced on the record]')

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
    pending_header = None  # accumulates multi-line party descriptions

    for line in stripped:
        if re.match(r'^(FOR THE|ATTORNEY FOR|ALSO PRESENT)', line):
            if cleaned:  # don't add blank at very start
                cleaned.append("")
            if line.rstrip().endswith(':'):
                # Complete single-line party description — output immediately
                wrapped = wrap_line(line, width=LINE_WIDTH, hang=4)
                cleaned.extend(wrapped)
                pending_header = None
            else:
                # Party description spans multiple lines (e.g. "FOR THE DEFENDANT, ALL STATE
                # INSURANCE COMPANY, solely as successor-in-interest" then "to NORTHBROOK...COMPANY:")
                # Accumulate until we see the closing colon
                pending_header = line
            in_block = True
        elif pending_header is not None:
            # Continuation of a multi-line party description — join until colon found
            pending_header = pending_header + ' ' + line
            if pending_header.rstrip().endswith(':'):
                # Complete — output the joined header
                wrapped = wrap_line(pending_header, width=LINE_WIDTH, hang=4)
                cleaned.extend(wrapped)
                pending_header = None
        else:
            if in_block:
                # Normalize (Via Zoom) → (Zoom) to match MB's house style
                line = re.sub(r'\(Via Zoom\)', '(Zoom)', line, flags=re.IGNORECASE)
                # Midpoint dot between state and zip: "Louisiana 70130" → "Louisiana· 70130"
                # MB's house style per accuracy report — applies to all address lines in appearances
                line = re.sub(r'([A-Za-z])\s+(\d{5}(?:-\d{4})?)\s*$', r'\1· \2', line)
                # Append (Zoom) to BY: lines for attorneys in ZOOM_ATTORNEYS list
                # Match on last name / partial name — case-insensitive
                if line.startswith('BY:') and '(Zoom)' not in line:
                    for zoom_name in ZOOM_ATTORNEYS:
                        if zoom_name in line.upper():
                            line = line.rstrip() + ' (Zoom)'
                            break
                # Firm name, address, email, BY: line — indent under party header
                wrapped = wrap_line(f"    {line}", width=LINE_WIDTH, hang=4)
                cleaned.extend(wrapped)
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
        # Always emit EXAMINATION header before BY line unless one was just added
        # Matches MB's format: EXAMINATION on its own line, then BY MR. NAME:
        if re.match(r'^BY\s+(MR\.|MS\.)', block):
            if not labeled or labeled[-1][0] != 'header':
                labeled.append(('header', 'EXAMINATION'))
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

        # Witness info: name line, address, and oath text that follow the witness intro.
        # Detected by name match OR known oath phrases — keeps all witness block
        # lines at the same 8-char indent in the output (matches MB's format).
        OATH_PHRASES = ['having been first duly sworn', 'was examined and testified',
                        'follows:', '(Witness sworn.)']
        if (WITNESS_NAME in block or WITNESS_LAST in block or
                any(phrase in block for phrase in OATH_PHRASES)):
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
            # Blank line before witness info block when following colloquy (matches MB)
            if prev_kind == 'colloquy':
                formatted.append('')
            # Indent witness name/address to match MB's format (~8 chars)
            formatted.append('        ' + text)
        elif kind == 'Q':
            body = re.sub(r'^Q\.\s+', '', text) if text.startswith('Q.') else text
            # Two-width wrap: first line body=42 chars, continuation=47 chars
            # [REVISIT:WRAP] ⚠ HACK — matches MB's page count (222 vs 223) but NOT verified.
            # cont_width=47 found by bracketing: 42→234pp, 52→214pp, 47→222pp (target 223).
            # MB's CAT shows 52 chars/line but we don't know how hang indent factors in.
            # HIGH PRIORITY: get MB to count chars on a finished Q/A line — owner: Scott.
            # Do NOT change this value without re-running page count check on Easley.
            # [TECH DEBT: first_width=42 not yet validated against MB's layout]
            wrapped = wrap_qa_line('     Q.   ', body, first_width=42, cont_width=47, hang=10)
            formatted.extend(wrapped)
        elif kind == 'A':
            body = re.sub(r'^A\.\s+', '', text) if text.startswith('A.') else text
            # [REVISIT:WRAP] ⚠ HACK — same as Q above. Matches page count, not verified.
            # HIGH PRIORITY: owner Scott — get MB to count chars on a finished Q/A line.
            # [TECH DEBT: first_width=42 not yet validated against MB's layout]
            wrapped = wrap_qa_line('     A.   ', body, first_width=42, cont_width=47, hang=10)
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
        raw_text = f.read()

    # Extract exhibit descriptions BEFORE anchor injection — cleanest source
    exhibit_descriptions = extract_exhibits(raw_text)

    text, anchor_map = inject_anchors(raw_text)
    sections = parse_file(text)

    # Parse exhibit numbers from steno index section (catches any not in whereupon parentheticals)
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

    # Pre-calculate index page count so section start numbers are correct.
    # build_index() is called twice: once here to measure, once at end to fill with real numbers.
    # [TECH DEBT: two-pass index build — pre-build just to count pages, then rebuild with real numbers]
    index_placeholder = build_index(99, 99, 99, 99, 99)
    num_index_pages = len(index_placeholder)

    # Reserve index slots
    idx_pos = len(all_pages)
    for _ in range(num_index_pages):
        all_pages.append(None)

    # Appearances — starts after caption + index pages
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

    # Build exhibit list for witness cert (steno-extracted, descriptions from whereupon lines)
    exhibit_pages = find_exhibit_pages(all_pages)
    all_exhibit_nums = sorted(set(exhibit_nums) | set(exhibit_descriptions.keys()) | set(exhibit_pages.keys()))
    steno_exhibits = [
        {
            'number':      num,
            'description': exhibit_descriptions.get(num, ''),
            'page':        exhibit_pages.get(num, 0),
        }
        for num in all_exhibit_nums
    ]

    # Witness Certificate — signature block only (exhibit list now lives in index)
    wcert_start = len(all_pages) + 1
    all_pages.extend(build_witness_cert())

    # Errata
    all_pages.extend(build_errata())

    # Build final index with correct page numbers and fill placeholders
    final_index_pages = build_index(app_start, stip_start, exam_start,
                                    cert_start, wcert_start, steno_exhibits)
    for i, pg in enumerate(final_index_pages):
        all_pages[idx_pos + i] = pg

    # Capture exact locations BEFORE stripping anchors
    build_review_locations(all_pages, anchor_map)

    # Strip {R:N} anchors — must not appear in final output
    all_pages = strip_anchors(all_pages)

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

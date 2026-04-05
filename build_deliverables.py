"""
build_deliverables.py — Generates all 5 analysis/support documents from cleaned_text.txt.

Produces:
  FINAL_DELIVERY/DELIVERY_CHECKLIST.txt
  FINAL_DELIVERY/DEPOSITION_SUMMARY.txt
  FINAL_DELIVERY/EXHIBIT_INDEX.txt
  FINAL_DELIVERY/MEDICAL_TERMS_LOG.txt
  FINAL_DELIVERY/PROOF_OF_WORK.txt
  FINAL_DELIVERY/QA_FLAGS.txt
"""
import re
import os
import json
from datetime import date

# --- Load case config ---
# CASE_CAPTION.json is authoritative — overrides depo_config.json (matches format_final.py logic)
with open('depo_config.json', encoding='utf-8') as _cfg_f:
    _cfg = json.load(_cfg_f)
if os.path.exists('CASE_CAPTION.json'):
    with open('CASE_CAPTION.json', encoding='utf-8') as _cf:
        _cfg.update(json.load(_cf))

_plaintiff = _cfg.get('plaintiff', 'UNKNOWN')
_defendant = _cfg.get('defendant', 'UNKNOWN')
CASE_NAME      = f"{_plaintiff} v. {_defendant}"
CASE_SHORT     = _cfg.get('case_short', 'Unknown_Case')
DOCKET         = _cfg.get('docket', 'UNKNOWN')
DIVISION       = _cfg.get('division', '')
COURT          = _cfg.get('court', 'UNKNOWN')
WITNESS        = _cfg.get('witness_name', 'UNKNOWN')
DEPO_DATE      = _cfg.get('depo_date', 'UNKNOWN')
REPORTER       = _cfg.get('reporter_name', 'UNKNOWN')
EXAMINING_ATTY = _cfg.get('examining_atty', 'UNKNOWN')
RUN_DATE       = date.today().strftime("%B %d, %Y")

INPUT_FILE  = 'corrected_text.txt'
OUTPUT_DIR  = 'FINAL_DELIVERY'

HEADER_BAR = "=" * 80

def header(title):
    return f"{HEADER_BAR}\n{title}\n{HEADER_BAR}\n"

def section(title):
    return f"\n{'-' * 80}\n{title}\n{'-' * 80}\n"


# =========================================================
# Read source
# =========================================================

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')


# =========================================================
# DELIVERY CHECKLIST
# =========================================================

def build_checklist():
    return f"""{header(f"DELIVERY CHECKLIST")}Case: {CASE_NAME}
Docket No.: {DOCKET} | Witness: {WITNESS} | Date: {DEPO_DATE}
Reporter: {REPORTER}
{HEADER_BAR}

REPORTER PRE-DELIVERY ACTIONS
{'-' * 80}
\u25a1  Transcript reviewed by reporter (full audio pass)
\u25a1  All AUDIO REVIEW flags resolved (see QA_FLAGS.txt)
\u25a1  All [CORRECTED: ___] and [REVIEW: ___] tags verified against audio
\u25a1  *REPORTER CHECK HERE* placeholder resolved
\u25a1  Caption page location confirmed (address and zip code verified)
\u25a1  All exhibit descriptions verified against original marked exhibits
\u25a1  Exhibit Bates numbers verified
\u25a1  "ROUGH DRAFT" designation REMOVED from final version

CERTIFICATION
{'-' * 80}
\u25a1  CCR license number added to certification page
\u25a1  Certification page signed by reporter
\u25a1  Certification date filled in (date of signing, not deposition date)

FORMATTING REVIEW
{'-' * 80}
\u25a1  25 numbered lines per page throughout
\u25a1  Page numbers verified (1 through final)
\u25a1  Speaker labels consistent (Q. / A. / MR. / MS. / THE WITNESS:)
\u25a1  Em dashes used for interruptions; ellipses for trailing off
\u25a1  Off-record transitions preserved: "(Off the record.)"
\u25a1  Examination header present: EXAMINATION BY {EXAMINING_ATTY}:
\u25a1  Stipulation pages formatted correctly
\u25a1  Appearances pages formatted correctly
\u25a1  Exhibit index page verified against physical exhibits

FINAL DELIVERY
{'-' * 80}
\u25a1  Delivered to:  {EXAMINING_ATTY}
\u25a1  Copy sent to:  [opposing counsel — verify from appearances page]
\u25a1  Invoice sent
\u25a1  Delivery receipt confirmed

INVOICE NOTES
{'-' * 80}
\u25a1  Transcript rate: $_____ per page
\u25a1  Copy rate: $_____ per page
\u25a1  Total pages: _____
\u25a1  Rush/expedite charges (if applicable): _____
\u25a1  Total invoice amount: $_____
\u25a1  Invoice date: _____

{HEADER_BAR}
"""


# =========================================================
# DEPOSITION SUMMARY
# =========================================================

def parse_appearances():
    """Extract attorney blocks from the appearances section."""
    in_app = False
    blocks = []
    current = []
    for line in lines:
        s = line.strip()
        if 'A P P E A R A N C E S' in s:
            in_app = True
            continue
        if in_app:
            if re.match(r'^(S T I P U L A T I O N|STIPULATION|THE VIDEOGRAPHER|BY MR\.|EXAMINATION)', s):
                break
            if s:
                current.append(s)
            elif current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks

def build_summary():
    app_blocks = parse_appearances()
    app_text = ""
    for block in app_blocks:
        app_text += "  " + "\n  ".join(block) + "\n\n"

    return f"""{header("DEPOSITION SUMMARY\nAI-Prepared \u2014 For Attorney Review Only\nNot a Legal Document / Not Certified")}
CASE:          {CASE_NAME}
DOCKET:        No. {DOCKET}, Division "{DIVISION}"
COURT:         {COURT}
WITNESS:       {WITNESS}
DATE:          {DEPO_DATE}
REPORTER:      {REPORTER}
PROCESSED:     {RUN_DATE}
{section("ATTORNEYS / APPEARANCES (from rough transcript)")}
{app_text}
{HEADER_BAR}
"""


# =========================================================
# EXHIBIT INDEX
# =========================================================

def parse_exhibits():
    """Extract exhibit entries from the index section of the transcript."""
    in_index = False
    exhibits = []
    for line in lines:
        s = line.strip()
        if 'E X H I B I T S' in s or 'EXHIBITS' in s:
            in_index = True
            continue
        if in_index:
            if re.match(r'^(A P P E A R A N C E S|APPEARANCES)', s):
                break
            m = re.match(r'Exhibit\s+No\.?\s+(\d+)\s+(.*)', s, re.IGNORECASE)
            if m:
                exhibits.append((m.group(1), m.group(2).strip()))
            elif exhibits and s and not re.match(r'^\d+\s', s):
                # continuation line
                exhibits[-1] = (exhibits[-1][0], exhibits[-1][1] + ' ' + s)
    return exhibits

def build_exhibit_index():
    exhibits = parse_exhibits()
    rows = ""
    for num, desc in exhibits:
        rows += f"  Exhibit No. {num:<6} {desc}\n"
    if not rows:
        rows = "  [Exhibits not parsed from this source — verify against physical index]\n"

    return f"""{header("EXHIBIT INDEX")}Case: {CASE_NAME}
Docket No.: {DOCKET} | Witness: {WITNESS} | Date: {DEPO_DATE}
{HEADER_BAR}

{rows}
{'-' * 80}
NOTE: Descriptions extracted from rough transcript index page.
Verify all Bates numbers and descriptions against physical exhibits.
Review for duplicate or missing entries before finalizing.
{HEADER_BAR}
"""


# =========================================================
# MEDICAL TERMS LOG
# =========================================================

MEDICAL_TERMS = [
    'fracture', 'injury', 'surgery', 'pain', 'treatment', 'diagnosis',
    'hospital', 'physician', 'doctor', 'medical', 'disability', 'chronic',
    'prescription', 'therapy', 'rehabilitation', 'impairment', 'workers comp',
    'workers\' comp', 'work comp', 'accident', 'trauma', 'mri', 'x-ray',
    'orthopedic', 'neurological', 'psychological', 'psychiatric',
]

def build_medical_log():
    found = []
    for i, line in enumerate(lines):
        lower = line.lower()
        for term in MEDICAL_TERMS:
            if term in lower:
                found.append((i + 1, term, line.strip()))
                break

    if found:
        rows = f"{'Line':<8} {'Term':<20} Context\n" + "-" * 70 + "\n"
        for lineno, term, context in found[:50]:
            rows += f"{lineno:<8} {term:<20} {context[:60]}\n"
        summary = f"  Medical/WC terms found: {len(found)}\n  Medical review required: YES"
    else:
        rows = "  No substantive medical or workers' compensation terms identified.\n"
        summary = "  Medical terms found: 0\n  Medical review required: NO"

    return f"""{header("MEDICAL TERMS LOG")}Case: {CASE_NAME}
Docket No.: {DOCKET} | Witness: {WITNESS} | Date: {DEPO_DATE}
{HEADER_BAR}

{rows}
{section("SUMMARY")}
{summary}
{HEADER_BAR}
"""


# =========================================================
# PROOF OF WORK
# =========================================================

CORRECTION_LOG_FILE = 'correction_log.json'

def load_correction_log():
    """Load correction_log.json if it exists. Returns list of correction dicts."""
    if os.path.exists(CORRECTION_LOG_FILE):
        with open(CORRECTION_LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('corrections', []), data
    return [], {}

def build_proof_of_work():
    corrections, log_meta = load_correction_log()

    if corrections:
        # Build v3-style correction log from ai_engine output
        # Format: LINE_NNN | original | corrected | CONF | reason
        COL = 56  # column width for original/corrected text
        rows = (
            f"{'Format:':<8} LINE     | {'ORIGINAL':<{COL}} | {'CORRECTED':<{COL}} | CONF   | REASON\n"
            + "-" * 80 + "\n\n"
        )
        high_count   = 0
        review_count = 0
        for c in corrections:
            line_ref  = f"LINE {c.get('line_approx', '?')}"
            original  = str(c.get('original',  '')).strip()
            corrected = str(c.get('corrected', '')).strip()
            conf      = str(c.get('confidence', '')).upper()
            reason    = str(c.get('reason', '')).strip()

            # Truncate long fields for column alignment
            orig_disp = (original[:COL-3]  + '...') if len(original)  > COL else original
            corr_disp = (corrected[:COL-3] + '...') if len(corrected) > COL else corrected

            rows += f"{line_ref:<10} | {orig_disp:<{COL}} | {corr_disp:<{COL}} | {conf:<6} | {reason}\n"

            if conf == 'HIGH':
                high_count += 1
            elif conf in ('MEDIUM', 'LOW'):
                review_count += 1

        total = len(corrections)
        model = log_meta.get('model', 'claude-sonnet-4-6')

        ai_section = (
            f"Engine corrections:  {total} total\n"
            f"  HIGH confidence:   {high_count}\n"
            f"  Needs review:      {review_count}\n"
            f"  Model:             {model}\n\n"
        )
        review_note = (
            f"  All [REVIEW: ___] tags in the transcript require reporter audio verification.\n"
            f"  {review_count} item(s) flagged for review — see QA_FLAGS.txt for full list."
        )
    else:
        # No correction log — ai_engine.py has not been run yet
        rows = "  [correction_log.json not found — run ai_engine.py to generate AI corrections]\n"
        ai_section = "  AI correction pass not yet run.\n"
        review_note = "  Run ai_engine.py and re-run build_deliverables.py to populate this section."

    return f"""{header("PROOF OF WORK\nAI Processing Record \u2014 Not a Legal Document")}Case: {CASE_NAME}
Docket No.: {DOCKET} | Witness: {WITNESS} | Date: {DEPO_DATE}
Engine: MASTER_DEPOSITION_ENGINE_v4
Processing Date: {RUN_DATE}
{HEADER_BAR}
{section("SECTION 1 — PRE-PROCESSING (steno_cleanup.py)")}
  Mechanical artifact removal — no judgment required.
  Changes: tilde removal, double-underscore → em dash, docket underscore → hyphen,
           compound word fixes, double-@ correction, encoding artifact removal.
  (Run steno_cleanup.py with --verbose for full counts.)
{section("SECTION 2 — AI CORRECTION PASS (ai_engine.py)")}
{ai_section}{rows}
{section("SECTION 3 — ITEMS REQUIRING REPORTER REVIEW")}
{review_note}
{HEADER_BAR}
"""


# =========================================================
# QA FLAGS
# =========================================================

QA_PATTERNS = [
    (r'\bREPORTER CHECK HERE\b', 'REPORTER CHECK REQUIRED', 'Placeholder left by engine — content unclear from audio'),
    (r'\[CORRECTED:', 'CORRECTION APPLIED', 'Engine made a correction — verify against audio'),
    (r'\[REVIEW:', 'REVIEW REQUIRED', 'Engine flagged uncertain content'),
    (r'\[FLAG:', 'FLAG', 'Engine flagged a procedural or content issue'),
    (r'\bUhmm\b|\bUhh\b|\bUmm\b', 'FILLER WORD', 'Filler word — remove per style rules or preserve per reporter preference'),
    (r'_{2,}', 'STENO ARTIFACT', 'Double underscore — possible em dash not converted'),
    (r'@@', 'EMAIL ERROR', 'Double @ in email address — correct before delivery'),
    (r'\bblacktop\b', 'POSSIBLE MISRECOGNITION', '"blacktop" may be "White Top" — verify in context'),
    (r'\bbrat spot', 'POSSIBLE MISRECOGNITION', '"brat spot" likely "bright spot" (seismic term)'),
]

def build_qa_flags():
    flags = []
    for pattern, flag_type, description in QA_PATTERNS:
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                flags.append((i + 1, flag_type, description, line.strip()[:80]))

    if flags:
        rows = ""
        for lineno, flag_type, desc, context in flags[:60]:
            rows += f"[Line {lineno:4d}] {flag_type}\n"
            rows += f"           {desc}\n"
            rows += f"           Context: {context}\n\n"
    else:
        rows = "  No QA flags detected.\n"

    return f"""{header("QA FLAGS \u2014 REPORTER ACTION REQUIRED")}Case: {CASE_NAME}
Docket No.: {DOCKET} | Witness: {WITNESS} | Date: {DEPO_DATE}
{HEADER_BAR}

NOTE: Line numbers are approximate (from cleaned_text.txt, not final pages).
Cross-reference against the final formatted transcript before delivery.

{rows}
{'-' * 80}
Total flags: {len(flags)}
{HEADER_BAR}
"""


# =========================================================
# WRITE ALL FILES
# =========================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

files = {
    'DELIVERY_CHECKLIST.txt':  build_checklist(),
    # DEPOSITION_SUMMARY.txt is produced by build_summary.py (Haiku AI) — do not duplicate here
    'EXHIBIT_INDEX.txt':        build_exhibit_index(),
    'MEDICAL_TERMS_LOG.txt':   build_medical_log(),
    'PROOF_OF_WORK.txt':       build_proof_of_work(),
    'QA_FLAGS.txt':             build_qa_flags(),
}

for filename, content in files.items():
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Written: {filename}  ({len(content):,} chars)")

print(f"\nAll deliverables written to {OUTPUT_DIR}/")

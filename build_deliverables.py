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
from datetime import date

# --- Case constants ---
CASE_NAME      = "Yellow Rock, LLC, et al. v. Westlake US 2 LLC, et al."
DOCKET         = "202-001594"
DIVISION       = "H"
COURT          = "14th Judicial District Court, Parish of Calcasieu, Louisiana"
WITNESS        = "Thomas L. Easley"
DEPO_DATE      = "Friday, March 13, 2026"
REPORTER       = "Marybeth E. Muir, CCR, RPR"
EXAMINING_ATTY = "Walker Hobby, Esq. (Susman Godfrey LLP)"
RUN_DATE       = date.today().strftime("%B %d, %Y")

INPUT_FILE  = 'cleaned_text.txt'
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
\u25a1  Duplicate Exhibit 142 on index resolved
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
\u25a1  Examination header present: EXAMINATION BY MR. HOBBY:
\u25a1  Stipulation pages formatted correctly
\u25a1  Appearances pages formatted correctly
\u25a1  Exhibit index page verified against physical exhibits

FINAL DELIVERY
{'-' * 80}
\u25a1  Delivered to:  {EXAMINING_ATTY}
\u25a1  Copy sent to:  Thomas J. Madigan, Esq. (Sher Garner — Plaintiff)
\u25a1  Rough draft delivered to: MS. CURTIS (requested on record)
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

{'-' * 80}
NOTES:
  - Deposition terminated by plaintiff's counsel before completion.
  - Westlake stated on record it was prepared to continue.
  - This was a VIDEOTAPED deposition.
  - Rough draft was requested by MS. CURTIS at conclusion.
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
{section("KEY FACTS FROM RECORD")}
  - Deposition terminated by plaintiff's counsel before completion.
  - Westlake stated on record it was prepared to continue.
  - Rough draft requested by MS. CURTIS at conclusion.
  - Videotaped deposition.
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

# Known corrections applied by steno_cleanup.py
KNOWN_CORRECTIONS = [
    ("E_mail / E_mails", "E-mail / E-mails", "Steno artifact — underscore for hyphen", "1.00"),
    ("day_to_day", "day-to-day", "Steno artifact", "1.00"),
    ("asirianni@@windelsmarx.com", "asirianni@windelsmarx.com", "Double-@ steno error", "1.00"),
    ("~ (tilde)", "(removed)", "Steno artifact — tilde used as filler", "1.00"),
    ("__ (double underscore)", "— (em dash)", "Steno artifact — double underscore for em dash", "0.99"),
    ("docket underscores (202_001594)", "202-001594", "Docket number formatting", "1.00"),
]

def count_corrections():
    counts = {}
    for old, new, _, _ in KNOWN_CORRECTIONS:
        counts[old] = text.count(new)  # approximate
    return counts

def build_proof_of_work():
    rows = ""
    for i, (old, new, reason, conf) in enumerate(KNOWN_CORRECTIONS, 1):
        rows += f"{i:2d}. \"{old}\" \u2192 \"{new}\"\n"
        rows += f"    Reason: {reason}  |  Confidence: {conf}\n\n"

    return f"""{header("PROOF OF WORK\nAI Processing Record \u2014 Not a Legal Document")}Case: {CASE_NAME}
Docket No.: {DOCKET} | Witness: {WITNESS} | Date: {DEPO_DATE}
Engine: MASTER_DEPOSITION_ENGINE_v4
Processing Date: {RUN_DATE}
{HEADER_BAR}
{section("AUTOMATIC CORRECTIONS APPLIED (HIGH CONFIDENCE)")}
{rows}
{section("ITEMS REQUIRING REPORTER REVIEW")}
  All [CORRECTED: ___] tags in the transcript require audio verification.
  All [REVIEW: ___] tags require manual review before finalizing.
  See QA_FLAGS.txt for full list.
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
    'DEPOSITION_SUMMARY.txt':  build_summary(),
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

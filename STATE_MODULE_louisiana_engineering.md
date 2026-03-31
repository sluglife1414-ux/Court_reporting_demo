# ═══════════════════════════════════════════════════════════════════
# STATE MODULE — LOUISIANA ENGINEERING
# ═══════════════════════════════════════════════════════════════════
# Compatible with: MASTER_DEPOSITION_ENGINE v4.0+
# State:           Louisiana
# Case Type:       Engineering Depositions
# Author:          Scott + Claude
# Version:         1.1
# Last Updated:    2026-03-22
# Change v1.0→1.1: Fixed objection format per KB-001 (Objection to form., not Objection, form.)
# ═══════════════════════════════════════════════════════════════════


===========================================================
MODULE DECLARATION
===========================================================
STATE:      Louisiana
CASE TYPE:  Engineering
ACTIVATE:   Engineering case type rules in Layer 4 of core engine.
OVERLAY:    None (single state, single case type)


===========================================================
GOVERNING LAW
===========================================================
  - Louisiana CCP Articles 1421–1459
  - Louisiana CCP Article 1450 (use of depositions at trial)
  - Louisiana CCP Article 1442 (corporate representative depositions)
  - Louisiana Code of Evidence
  - LAPELS Laws: LA R.S. 37:681–703
  - LAPELS Rules: LAC Title 46, Part LXI


===========================================================
PARTY LABELING
===========================================================
  Standard civil:
    - Plaintiff's Attorney / Defense Attorney
    - OR: Petitioner's Attorney / Respondent's Attorney
      (use whichever matches case_info.txt)

  Corporate rep depositions (Art. 1442):
    - Identify and tag all designee testimony.
    - FLAG testimony outside designated topics:
      [FLAG: OUTSIDE DESIGNATED TOPIC]
    - FLAG inconsistencies with documents:
      [FLAG: INCONSISTENT WITH EXHIBIT]


===========================================================
CASE NUMBER FORMAT
===========================================================
  Louisiana civil:  [Parish] [Division]-[Year]-[Number]
  Use whatever format appears in case_info.txt exactly.


===========================================================
DATE FORMAT
===========================================================
  Month Day, Year → "March 15, 2023"


===========================================================
OBJECTIONS — NORMALIZE TO THESE EXACT FORMS
===========================================================
  ⚠️  KB-001 OVERRIDE: Louisiana standard is "Objection to form." — NOT "Objection, form."
      The comma-form was v1.0 error. v1.1 corrects it.

  Standard:
    Objection to form.
    Objection, leading.
    Objection, relevance.
    Objection, foundation.
    Objection, hearsay.
    Objection, privilege.

  Multi-basis: separate with semicolon (not comma)
    Objection to form; vague.
    Objection; mischaracterizes the document.
    Objection; assumes facts not in evidence.

  Engineering-specific:
    Objection, calls for speculation.
    Objection, outside licensed discipline.
    Objection, calls for legal conclusion.
    Objection, misstates engineering standard.
    Objection, assumes facts not in evidence.

  DO NOT normalize wording beyond these forms.
  Preserve exactly what attorney said. Correct only obvious steno errors.


===========================================================
RECORD TRANSITIONS
===========================================================
  Preserve exactly as spoken:
    OFF THE RECORD
    BACK ON THE RECORD
    (Off the record discussion.)

  Missing ruling → [FLAG: RULING NOT RECORDED]
  Missing sworn statement → [FLAG: SWORN STATEMENT MISSING]
  Unclear Louisiana procedural phrase → [CHECK: LOUISIANA RULE]


===========================================================
EXAMINATION HEADERS
===========================================================
  EXAMINATION BY MR. [LASTNAME]:
  EXAMINATION BY MS. [LASTNAME]:
  CROSS-EXAMINATION BY MR. [LASTNAME]:
  CROSS-EXAMINATION BY MS. [LASTNAME]:
  REDIRECT EXAMINATION BY MR. [LASTNAME]:
  REDIRECT EXAMINATION BY MS. [LASTNAME]:


===========================================================
ENGINEERING RULES — LAPELS COMPLIANCE
===========================================================
  All engineering opinions MUST be tied to at least one of:
    - Calculations
    - Published standards (ASCE, ASTM, ACI, API, NFPA, IBC,
      Louisiana Building Code)
    - Drawings or specifications
    - Field inspections or test data

  Unsupported opinion → [FLAG: ENGINEERING OPINION LACKS FOUNDATION]

  LAPELS compliance checks:
    - Engineer must testify within licensed discipline.
    - Must not misrepresent qualifications.
    - Engineering judgment must be traceable to accepted principles.
    - Possible ethics issue → [FLAG: POSSIBLE LAPELS ETHICS ISSUE]

  Technical terminology:
    Normalize units:         psi | kN | MPa | ft-lbs | kPa
    Normalize abbreviations: FEA | NDT | QA/QC | P.E. | EOR | RFI | ASI
    Preserve all formulas and numerical data exactly as spoken.
    Unclear term → [FLAG: UNCLEAR ENGINEERING TERM — original: ___]


===========================================================
EXHIBIT LABELING CONVENTION
===========================================================
  Standard format: "Exhibit [Letter or Number]"
  Examples: Exhibit A | Exhibit 1 | Exhibit 12


===========================================================
CERTIFICATION PAGE
===========================================================
  Louisiana civil deposition certification must include:
    - Reporter name and license number
    - Statement that the witness was duly sworn
    - Statement that the transcript is a true and accurate record
    - Reporter signature line
    - Date of certification

  Missing or incomplete → [FLAG: LOUISIANA CERTIFICATION INCOMPLETE]

  NOTE: Reporter must sign before delivery. AI formats only.


===========================================================
JURISDICTION-SPECIFIC FLAG
===========================================================
  Use this format for all Louisiana procedural uncertainties:
    [CHECK: LOUISIANA RULE]


===========================================================
GLOSSARY TERMS — LOUISIANA ENGINEERING (SEED LIST)
===========================================================
  Supplement with glossary.* file if available.
  These are baseline terms — correct silently at HIGH confidence.

  LAPELS         Louisiana Professional Engineering and Land Surveying Board
  EOR            Engineer of Record
  RFI            Request for Information
  ASI            Architect's Supplemental Instruction
  QA/QC          Quality Assurance / Quality Control
  NDT            Non-Destructive Testing
  FEA            Finite Element Analysis
  P.E.           Professional Engineer
  ACI 318        American Concrete Institute Building Code
  ASCE 7         Minimum Design Loads for Buildings and Other Structures
  IBC            International Building Code
  NFPA           National Fire Protection Association
  API            American Petroleum Institute


===========================================================
MAINTAINER NOTES
===========================================================
VERSION:      1.1
STATE:        Louisiana
CASE TYPE:    Engineering
ENGINE:       Compatible with MASTER_DEPOSITION_ENGINE v4.0+

TO EXPAND:    Add additional objection types or glossary terms
              directly in this file. Do not edit the core engine.
TO COMBINE:   This module can be loaded alongside other modules
              if the engine supports stacking.

===========================================================
RULES EXTRACTED FROM LA STATE SPEC PDFs
[SOURCE: Court_Transcript_Format.pdf | Deposition_Transcript_Format.pdf]
Added: 2026-03-30
===========================================================

--- SECTION: PAGE LAYOUT AND LINE NUMBERING ---
[SOURCE: Court_Transcript_Format.pdf]
  - 32 lines per page (court transcript format — as demonstrated in sample).
  - Line numbers printed flush left, one per line.
  - Text formatted in Courier monospace typeface.

[SOURCE: Deposition_Transcript_Format.pdf]
  - 25 lines per page (deposition transcript format — as demonstrated in sample).
  - Line numbers printed flush left, one per line.
  - Text formatted in Courier monospace typeface.
  - [REVISIT] Confirm 25 vs 32 line-per-page split: court = 32, deposition = 25.
    Both confirmed by sample PDFs but must be verified against board rules.

--- SECTION: TITLE PAGE / CAPTION FORMAT ---
[SOURCE: Court_Transcript_Format.pdf]
  Court transcript caption (criminal):
    Line 1: Court name (e.g., CRIMINAL DISTRICT COURT)
    Line 2: Parish name (e.g., PARISH OF ORLEANS)
    Line 3: STATE OF LOUISIANA
    Then: Case style block — party vs. party with NO. and SECTION on right
    Then: Bold centered hearing type (e.g., "Probable Cause Hearing")
    Then: Narrative intro paragraph: "Testimony and Notes of Evidence, taken..."
    Then: APPEARANCES: block with indented attorney name + role

[SOURCE: Deposition_Transcript_Format.pdf]
  Deposition caption (civil):
    Line 1: [Judicial District] JUDICIAL DISTRICT COURT (ALL CAPS, centered)
    Line 2: PARISH OF [Parish] (centered)
    Line 3: STATE OF LOUISIANA (centered)
    Then: NO. [number] flush left | DIVISION "[letter]" flush right on same line
    Then: Case style — plaintiff vs. defendant (centered)
    Then: Narrative intro: "Deposition of [WITNESS NAME], taken at [location]..."
    Witness name in bold in the intro narrative.
    Then: "Reported by:" block with reporter name (bold) + credentials.

--- SECTION: APPEARANCES PAGE FORMAT ---
[SOURCE: Deposition_Transcript_Format.pdf]
  Appearances page format:
    - APPEARANCES: header flush left (no bold, no underline in sample).
    - Each firm: Firm name on first line, then "(By: [FIRSTNAME LASTNAME], Esq.)"
      on next line (bold), then street address, then city/state/zip.
    - Role label centered below each attorney block: "ATTORNEY FOR PLAINTIFF" etc.
    - Blank line between each attorney entry.

--- SECTION: INDEX PAGE ---
[SOURCE: Deposition_Transcript_Format.pdf]
  Deposition index page contains three sections:
    1. INDEX (centered, underlined)
    2. AGREEMENT OF COUNSEL — page number
    3. EXAMINATION BY — attorney name + page number (indented under "EXAMINATION BY")
    4. EXHIBITS — exhibit label + description + page number (indented under "EXHIBITS")
    5. REPORTER'S PAGE — page number
    6. REPORTER'S CERTIFICATE — page number

[SOURCE: Court_Transcript_Format.pdf]
  Court transcript uses WITNESS INDEX and EXHIBIT INDEX as separate pages.
  - WITNESS INDEX: bold centered header; witness name(s) bold, examination types indented.
  - EXHIBIT INDEX: columns OFR'D and REC'D (offered and received page numbers).

--- SECTION: STIPULATION FORMAT ---
[SOURCE: Deposition_Transcript_Format.pdf]
  Standard Louisiana deposition stipulation language:
    "It is stipulated and agreed by and between counsel for the parties that the
    deposition of [WITNESS], is hereby taken under Article 1421 Et Seq., of the
    Louisiana Code of Civil Procedure, in accordance with law, pursuant to notice;
    That the formalities, such as reading, signing, sealing, certification, and
    filing, are specifically waived;
    That all objections, save those as to the form of the questions, are hereby
    reserved until such time as this deposition, or any part thereof, may be used
    or sought to be used in evidence."
  Then: *** separator
  Then: Reporter's name + "officiated in administering the oath" statement.

  [REVISIT] If formalities are NOT waived, the stipulation block changes.
  Verify with MB whether her standard is always the waiver form or case-dependent.

--- SECTION: WITNESS INTRODUCTION FORMAT ---
[SOURCE: Deposition_Transcript_Format.pdf]
  After stipulation, witness is introduced:
    [WITNESS FULL NAME], (bold, centered)
    [street address, city, state, zip], (address on next line)
    after having been first duly sworn by the Certified Court Reporter, did testify as follows:
    Then: - EXAMINATION - (centered, with em-dashes)
    Then: BY MR. [LASTNAME]: (flush left)

[SOURCE: Court_Transcript_Format.pdf]
  Court format uses:
    [WITNESS FULL NAME, TITLE],
    [employer], after having been first duly sworn, did testify as follows:
    Then: - DIRECT EXAMINATION - (centered, with em-dashes, bold)
    Then: BY MS. [LASTNAME]: (flush left)

--- SECTION: Q/A FORMAT ---
[SOURCE: Deposition_Transcript_Format.pdf]
  - Q and A labels are bold italic in the sample PDF.
  - Q and A are indented (approximately 5 chars) from left margin.
  - Answer text begins on same line as A.
  - [REVISIT] Confirm bold-italic Q/A labels vs. plain with MB — may be reporter style.

--- SECTION: COLLOQUY / SPEAKER LABEL FORMAT ---
[SOURCE: Deposition_Transcript_Format.pdf]
  Colloquy speakers formatted as: "MR. [LASTNAME]:" (bold) then text indented.
  "THE WITNESS:" (bold) then text indented.
  Indented text runs approximately 14 characters from left margin.

[SOURCE: Court_Transcript_Format.pdf]
  Same convention. Bold speaker label, indented continuation text.
  "MS. [LASTNAME]:" | "THE COURT:" | "THE WITNESS:"

--- SECTION: OFF-THE-RECORD NOTATION ---
[SOURCE: Deposition_Transcript_Format.pdf]
  Format confirmed: (Off-the-record) — parentheses, hyphenated, sentence case.
  "Back on the Record." — capital R on Record.

--- SECTION: REPORTER'S PAGE FORMAT ---
[SOURCE: Court_Transcript_Format.pdf + Deposition_Transcript_Format.pdf]
  Both formats use identical Reporter's Page text:
    Header: REPORTER'S PAGE (bold, centered, underlined in court format)
    "I, [REPORTER NAME], Certified Court Reporter in and for the State of Louisiana,
    the officer, as defined in Rule 28 of the Federal Rules of Civil Procedure
    and/or Article 1434(B) of the Louisiana Code of Civil Procedure, before whom
    this proceeding was taken, do hereby state on the Record:"
    Para 1: Dashes (--) used for pauses/changes in thought/talkovers statement.
    Para 2: Phonetically spelled words statement.
    Then: Signature line — reporter name (bold) + "Certified Court Reporter" +
          "Registered Professional Reporter"

--- SECTION: REPORTER'S CERTIFICATE FORMAT ---
[SOURCE: Court_Transcript_Format.pdf]
  Court transcript certificate text:
    "This certification is valid only for a transcript accompanied by my original
    signature and original required seal on this page."
    Certifies: stenotype method | prepared/transcribed by reporter or under
    personal direction | true and correct | prepared in compliance with transcript
    format guidelines required by statute, or by rules of the board, or by the
    Supreme Court of Louisiana | reporter not of counsel, not related, not interested.

[SOURCE: Deposition_Transcript_Format.pdf]
  Deposition certificate text (EXPANDED — more fields than court format):
    Same opening certification re: transcript validity.
    ADDS: witness sworn upon authority of R.S. 37:2554.
    ADDS: Specifies page count ("did testify as hereinbefore set forth in the
          foregoing [X] pages").
    ADDS: Compliance with Louisiana Certified Shorthand Reporter Board rules.
    ADDS: Full financial arrangement disclosure statement.
    ADDS: Prohibition on contractual relationships statement (CCP Art. 1434).
    ADDS: No knowledge of prohibited employment or contractual relationship.
    "That I am not of counsel, not related to counsel or the parties herein,
    nor am I otherwise interested in the outcome of this matter."

  KEY DIFFERENCE FROM COURT CERTIFICATE:
    Deposition certificate is LONGER and includes:
    (1) Financial arrangement disclosure
    (2) Contractual relationship prohibition (CCP Art. 1434)
    (3) Prohibited employment statement
    These are NOT present in the court transcript certificate.

  ⚠️ FLAG TRIGGER: If deposition certificate is missing the financial/contractual
     language → [FLAG: LOUISIANA CERTIFICATION INCOMPLETE — depo cert requires
     financial arrangement + CCP 1434 prohibition language]

--- SECTION: SEPARATOR MARKERS ---
[SOURCE: Court_Transcript_Format.pdf + Deposition_Transcript_Format.pdf]
  End-of-hearing marker: * * * * * (five asterisks with spaces)
  Section separator within deposition: * * * (three asterisks with spaces)

--- SECTION: GOVERNING AUTHORITY FOR CERTIFICATION ---
[SOURCE: Deposition_Transcript_Format.pdf]
  Reporter administers oath under authority of R.S. 37:2554.
  Reporter is "the officer" as defined in Rule 28 FRCP and/or CCP Art. 1434(B).
  Compliance with "transcript format guidelines required by statute or by the Rules
  of the Louisiana Certified Shorthand Reporter Board."

===========================================================
LOUISIANA CERTIFIED SHORTHAND REPORTER BOARD — WEB RESEARCH
[SOURCE: lacourtreporterboard.org]
Research date: 2026-03-30
===========================================================

FETCH STATUS: WebFetch tool was not available during this session.
The URL https://lacourtreporterboard.org/ could not be automatically fetched.

ACTION REQUIRED: Scott or MB should manually review the following pages
on the LA board website for transcript format rules, regulations, and standards:
  - https://lacourtreporterboard.org/
  - Look for: Rules/Regulations section, Transcript Format Guidelines,
    Board Orders, Advisory Opinions
  - Governing statute: R.S. 37:2551 et seq.
  - Rules cite: Rules of the Louisiana Certified Shorthand Reporter Board

KNOWN STATUTORY REFERENCES (from deposition certificate language in sample PDFs):
  - R.S. 37:2554: Authority for reporter to administer oath
  - CCP Art. 1434: Prohibition on contractual relationships
  - CCP Art. 1434(B): Definition of reporter as "officer" (FRCP Rule 28)
  - "Transcript format guidelines required by statute or by the Rules of
    the Louisiana Certified Shorthand Reporter Board"

[REVISIT] After manual review, append any board rules found here with
[SOURCE: lacourtreporterboard.org — manually verified DATE] tags.

═══════════════════════════════════════════════════════════════════
END OF STATE MODULE — LOUISIANA ENGINEERING v1.0
═══════════════════════════════════════════════════════════════════

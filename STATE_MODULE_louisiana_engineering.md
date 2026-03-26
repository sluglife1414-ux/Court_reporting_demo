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

═══════════════════════════════════════════════════════════════════
END OF STATE MODULE — LOUISIANA ENGINEERING v1.0
═══════════════════════════════════════════════════════════════════

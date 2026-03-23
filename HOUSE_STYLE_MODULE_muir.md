# ═══════════════════════════════════════════════════════════════════
# HOUSE STYLE MODULE — MARYBETH E. MUIR, CCR, RPR
# ═══════════════════════════════════════════════════════════════════
# Source:    030626yellowrock-FINAL to scott (1).pdf
#            John G. Cox deposition, Yellow Rock v. Westlake, 3/6/2026
#            Same reporter, same case as Easley deposition (PROD-RUN-001)
# Extracted: 2026-03-23
# Author:    Scott + Claude
# Version:   1.0
#
# PURPOSE: These rules override generic engine defaults wherever Muir's
# actual finalized transcripts differ from engine behavior.
# Load AFTER core engine and STATE_MODULE. These are the ground truth.
# ═══════════════════════════════════════════════════════════════════


===========================================================
1. LINE NUMBERS
===========================================================
  Every page has line numbers 1 through 25 in the left margin.
  Format:  [linenum] [content]
  Where linenum is right-justified in a 2-character field.

  Example:
   1 STATE OF LOUISIANA
   2 PARISH OF CALCASIEU
  ...
  25

  NOTE: Engine must output line numbers. Without them the transcript
  does not match Marybeth's required format.


===========================================================
2. LETTER-SPACED SECTION HEADERS
===========================================================
  All major section headers use letter-spacing (one space between
  each letter):

    I N D E X
    E X H I B I T S
    A P P E A R A N C E S:        ← colon after S on counsel pages
    A P P E A R A N C E S         ← no colon on "ALSO PRESENT" page
    S T I P U L A T I O N
    C E R T I F I C A T E         ← used for BOTH reporter cert and witness cert

  DO NOT use plain headers. DO NOT use underlines. Letter-spaced only.


===========================================================
3. COVER PAGE (CAPTION) FORMAT
===========================================================
  Asterisk divider: * * * * * * * * * * * * * * * * * * * * * * * *
  (Alternating asterisk-space, full line width.)

  Layout (centered within line-number field):

    [line 1]  STATE OF LOUISIANA
    [line 2]  PARISH OF [PARISH NAME]
    [line 3]  [#]TH JUDICIAL DISTRICT
    [line 4]  * * * * * * * * * * * * * * * * * * * * * * * *
    [line 5]  [PLAINTIFF], et    Docket No.
              al,                [DOCKET NUMBER]
    [line 6]  Plaintiffs,        Division "[LETTER]"
    [line 7]  v.
              [DEFENDANT] f/k/a
    [line 8]  [PRIOR NAME] et al.,
              Defendants.
    [line 9]  (blank)
    [line 10] * * * * * * * * * * * * * * * * * * * * * * * *
    [line 11] (blank)
    [line 12] VIDEOTAPED DEPOSITION
              OF
    [line 13] [WITNESS FULL NAME]
    [line 14] taken on
    [line 15] [Weekday], [Month] [#], [Year]
              commencing at [time]
    [line 16] at
    [line 17] the offices of
              [FIRM NAME]
    [line 18] [STREET ADDRESS]
              Suite [#]
    [line 19] [City], [State] [Zip]
    [line 20] Reported By: MARYBETH E. MUIR, CCR, RPR
    [line 21] * * * * * * * * * * * * * * * * * * * * * * * *


===========================================================
4. INDEX PAGE FORMAT
===========================================================
  Header: I N D E X        Page  (Page right-justified)

  Body (page references right-aligned):
    Caption                                   1
    Appearances                               4
    Stipulation                              10
    Examination
      Mr. [Lastname]                         13
    Reporter's Certificate                  180
    Witness's Certificate                   182

  Then EXHIBITS section:
  Header: E X H I B I T S  (can span page 2 and 3 if many exhibits)

  Exhibit entry format (two lines per exhibit):
    Exhibit No. [#]  [Brief Description], [Date]
      [Bates Range]                          [pg]

  Example:
    Exhibit No. 113  E-mail, 9/10/18
      YR-440894-440895                       68


===========================================================
5. APPEARANCES BLOCK FORMAT
===========================================================
  Each page header: A P P E A R A N C E S:

  Party entry format:
    FOR THE [PARTY DESIGNATION]:
      [FIRM NAME]
      [STREET ADDRESS]
      Suite [#]
      [City], [State]  [ZIP]-[ZIP4]
      [PHONE]
      [email@address.com]
      BY: [FULL NAME], ESQ.
         [SECOND NAME], ESQ.
         (etc.)

  Modifiers (flush right or inline):
    (Via Zoom)      — when attending remotely
    NOT PRESENT     — when filed appearance but not attending

  LAST APPEARANCES PAGE — "ALSO PRESENT":
    Header: A P P E A R A N C E S   (no colon)
    ALSO PRESENT:
      [Name]
      [Name]
      [Role, e.g., Videographer]

    Footer block (on last appearances page only):
      Reported by: Marybeth E. Muir,
        Certified Court Reporter
        In and for the State of
        Louisiana and Registered
        Professional Reporter


===========================================================
6. STIPULATION PAGE FORMAT
===========================================================
  Header: S T I P U L A T I O N

  Standard Louisiana stip text (exact):
    It is stipulated and agreed by and between
    Counsel that the testimony of the witness, [WITNESS NAME IN CAPS],
    is hereby being taken pursuant to Notice under
    the Louisiana Code of Civil Procedure for all
    purposes permitted under law.

    The witness reserves the right to read and
    sign the deposition. The original is to be
    delivered to and retained by [ATTORNEY NAME],
    [SUFFIX], for proper filing with the Clerk of
    Court.

    All objections, except those as to the form
    of the questions and/or responsiveness of the
    answers, are reserved until the time of the trial of
    this cause.

    * * * * *
    Marybeth E. Muir, Certified Court Reporter
    in and for the State of Louisiana and Registered
    Professional Reporter, officiated in administering
    the oath to the witness.

  NOTE: CAT software timestamp (e.g., "08:31:59AM") may appear at the
  bottom of the stip page as a steno artifact. Strip it in post-processing.


===========================================================
7. WITNESS INTRODUCTION FORMAT
===========================================================
  Before examination begins, after videographer swears witness in:

    [WITNESS NAME IN CAPS],
    [Address], [City] [State] [Zip]
    [email@address.com], having been first
    duly sworn, was examined and testified as
    follows:

  NOTE: Witness intro runs continuous (address and email on same line as
  name when short; wrapped when long). The comma after the name is required.


===========================================================
8. EXAMINATION HEADER FORMAT
===========================================================
  New examination section (opening, cross, redirect, recross):

    EXAMINATION
    BY MR. [LASTNAME]:

    OR:

    CROSS-EXAMINATION
    BY MR. [LASTNAME]:

  Rules:
    - Two lines. Flush left. No centering.
    - No separator line above or below.
    - All caps for the examination type word.
    - "BY MR." / "BY MS." on second line.
    - Colon after last name.
    - The Q. immediately follows on the next line.

  RE-ATTRIBUTION WITHIN EXAMINATION (mid-page resumption):
  When questioning resumes after a colloquy, exhibit marking, or
  off-record interruption — use attribution line only (no full header):

    BY MR. [LASTNAME]:
    Q. [Question continues...]

  This is NOT a new examination section. It is a speaker re-attribution.


===========================================================
9. Q AND A FORMAT
===========================================================
  Q. [Question text]
  A. [Answer text]

  - "Q." and "A." are the only prefixes for testimony Q&A.
  - Attorneys identified only in colloqy (MR./MS./THE COURT REPORTER:/
    THE VIDEOGRAPHER:)
  - Interruptions and incomplete sentences use em dash: --
    (double hyphen, no spaces — steno convention, distinct from typeset em dash)
  - Witness response "Uh-huh." = affirmative. Preserve exactly.
  - Witness response "Huh-uh." = negative. Preserve exactly.


===========================================================
10. OBJECTION FORMAT
===========================================================
  Standard objection (own line, attorney identified):
    MR. [LASTNAME]: Objection to form.
    Go ahead.

  Multi-basis:
    MR. [LASTNAME]: Objection to form; vague.
    Go ahead.

  NOTE: "Go ahead." is on its own numbered line immediately after the
  objection line. It is spoken by the same objecting attorney giving
  the witness permission to answer despite the objection.

  STENO VARIATION: "Object to form." (drops "-ion") should be normalized
  to "Objection to form." — confirmed as steno artifact, not speaker intent.

  Preserve all other objection language verbatim (no rewording).


===========================================================
11. EXHIBIT MARKING FORMAT
===========================================================
  When an exhibit is introduced (parenthetical, two lines):

    (Whereupon, Exhibit No. [#], was
    marked for Identification.)

  Immediately after, when witness is given the exhibit:

    (Witness peruses document.)

  These are parentheticals — indented, in parentheses.
  They appear between the Q. that introduces the exhibit and the A.


===========================================================
12. E-MAIL SPELLING
===========================================================
  ALWAYS: E-mail   (capital E, hyphen)
  NEVER:  email    (lowercase, no hyphen)
  NEVER:  e-mail   (lowercase e)
  NEVER:  E_mail   (underscore — steno artifact to be cleaned before engine)

  This applies in all contexts: text body, exhibit descriptions, index entries.


===========================================================
13. COMPANY NAME: WESTLAKE CHLOR-VINYLS
===========================================================
  Correct spelling: WESTLAKE CHLOR-VINYLS CORPORATION
  (hyphen between CHLOR and VINYLS)

  Common steno errors:
    CHLOR_VINYLS   → CHLOR-VINYLS  (underscore artifact)
    CHLOROVINYLS   → CHLOR-VINYLS  (dropped hyphen)

  The engine should flag all instances of CHLOR[_\s]VINYLS for review.
  The state module compound fix list should NOT auto-correct company names.


===========================================================
14. REPORTER'S CERTIFICATE FORMAT
===========================================================
  Page header: C E R T I F I C A T E

  Opening notice (first 2-3 lines):
    Certification is valid only for a transcript
    accompanied by my original signature and
    Original required seal on this page.

  Body (verbatim statutory language):
    I, Marybeth E. Muir, Certified Court
    Reporter in and for the State of Louisiana, and
    Registered Professional Reporter, as the officer
    before whom this testimony was taken, do hereby
    certify that [WITNESS NAME IN CAPS], after having been duly
    sworn by me upon authority of R.S. 37:2554, did
    testify as hereinbefore set forth in the foregoing
    [N] pages; that this testimony was reported by me in
    the stenotype reporting method, was prepared and
    transcribed by me or under my personal direction and
    supervision, and is a true and correct transcript to
    the best of my ability and understanding; that the
    transcript has been prepared in compliance with
    transcript format guidelines required by statute or
    by rules of the board, and that I am informed about
    the complete arrangement, financial or otherwise,
    with the person or entity making arrangements for
    deposition services; that I have acted in compliance
    with the prohibition on contractual relationships,
    as defined by Louisiana Code of Civil Procedure
    Article 1434 and in rules and advisory opinions of
    the board; that I have no actual knowledge of any
    prohibited employment or contractual relationship,
    direct or indirect, between a court reporting firm
    and any party litigant in this matter nor is there
    any such relationship between myself and a party
    litigant in this matter. I am not related to
    counsel or to the parties herein, nor am I otherwise
    interested in the outcome of this matter.

  Closing:
    This [Nth] day of [Month], [Year].


    _________________________
    MARYBETH E. MUIR, CCR, RPR

  NO LICENSE NUMBER on the certificate page.
  Signature line is a blank underscore line with name below.


===========================================================
15. WITNESS'S CERTIFICATE FORMAT
===========================================================
  Page header: C E R T I F I C A T E   (same header as reporter cert)

  Body:
    I, [WITNESS NAME IN CAPS], do hereby certify that I have
    read or have had read to me the foregoing transcript
    of my testimony given on [Month] [#], [Year], and find
    same to be true and correct to the best of my
    ability and understanding with the exceptions noted
    on the amendment sheet;

    CHECK ONE BOX BELOW:
    ( ) Without Correction.
    ( ) With corrections, deletions, and/or
        additions as reflected on the errata
        sheet attached hereto.

    Dated this ___ day of ___________,
    [Year].


    _________________________
    [WITNESS NAME IN CAPS]

  Footer on witness cert page:
    Reported by: Marybeth E. Muir, CCR, RPR


===========================================================
16. ERRATA SHEET FORMAT
===========================================================
  Title: DEPOSITION ERRATA SHEET

  Repeated block (6-7 entries per page, 2 pages total):
    Page No._____Line No._____Change to:______________
    _______________________________________________
    Reason for change:________________________________

  Footer at end of second errata page:
    SIGNATURE:_______________________DATE:___________
    [WITNESS NAME IN CAPS]


===========================================================
17. DELIVERY FILE ORDER
===========================================================
  Files appear in this order in the final delivery:
    1. Caption page (p.1)
    2. Index (pp. 2-3 or more if many exhibits)
    3. Appearances (pp. 4-9 or as needed)
    4. Stipulation (p.10)
    5. Videographer on-record statement
    6. Witness sworn in (intro block)
    7. Examination (bulk of transcript)
    8. Adjournment statement
    9. Reporter's Certificate
    10. Witness's Certificate
    11. Errata Sheet (2 pages)


===========================================================
MAINTAINER NOTES
===========================================================
  VERSION:      1.0
  REPORTER:     Marybeth E. Muir, CCR, RPR
  SOURCE FILE:  030626yellowrock-FINAL to scott (1).pdf
  CASE:         Yellow Rock, LLC v. Westlake US 2 LLC et al.
  ENGINE:       MASTER_DEPOSITION_ENGINE v4.0+

  These rules reflect Marybeth's personal finalized output.
  When uncertain, the PDF is the ground truth.
  Do not override these rules from generic style sources.

  OPEN ITEMS:
    - Line number rendering: engine must implement 1-25 per page output
    - Letter-spaced headers: engine must output letter-spaced format
    - Certification template: copy verbatim statutory language from Section 14
    - E-mail fix: steno_cleanup.py compound_fixes list must use E-mail not email

═══════════════════════════════════════════════════════════════════
END OF HOUSE STYLE MODULE — MARYBETH E. MUIR v1.0
═══════════════════════════════════════════════════════════════════

# Brandl chunk_01 Defect Evidence — 2026-04-16

## Source
Evidence gathered via read-before-think protocol.
Files examined: extracted_text.txt, label_qa.py,
MASTER_DEPOSITION_ENGINE_v4.1.md, ai_engine.py,
chunk_01 baseline FINAL_FORMATTED.txt

Session type: Evidence-gathering only. No fixes applied.
Button-up note: NOT written at session close (protocol failure —
this file recovers what was lost).

---

## DEF-A — Q/A Cascade (CRITICAL)
Root cause: label_qa.py toggle flips per sentence, not per
speaker turn (lines 217-220). When speaker label encountered
(lines 173-179), toggle is not reset or advanced.

Evidence — page 12 lines 1–25 baseline output (verbatim):

  12
   1  MR. Thank you. other stipulation is one objection is good
   2  present unless somebody opts
   3  MR. Agreed.
   4  MR. Agreed.
   5  MR. I don't agree to your Reservation of Rights, but object to
   6  that. Let's move forward.
   7  MR. I agree. Are there any other stipulations? Okay. We're ready
   8  to go.
   9  
  10                            EXAMINATION
  11  BY MR. PEACOCK:
  12       Q.   Good morning.
  13          Can can you please state your name for the
  14          record? A. My name is Bradley Shea Brandl. I
  15          go by Brad Brandl. Q. My name is Trey
  16          Peacock, Trey Peacock. I represent Westlake
  17          in this matter. I'll be the lawyer
  18          questioning you today. It's nice to meet
  19          you. before have before you are here today
  20          represented by counsel you are not
  21          represented by counsel
  22  
  23       Q.   represent Okay. They are going to go over
  24            some rules with you just a moment. First,
  25            I'v

Observed: lines 12–21 show one Q. block containing three distinct
speaker turns (Q by Peacock, A by Brandl, second Q by Peacock)
plus a partial second A — all collapsed under a single Q. label.
The inline "A." and "Q." on lines 14–15 were preserved by the AI
instead of being broken into separate speaker turns. Q/A cascade
inverts attribution for the remainder of the examination.

---

## DEF-A2 — Inline Q/A Label Preservation
AI receives dense blocks with inline Q./A. labels and preserves
them instead of breaking into proper speaker turns.

Evidence — page 16 lines 1–13 baseline output (verbatim):

  16
   1            which I do not know. Amount? Okay. What was
   2            the nature of your testimony? Just
   3            operational issues -- were tank bottoms
   4            hauled, were batteries constructed, that
   5            sort of mechanism? Uhmm. Like I said,
   6            factual testimony just about Samedan, its
   7            operations, you know -- reported to whom,
   8            safety program --
   9       Q.
  10       A.   I mean, wasn't in charge of the safety
  11            program. The company implemented it; I
  12            abided. Were you on-site or near the site
  13            when the event -- the incident -- happened?

Key defect: Line 9 is an empty Q. label followed immediately by
an A. on line 10. AI blindly enforced Layer 11 alternation
checklist with no actual Q content to label.

---

## DEF-B — MR. Name Strip (Context-Dependent)
Raw steno has MR. LASTNAME:\n on standalone line followed by
speech below. Mid-examination MR. PEACOCK: preserved (page 19).
Pre-examination MR. GUILLOT: stripped to bare "MR." (page 11).
Mechanism of context-dependent strip: UNKNOWN — investigation
task for next session.

Evidence — page 11 lines 17–25 baseline output (GUILLOT STRIPPED, verbatim):

  17  MR. This this is Darren Guillot on behalf of Starr Indemnity &
  18  Liability Company reserve rights including limited to, the right
  19  re-depose this witness if and when we've opportunity conduct
  20  meaningful discovery have benefit of meaningful discovery We'd
  21  also like to add two stipulations if it's agreeable the first
  22  objections reserved except for the form of the question the
  23  responsiveness of an answer are there any objections that
  24  stipulation
  25  MR. Agreed.

Key defect: Attorney last name stripped. Raw steno had
"MR. GUILLOT:" on standalone line followed by speech. Output
shows bare "MR." with name removed. Occurs in pre-examination
stipulation block.

Evidence — page 19 lines 15–21 baseline output (PEACOCK PRESERVED, verbatim):

  15            graduate from high school? when did you
  16            graduate from high school
  17       A.   1988.
  18       Q.   Where did you go to college? college
  19       A.   Texas A&M.
  20                MR. PEACOCK: We should go ahead and
  21                note -- we have marked Exhibit No. No.

Key defect: Contrast with page 11 — MR. PEACOCK: preserved
mid-examination. Pattern suggests context-dependent strip
(pre-exam vs mid-exam). Mechanism UNKNOWN — investigation task
for design phase.

---

## DEF-E — Colloquy Intrusion (PARKED)
Line 506 MR. MADIGAN appears mid-examination without surrounding
blank lines. Scoped for future session.

Status: PARKED — not blocking Brandl delivery. Log and revisit.

---

## Prompt Contradiction (ROOT CAUSE OF CASCADE UNPREDICTABILITY)
Three conflicting instructions in AI prompt:
  - Layer 1A line 391: "Do NOT add Q/A labels"
  - Layer 11 lines 829-830: "Enforce Q/A alternation"
  - API_MODE_OVERRIDE anchor: "Every line must begin with Q. or A."

These three instructions are in direct conflict. The AI's
behavior on any given chunk is unpredictable because all three
fire. Which one wins depends on chunk content and context window
state. This is the root cause of cascade unpredictability — not
a formatting bug, a specification bug.

---

## Next Session
Opus design spec for coordinated 3-file fix:
  - label_qa.py (remove Q/A assignment, keep structure detection)
  - MASTER_DEPOSITION_ENGINE_v4.1.md (resolve contradiction,
    make AI sole Q/A authority)
  - ai_engine.py qa_anchor (rewrite or remove)

Design spec must be written before any code is touched.
All three files change together or none change.

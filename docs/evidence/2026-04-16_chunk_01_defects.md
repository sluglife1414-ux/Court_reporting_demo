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

Evidence — page 12 lines 12-21 baseline output:
  [EVIDENCE NOT PRESERVED — session ended without commit.
   Scott's Opus chat is the only record. Recover before next run.]

Observed symptom: page 12 has three speaker turns collapsed
into one Q block. Q/A cascade inverts attribution for remainder
of examination.

---

## DEF-A2 — Inline Q/A Label Preservation
AI receives dense blocks with inline Q./A. labels and preserves
them instead of breaking into proper speaker turns.

Evidence — page 16 line 9 empty Q. label:
  [EVIDENCE NOT PRESERVED — recover from Opus chat.]

Observed symptom: empty Q. label with no content text. Formatter
emits the label but AI did not supply a question body.

---

## DEF-B — MR. Name Strip (Context-Dependent)
Raw steno has MR. LASTNAME:\n on standalone line followed by
speech below. Mid-examination MR. PEACOCK: preserved (page 19).
Pre-examination MR. GUILLOT: stripped to bare "MR." (page 11).
Mechanism of context-dependent strip: UNKNOWN — investigation
task for next session.

Evidence — page 11 (MR. GUILLOT stripped) and page 19
(MR. PEACOCK preserved):
  [EVIDENCE NOT PRESERVED — recover from Opus chat.]

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

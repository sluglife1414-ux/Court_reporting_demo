# Session Log — 2026-04-17 Part 3
## SPEC-2026-04-17-chunk01-3file: Full Brandl Run + chunk_02 DEF-015 Repro

**Date:** April 17, 2026
**Branch:** `claude/goofy-hodgkin`
**Session type:** Validation — full Brandl tip-to-tail + DEF-015 repro isolation

---

## Full Brandl Run Results

**Job:** `muir_mb_001_20260415_brandl_v6/work`
**Input:** SGNGL extraction (032626YELLOWROCK-FINAL.sgngl)
**Engine:** v4.2 (MASTER_DEPOSITION_ENGINE_v4.2.md, ai_engine.py qa_anchor rewrite)
**AI model:** claude-sonnet-4-6, 70 chunks, 279,191 chars
**Output:** 305 pages, 418,861 chars

**Acceptance test result: FAIL — DEF-015 (19 hits)**

All other checks PASS:
- DEF-011, DEF-004a/b, DEF-012a/b, DEF-013a/b, DEF-005a/b, DEF-009a/b: PASS
- DEF-014: PASS (283 labeled lines)
- DEF-016: PASS (211 MR. LASTNAME labels)
- DEF-017: PASS (2 EXAMINATION headers)
- DEF-018: PASS (42 BY MR. attributions)
- DEF-004c: INFO (288 bare steno [ artifacts)

**19 DEF-015 hit locations (FINAL_FORMATTED.txt line numbers):**

```
Line  979: A.   That 's the same thing. Q. Okay. So I
Line  983:      A. That. What does that involve? A. There
Line 1423:      Samedan? A. No. Q. Okay. Again, just
Line 1430: A.   Greenspoint. Q. Okay. Did your office
Line 1463: Q.   In charge of wells? A. Pardon? That -- I
Line 1478:      correct? A. Correct. Q. For example, a
Line 1799: A.   Yes. Q. Okay. The way I look at it would   ← page 64 top
Line 1870: Q.   Okay. Q. Used the $50,000 number that you
Line 1945: Q.   Okay, fair enough. Okay. Q. Did you leave
Line 1949:      disrespectful. A. No, it's not negative. Q.
Line 1964:      A. Year-and-a-half, till 2006. Q. Okay.
Line 2679: Q.   That's fair enough. A. Literally, I can't
Line 2696: A.   Yes. Q. Yellow Rock — under what you came
Line 2727: A.   Uh-huh. Q. Describe their period of
Line 2749:      That sounds fair. Q. Understood. A. I see
Line 2762: A.   Yes, sir. Thank you. Q.  Is it just -- is
Line 2773: A.   Yes, sir. Q.  You're one of the people who
Line 2791: Q.   Okay. A.  Uhmm, just going -- basically,
Line 2822: A.   Correct. Q.  Under "Geoscience," did you   ← page 101/102 seam
```

Notable cluster: lines 2679–2822 (~150-line window) likely a chunk seam where AI lost toggle context.

---

## Root Cause

**SPEC §5.2 DENSE INLINE BLOCKS rule is not consistently applied across all AI chunks.**

The rule reads:
> "When you encounter dense inline content (e.g., 'Q. text A. text Q. text' on a single line or in a single block), break it into proper speaker turns — one utterance per turn."

The AI breaks dense blocks correctly in some chunks and fails in others. The failure pattern suggests the instruction is present in the system prompt but not reliably followed when:
- The dense block appears mid-chunk where Q/A context is ambiguous
- Chunk boundary creates a toggle re-anchor that conflicts with the preservation instruction

Per SPEC §5.2 (confirmed at review): line 1463 (`Q. In charge of wells? A. Pardon?`) is a confirmed bug — not correct verbatim behavior.

---

## chunk_02 Reproduction Test Case

**Job:** `muir_mb_001_20260416_brandl_chunk_02/work`
**Input:** extracted_text.txt (lines 1–1200 of v6 source, pre-built by build_chunks.py Apr 16)
**AI:** 18 chunks, 96,104 chars, ~35 min
**Output:** 112 pages

**Acceptance test result: FAIL — DEF-015 (4 hits)**

```
A. That's the same thing. Q. O         ← matches full-run line 979
Q.   It's more — closer to 50? Q. O
Q.   Did those involve a geoscientist? Q.  W
(1 more)
```

**Lines 979/983 from the full run are confirmed reproduced in chunk_02.** This is the iteration test case going forward. Runtime ~35 min vs ~90 min for full Brandl — 2.5x faster iteration loop.

---

## Pre-Existing Issues Flagged (Not DEF-015)

**JSON parse failures:** Chunks 5, 12, 16 (of 18) failed JSON parsing after 2 retries — kept as-is, +0 corrections. Failure rate ~17%. Not related to DEF-015 (the DEF-015 hits fall in chunks that completed successfully). Requires separate investigation.

**Full-run JSON failures also observed** during specialist verify pass (InterpolationAgent batch 11, GrammarAgent batch 1, SpeakerAgent batch 1, ConsistencyAgent batch 1) — connection errors, not parse failures. Separate issue.

---

## Page Count Delta

**305 pages (this run) vs 357 target.**

52-page gap. Not related to DEF-015. Likely cause: this run used SGNGL extraction which may produce denser/cleaner output than the RTF extraction path used in earlier runs. Requires separate investigation — compare `extracted_text.txt` line counts across extraction methods. Do not block DEF-015 work on this.

---

## Next Session

1. Open chunk_02 FINAL_FORMATTED.txt, read all 4 DEF-015 hits in context
2. Compare the AI's corrected_text.txt at those locations — determine whether the dense block arrived at the formatter already inline (AI failed to break it) or was collapsed by format_final.py
3. Propose §5.2 prompt refinement based on findings
4. Re-run chunk_02, verify 0 DEF-015 hits
5. If clean on chunk_02, run chunk_07 (full testimony) to confirm fix holds across chunk boundaries

---

END OF SESSION LOG

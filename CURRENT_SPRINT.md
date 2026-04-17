# ═══════════════════════════════════════════════════════════════════
# CURRENT_SPRINT.md — INSTRUCTIONS FOR CODE CLAUDES
# Deposition Transformation Engine
# ═══════════════════════════════════════════════════════════════════
# Written by: Project Lead Claude
# For:        Code Claudes working in Claude Code
# Updated:    2026-04-17
# ═══════════════════════════════════════════════════════════════════
# BEFORE YOU TOUCH ANYTHING:
#   1. Read CLAUDE.md fully — technical ground truth.
#   2. Read this file fully — your exact tasks.
#   3. Do not invent scope. Do exactly what is written here.
#   4. When done with a task, say so clearly so Scott can log it.
# ═══════════════════════════════════════════════════════════════════

## SESSION 2026-04-17 — Sync & Evidence Recovery COMPLETE

Commits this session:
  4e9a825 — Evidence file skeleton preserved
  485b98b — Evidence file completed (page 16, 11, 19 excerpts)
  3bb834e — Sprint docs rebuilt (stale since 2026-03-30)
  50a810a — Worktree rebased onto master (3 Apr 16 commits pulled)
  2b03ad5 — D-21 filed across DEFECT_LOG + sprint + board

Protocol gaps caught and fixed:
  - April 16 evidence had no button-up note — evidence lost
    until today's ramp-up recovered it from chat history
  - Acceptance test gap (D-21) would have green-lit Brandl v5
    with cascade defects
  - Naming collision (DEF-014 vs existing D-14) caught before
    commit
  - Truncation between chat windows required smaller message
    blocks for full evidence transfer

Next session: Opus writes coordinated 3-file design spec in
fresh context. Scott will bootstrap new Opus session with
prepared message. Sonnet builds from spec once Scott approves.

Housekeeping for Scott (non-urgent):
  - 3 April 16 commits (daee554, 2fbf71f, c7529f8) exist on
    local master only — never pushed to origin. Push when
    convenient.

---

## SPRINT GOAL

One track: **Brandl Q/A defect fix — design spec first, then coordinated 3-file fix.**

The April 13-15 defect sprint closed DEF-001 through DEF-013 and passed the
acceptance test. But the acceptance test is blind to Q/A structural defects.
April 16 evidence session found three live defects (DEF-A, DEF-A2, DEF-B)
rooted in a prompt contradiction across three files. Fix requires a design spec
before any code is touched. All three files change together or none change.

---

## WHERE THINGS STAND (read before starting)

**Active engine:** `C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\`
**GitHub:** https://github.com/sluglife1414-ux/Court_reporting_demo (PRIVATE, branch: court_reporting)
**Last full run:** Brandl v5 — 354 pages, acceptance test PASS (2026-04-15)
**Acceptance test caveat:** Passes on artifact/reasoning bleed only. BLIND to Q/A structural defects.

**The pipeline (run in order via run_pipeline.py):**
```
extract_rtf.py      → raw_text.txt
steno_cleanup.py    → cleaned_text.txt
label_qa.py         → labeled_text.txt  (pre-AI Q/A structure labeler — added 2026-04-15)
ai_engine.py        → corrected_text.txt  (Claude API, ~56 min, checkpoints every chunk)
extract_config.py   → depo_config.json
format_final.py     → FINAL_FORMATTED.txt
build_pdf.py        → FINAL.pdf
build_transcript.py → FINAL_TRANSCRIPT.txt
build_condensed.py  → CONDENSED.txt
build_deliverables.py → 5 analysis docs
```

**One command runs it all:**
```
python run_pipeline.py              # full run (~60 min)
python run_pipeline.py --skip-ai   # post-AI only (~2 min, use when corrected_text.txt exists)
python run_pipeline.py --from STEP # resume from any step
python run_pipeline.py --dry-run   # preview without running
```

**⚠️ CRITICAL:** NEVER run without --skip-ai if corrected_text.txt already exists and is >50KB.
That overwrites 56 minutes of API work.

**Style module rule:** Each CR has their own HOUSE_STYLE_MODULE. NEVER cross-load.
muir.md = MB (LA civil). dalotto.md = AD (NY WC). They are different CRs in different states.

---

## ⚠️ OPEN DEFECTS THAT AFFECT YOUR WORK

Do not resolve these without Scott's input — flag and wait:

- **DEF-A (Q/A Cascade)** — CRITICAL. label_qa.py toggle flips per sentence, not per
  speaker turn. Three speaker turns collapse into one Q block. Inverts Q/A for remainder
  of examination. Evidence: `/docs/evidence/2026-04-16_chunk_01_defects.md`

- **DEF-A2 (Empty Q label)** — AI enforces alternation with no content to label.
  Empty Q. label on page 16 line 9. Same evidence file.

- **DEF-B (MR. name strip — context-dependent)** — Pre-examination speaker labels
  stripped to bare "MR." Mid-examination preserved. Mechanism unknown.
  Same evidence file.

- **Prompt contradiction (root cause of DEF-A/A2 unpredictability):**
  Three conflicting instructions in MASTER_DEPOSITION_ENGINE_v4.1.md:
  Layer 1A line 391 ("Do NOT add Q/A labels") vs Layer 11 lines 829-830
  ("Enforce Q/A alternation") vs API_MODE_OVERRIDE anchor ("Every line must
  begin with Q. or A."). These conflict. Fixing any one file without the others
  makes it worse.

- **D-21 (Acceptance test blind to Q/A structure)** — Filed. Current
  test only checks for reasoning bleed. No structural integrity checks exist.

---

## ACTIVE TASKS

### TASK 1 — Sync worktree to main (SYNC STEP 3)
**Status:** READY
Main repo has 3 commits not in this worktree:
  - daee554: fix(ai_engine): SSL/KeyboardInterrupt retry
  - 2fbf71f: fix(run_pipeline): os.path.exists
  - c7529f8: fix(run_pipeline): skip input check when --from steno

Steps:
1. Pull those 3 commits into this worktree
2. Report merge result — no conflicts expected (pipeline fixes only)

---

### TASK 2 — Review April 16 commits for design conflicts (SYNC STEP 4)
**Status:** READY (after TASK 1)
Read the diff for each of the 3 commits above — especially any changes to
ai_engine.py. Need to understand what changed before designing the qa_anchor
rewrite. Report findings. Do NOT make judgment calls — report only.

---

### TASK 3 — File D-21 in DEFECT_LOG.md (SYNC STEP 5)
**Status:** READY
Add new row to DEFECT_LOG.md:
  ID: D-21
  Date: 2026-04-17
  Status: OPEN
  Symptom: Acceptance test passes on output with inverted Q/A cascade
  Root Cause: acceptance_test.py only checks for AI reasoning bleed.
    No structural Q/A integrity checks exist.
  Fix: Design structural Q/A checks for acceptance_test.py — minimum:
    (1) empty Q. label check, (2) Q/A ratio sanity check, (3) cascade
    detection (A immediately follows Q with no content between)
  Commit: (pending)

---

### TASK 4 — Opus design spec (NEXT SESSION — do not start without Scott)
**Status:** WAITING ON SCOTT
**Prerequisite:** SYNC STEPs 3 and 4 must be complete. Opus needs Apr 16 commit diffs (especially ai_engine.py changes) before finalizing spec.
Opus will design the coordinated 3-file fix:
  - label_qa.py: remove Q/A assignment, keep structure detection only
  - MASTER_DEPOSITION_ENGINE_v4.1.md: resolve the three-way contradiction,
    make AI the sole Q/A authority
  - ai_engine.py qa_anchor: rewrite or remove

Do not touch these files until the design spec is written and Scott approves.
All three change together or none change.

---

## DONE THIS SPRINT

| Task | Completed | Notes |
|------|-----------|-------|
| DEF-001 through DEF-013 closed | 2026-04-13–15 | See DEFECT_LOG.md |
| label_qa.py added to pipeline | 2026-04-15 | Pre-AI Q/A structure labeler |
| acceptance_test.py built | 2026-04-15 | Passes Brandl v5 — caveat: blind to Q/A structure |
| Brandl v5 acceptance test PASS | 2026-04-15 | 354 pages, zero bleed |
| April 16 evidence preserved | 2026-04-17 | docs/evidence/2026-04-16_chunk_01_defects.md |
| CURRENT_SPRINT.md updated | 2026-04-17 | This file — replacing stale 2026-03-30 version |
| PROJECT_BOARD.md updated | 2026-04-17 | Replacing stale 2026-03-30 version |

---

## HOW TO COMMUNICATE BACK

**If task complete:**
> ✅ TASK [#] DONE — [one line summary]
> Files changed: [list]
> Ready for: [what comes next]

**If blocked:**
> 🔴 BLOCKED ON TASK [#] — [what's blocking you]
> Need from Scott: [specific question or decision]

**If you find something unexpected:**
> ⚠️ FLAG — [what you found, where, why it matters]
> Recommendation: [what you think should happen]

Do not silently fix things outside your task scope. Flag and wait.
Over-communicate. Scott wants to know everything.

---
*Written by: Project Lead Claude*
*Last updated: 2026-04-17*
*Next update: after SYNC STEPs 3-5 complete and design spec session scheduled*

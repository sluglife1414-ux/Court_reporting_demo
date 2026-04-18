# Session Log — 2026-04-17 Part 2
## SPEC-2026-04-17-chunk01-3file: Brandl chunk_01 Validation Run

**Date:** April 17, 2026
**Branch:** `claude/goofy-hodgkin`
**Session type:** Post-build validation — first end-to-end test of v4.2 fixes

---

## What Happened This Session

### Build recap (Part 1 — same branch, prior context)
All 4 build steps landed before this session began:
- `3030a97` — step 1/4: prompt v4.2 (4-way contradiction resolved)
- `d79bfad` — step 2/4: ai_engine qa_anchor rewrite
- `deca774` — step 3/4: qa_structure_detector rename + scope cut
- `f61ded0` — step 4/4: acceptance_test DEF-014 through DEF-018 (D-21 closure)

### This session: Brandl chunk_01 validation run

Ran the full pipeline (steno → qa_structure_detector → AI → verify → format → build)
against the Brandl chunk_01 test fixture using the goofy-hodgkin worktree code.

**Fixture:** `muir_mb_001_20260416_brandl_chunk_01` — lines 1-600 of Brandl extracted_text
+ reporter cert tail. Per build_chunks.py: "hits all 18 known defects."

**Runtime:** ~10 min total (8.5 min AI pass, 7 internal processing chunks)

**Output:** `FINAL_DELIVERY/Brandl_YellowRock_FINAL_FORMATTED.txt` — 46 pages, 57,867 bytes

---

## Acceptance Test — 17/17 PASS

All checks clean on v4.2 output:

```
DEF-011  PASS   0 / 0    *REPORTER CHECK HERE* in output
DEF-004a PASS   0 / 0    Empty [] brackets
DEF-004b PASS   0 / 0    [|] bracket variants
DEF-004c INFO   3 / —    Bare steno [ artifacts (informational)
DEF-012a PASS   0 / 0    Unmatched ]] closing tag
DEF-012b PASS   0 / 0    "Verify audio" in output
DEF-013a PASS   0 / 0    "steno artifact" in output
DEF-013b PASS   0 / 0    "token N" numbering in output
DEF-005a PASS   0 / 0    Reasoning phrases in output
DEF-005b PASS   0 / 0    "high/low confidence" in output
DEF-009a PASS   0 / 0    Double Q label
DEF-009b PASS   0 / 0    Double A label
DEF-014  PASS   5 / >=1  Q./A. labeled testimony lines present
DEF-015  PASS   0 / 0    Dense inline Q/A blocks
DEF-016  PASS   2 / >=1  MR. LASTNAME: speaker labels
DEF-017  PASS   2 / >=1  EXAMINATION section headers
DEF-018  PASS   1 / >=1  BY MR. attribution

RESULT: PASS — all checks clean
```

---

## Defect-Specific Findings

### DEF-A (Q/A toggle per speaker turn) — FIXED
AI now assigns Q./A. labels based on semantic context. The dense run-on steno
(`"can you please state your name for the record name Bradley Shay Brandl I go Brad
Brandl name Trey peacockTrey Peacock I represent..."`) arrived at the AI unlabeled
(qa_structure_detector correctly passed it through). The AI assigned Q./A. correctly.
Verification agents flagged the reconstruction at line~469 and line~484 as needing
reporter review — which is correct behavior (those are genuinely hard steno fragments).

### DEF-A2 (dense inline blocks not broken) — FIXED (structurally)
The qa_structure_detector scope cut means no pre-labels reach the AI. The old
defective toggle that injected Q./A. mid-block is gone. DEF-015 acceptance check
confirmed 0 inline Q/A blocks in output. The structural fix worked.

### DEF-B (MR. LASTNAME stripping) — NOT FIXED, as predicted by spec §9
Input: 9 MR. LASTNAME: labels (GUILLOT×5, MADIGAN×1, PEACOCK×2, PITRE×1)
Output: 2 MR. LASTNAME: labels (MADIGAN×1, PEACOCK×1)
GUILLOT (5 occurrences) and PITRE (1 occurrence) were stripped.
Root cause is downstream — suspected format_final.py colloquy normalization.
Prompt-level fixes were never intended to address this. Separate sprint required.

### Internal processing chunks 5 and 6 — parse failures
Chunks 5 and 6 (of 7 internal ~3000-char AI processing chunks) had JSON parse
failures. These are the steno-dense stipulation blocks (MR. GUILLOT, MR. MADIGAN
colloquy pages) — the hardest content in the fixture. Chunk 5 failed after retries
(0 corrections applied, content kept verbatim). Chunk 6 had empty ops list (fallback).
Not a v4.2 regression — pre-existing reliability issue on highly fragmented steno.

### Specialist flags (highest severity)
Two items flagged by all 6 specialist agents — needs MB review:
- `line~590`: `'GUILLOT:'` → `'This'` — speaker label misidentified as sentence content
- `line~484`: fragmented steno reconstruction — "it's nice to meet have before have
  before you are here today" reconstructed as two questions; speculative

13 items total tagged [REVIEW] in output for reporter verification.

---

## Terminology Clarification (from Scott)

**The 7 Brandl "chunks"** (`brandl_chunk_01` through `brandl_chunk_07`) are a
**test fixture for human-scale review** — not a production concept. Built by
`build_chunks.py` to create progressively larger slices of the full depo for
iterative testing.

**The ~7 internal processing chunks** in this run (visible in the pipeline output
as `[1/7]`, `[2/7]`, etc.) are how the engine normally operates — the AI processes
`cleaned_text.txt` in ~3000-char token-size chunks. These are always present for any
depo regardless of size.

**"Chunks 5 and 6 parse failures"** in the run log refer to internal processing
chunks (token-driven), NOT transcript chunks (test fixture slices).

---

## Key File Paths

| What | Path |
|---|---|
| Brandl chunk jobs | `C:\depo_transformation\data\cr_profiles\muir_mb_001\brandl_chunks\jobs\` |
| Engine deployment (pre-fix) | `C:\depo_transformation\engine\mb_demo_engine_v4` |
| Worktree (v4.2, active) | `C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\.claude\worktrees\goofy-hodgkin` |
| .env | Copied from deployment to worktree. Gitignored (`.gitignore` line 61). Safe. |

---

## How to Run from CMD (next time)

```cmd
cd C:\depo_transformation\data\cr_profiles\muir_mb_001\brandl_chunks\jobs\muir_mb_001_20260416_brandl_chunk_01\work

python C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\.claude\worktrees\goofy-hodgkin\steno_cleanup.py

python C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\.claude\worktrees\goofy-hodgkin\qa_structure_detector.py

python C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\.claude\worktrees\goofy-hodgkin\run_pipeline.py --from ai
```

Note: `--from steno` won't work directly (triggers RTF/sgngl detection, chunk jobs
have no RTF). Run steno and qa_structure standalone first, then `--from ai`.

---

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| .env delivery | Option 1 — copy to worktree | Gitignored, isolated, matches deployment behavior |
| Pipeline execution | Worktree path approach | Branches exist for isolated testing; no hand-copying to deployment |
| DEF-016/017/018 check type | Option 3 — output-only structural min | Total-strip is the production failure; partial-strip = regression harness scope |
| Min check runner | Option B — `('min', N)` tuple target | ~13 lines added to runner; clean; gives real pass/fail |

---

## What's Next

1. **Full Brandl tip-to-tail run** — all ~350 pages (chunk_07, lines 1-4100 + cert)
   through the full v4.2 pipeline. The real production-scale validation. Start fresh
   Claude Code session for this.

2. **DEF-B investigation sprint** — separate session targeting `format_final.py`
   colloquy/speaker-label normalization. Input had 9 MR. LASTNAME: labels; output
   had 2. Root cause unknown.

3. **MB review** — unavailable until weekend. Acceptance test passed but human
   review of the specialist flags (especially line~590 and line~484) needed before
   delivery sign-off.

4. **Easley full run** — queued for tomorrow. Different depo, same v4.2 engine.

5. **Merge goofy-hodgkin → court_reporting** — after Brandl and Easley both validate
   cleanly and MB review is complete.

---

## Commit Stack (end of session)

```
f61ded0 SPEC-2026-04-17-chunk01-3file: step 4/4 — acceptance_test D-21 closure
deca774 SPEC-2026-04-17-chunk01-3file: step 3/4 — qa_structure_detector rename + scope cut
d79bfad SPEC-2026-04-17-chunk01-3file: step 2/4 — ai_engine qa_anchor rewrite
3030a97 SPEC-2026-04-17-chunk01-3file: step 1/4 — prompt v4.2
4e3d9c1 SPEC-2026-04-17-chunk01-3file: add MyReporterX mindset addendum v1
b6a208e SPEC-2026-04-17-chunk01-3file: add spec v1.1 to worktree
4004b3a SPEC-2026-04-17-chunk01-3file: add coder mindset to worktree
```

Nothing pushed. All commits local to `claude/goofy-hodgkin`.

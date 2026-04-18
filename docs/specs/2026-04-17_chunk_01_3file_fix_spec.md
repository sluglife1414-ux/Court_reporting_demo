# Design Spec v1.1: Coordinated Fix for chunk_01 Q/A Cascade Defects

**Spec ID:** SPEC-2026-04-17-chunk01-3file
**Version:** 1.1 (supersedes v1.0)
**Author:** Claude Chat (Opus) — architect
**Builder:** Claude Code (Sonnet)
**Approver:** Scott
**Status:** APPROVED FOR BUILD — all §10 open items signed off
**Evidence source:** /docs/evidence/2026-04-16_chunk_01_defects.md
**Recon source:** Sonnet recon report, 2026-04-17
**Related blocker:** D-21 (acceptance test blind to Q/A structure)

---

## Changelog: v1.0 → v1.1

v1.1 incorporates Sonnet's recon findings:

1. Added 4th contradiction site — MASTER_DEPOSITION_ENGINE_v4.1.md line 592 (ROUGH_DRAFT MODE LOAD) must be patched alongside lines 391, 829-830, and the ai_engine.py anchor
2. Added first-chunk blind spot mitigation — chunk 1 has qa_anchor=None, receives zero Q/A guidance under v1.0 proposal. v1.1 moves preservation instruction into system prompt so it applies to all chunks
3. Added Layer 11 self-audit carve-out — strict alternation checks (lines 829-830) must explicitly exempt pre-labeled pipeline input, or self-audit will silently undo the preservation fix
4. Rescoped DEF-B investigation — Sonnet confirmed the MR. LASTNAME stripping bug is NOT in label_qa.py or ai_engine.py. Investigation moves to apply_ops.py, format_final.py, validate_ops.py
5. File rename — label_qa.py → qa_structure_detector.py (scope has changed completely; name must reflect new responsibility)
6. Added Step 0: Branch verification — avoid branch-name drift between sessions
7. Added silent-failure check gate — before declaring any fix complete, verify no downstream layer can undo it

---

## 1. Defects Addressed

| ID | Summary | File(s) primarily responsible |
|----|---------|-------------------------------|
| DEF-A | label_qa.py Q/A toggle flips per sentence instead of per speaker turn | qa_structure_detector.py (renamed from label_qa.py) |
| DEF-A2 | AI preserves inline Q/A labels instead of breaking dense blocks into proper speaker turns | MASTER_DEPOSITION_ENGINE_v4.1.md, ai_engine.py |
| DEF-B | MR. LASTNAME label stripped pre-examination, preserved mid-examination | Investigation — apply_ops.py, format_final.py, validate_ops.py (confirmed not in label_qa.py or ai_engine.py per Sonnet recon) |
| D-21 | acceptance_test.py does not check Q/A structural integrity | acceptance_test.py |

**Root cause being resolved:** FOUR-way prompt contradiction (not three-way as in v1.0):

1. MASTER_DEPOSITION_ENGINE_v4.1.md Layer 1A line 391: "✗ Adding Q./A. labels where none existed in steno"
2. MASTER_DEPOSITION_ENGINE_v4.1.md ROUGH_DRAFT MODE line 592: "LOAD: Q./A. format and speaker labels (universal)"
3. MASTER_DEPOSITION_ENGINE_v4.1.md Layer 11 lines 829-830: strict alternation self-audit
4. ai_engine.py qa_anchor lines 619-620: "Every line of testimony must begin with Q. or A."

Fix establishes the AI as sole Q/A labeling authority, with qa_structure_detector.py (renamed) demoted to structure-detection-only.

---

## 2. Files Touched & Prime Directive Check

Per CODER_MINDSET_v1.md — before any change, ask: could this reduce transcript accuracy or credibility?

### 2.1 label_qa.py → qa_structure_detector.py (RENAME + SCOPE REDUCTION)
- Change type: Rename + remove Q/A assignment logic + retain structural detection.
- Prime Directive check: PASS — current Q/A assignment is DEFECTIVE. Removing broken logic and transferring responsibility to AI REDUCES risk. Rename prevents future confusion about file's role.
- Residual risk: AI hallucination of speaker turns. Mitigation: post-AI sanity check in renamed file (§3.2).
- Rename blast radius: Every import of label_qa must be updated. Sonnet verifies full grep before commit.

### 2.2 MASTER_DEPOSITION_ENGINE_v4.1.md → v4.2
- Change type: Prompt rewrite — resolve 4-way contradiction, add speaker-label preservation rule, add Layer 11 carve-out.
- Prime Directive check: PASS — contradictions themselves are the accuracy risk. Unified instructions REDUCE cascade unpredictability.
- Residual risk: Prompt regressions on non-Q/A behaviors. Mitigation: diff review against v4.1, scoped changes only, LA_TestHarness regression run.
- Rename blast radius: File rename v4.1.md → v4.2.md requires updating every reference in ai_engine.py, run_pipeline.py, and any other loader. Sonnet verifies full grep before commit.

### 2.3 ai_engine.py qa_anchor (lines 613-623)
- Change type: Rewrite lines 619-620 — from label enforcement TO preservation instruction.
- Prime Directive check: PASS — current anchor FORCES Q/A labels even on non-Q/A content. Replacing forced labeling with preservation instruction preserves accuracy across chunk boundaries.
- Residual risk: First chunk has qa_anchor=None and receives empty anchor_header. Mitigation: system-prompt-level preservation rule (§5.2) covers chunk 1.

### 2.4 acceptance_test.py (D-21 closure)
- Change type: Additive — new structural Q/A checks.
- Prime Directive check: PASS — additive test coverage only.

---

## 3. Design Decisions (Confirmed by Sonnet Recon + Scott Approval)

### 3.1 AI as sole Q/A authority — APPROVED
AI breaks dense blocks into proper speaker turns AND re-labels Q/A based on speaker context. Original Q./A. markers in source are treated as hints, not authoritative.

Sonnet caveat (accepted): The qa_anchor mechanism currently serves double duty — re-orient AI AND enforce completeness. Stripping the enforcement line leaves chunk 1 unanchored if we don't also push preservation into the system prompt. v1.1 addresses this via §5.2 system-prompt-level rule.

### 3.2 Post-AI sanity check in qa_structure_detector.py — APPROVED
After AI pass completes, the renamed detector runs a sanity check: "If AI output has more distinct speaker turns than input had speaker-label cues + 2σ tolerance, flag chunk for human review in Proof of Work."

Rationale: Prime Directive guardrail against AI hallucinating speaker turns. Does not block delivery — flags for MB's review queue.

### 3.3 File rename label_qa.py → qa_structure_detector.py — APPROVED
The file's job is completely changing. Rename prevents the new file from carrying old expectations.

### 3.4 File rename MASTER_DEPOSITION_ENGINE_v4.1.md → v4.2.md — APPROVED
Version bump reflects scope of change. All loaders must be updated in same commit.

---

## 4. Coordinated Rollout Sequence

Order matters. Deploying files out of order produces a broken intermediate state.

### Step 0 — Branch Verification (NEW in v1.1)
Before any file change, run git branch --show-current. Confirm we are on the expected working branch. Report branch name to Scott. Do NOT proceed if branch is unexpected.

### Step 1 — MASTER_DEPOSITION_ENGINE_v4.1.md → v4.2.md
- Rewrite Layer 1A (line 391), ROUGH_DRAFT MODE LOAD (line 592), Layer 11 (lines 829-830)
- Add speaker-label preservation rule
- Add Layer 11 self-audit carve-out
- Rename file to v4.2.md
- Update every loader reference (ai_engine.py, run_pipeline.py, others — Sonnet greps full repo)
- Why first: Prompt is the behavioral contract. AI and deterministic code must conform to it.

### Step 2 — ai_engine.py qa_anchor rewrite
- Implement preservation instruction, load v4.2 prompt
- Why second: AI must be ready to accept sole Q/A authority before the deterministic labeler gives up that responsibility.

### Step 3 — label_qa.py → qa_structure_detector.py (rename + scope reduction + post-AI sanity check)
- Rename file
- Remove Q/A assignment logic
- Retain structural detection: classify(), split_sentences(), ensure_blank()
- Add sanity_check_speaker_turns() function (post-AI)
- Update every import across the codebase (Sonnet greps full repo)
- Why third: Completes the authority transfer.

### Step 4 — acceptance_test.py structural checks
- Add 5 new structural check tuples to CHECKS list
- Why last: Tests validate the NEW contract.

Branch strategy: All four steps land as a single coordinated PR. Do not merge partial.

Commit granularity: One commit per step, with spec ID prefix:
- SPEC-2026-04-17-chunk01-3file: step 1/4 — prompt v4.2
- SPEC-2026-04-17-chunk01-3file: step 2/4 — ai_engine qa_anchor rewrite
- SPEC-2026-04-17-chunk01-3file: step 3/4 — qa_structure_detector rename + scope cut
- SPEC-2026-04-17-chunk01-3file: step 4/4 — acceptance_test D-21 closure

---

## 5. Per-File Specifications

### 5.1 label_qa.py → qa_structure_detector.py

Responsibility AFTER fix:
- Detect BY MR. [NAME] attorney identification lines
- Detect MR. [LASTNAME]: speaker labels
- Detect EXAMINATION, CROSS-EXAMINATION, REDIRECT section headers
- Emit structured metadata for AI consumption
- NEW: Post-AI sanity check — flag if AI output has more speaker turns than input had cues (+2σ tolerance)
- Does NOT assign Q. or A. labels (removed)
- Does NOT toggle per sentence (removed)

Deletion set (per Sonnet recon):

DELETE lines 121-122 (state variables):
  in_testimony   = False
  qa_toggle      = 'Q'

DELETE lines 135-139 (emit_qa_block helper):
  def emit_qa_block(text, label): ...

DELETE line 169 (toggle reset):
  qa_toggle = 'Q'

DELETE lines 186-191 (toggle advancement on existing q/a):
  if kind == 'q': ... qa_toggle = 'A'
  else: ... qa_toggle = 'Q'

DELETE lines 201-222 (entire testimony content labeling block):
  if not in_testimony: ... emit(s); continue
  sentences = split_sentences(s)
  for sent in sentences: emit_qa_block(sent, qa_toggle); toggle...

DELETE in_testimony flag at lines 160 and 168

Retained functions (per Sonnet recon — zero dependency on deleted toggle state):
- split_sentences() — lines 49-76
- classify() — lines 81-100
- ensure_blank() closure — lines 130-133

New function to add:
def sanity_check_speaker_turns(ai_output, input_cues):
    """
    Post-AI guardrail. Counts distinct speaker turns in AI output
    vs. speaker-label cues present in input. Flags chunk for human
    review if AI added speaker turns beyond +2σ tolerance.

    Returns: (passed: bool, details: dict for Proof of Work logging)

    Does NOT block delivery. Flags only.
    """

Sonnet proposes signature based on actual data structures in renamed file.

Import updates required: Every file that imports label_qa must be updated to import qa_structure_detector. Sonnet greps full repo before committing this step.

---

### 5.2 MASTER_DEPOSITION_ENGINE_v4.1.md → v4.2.md

Four-way contradiction resolution:

Patch 1 — Layer 1A line 391:
Current: "✗ Adding Q./A. labels where none existed in steno"
Replace with: "✗ Adding Q./A. labels where none existed in steno AND no pipeline pre-labeling is present"

Add directly after the existing ⚠️ preservation caveat at line 404, before the PERMITTED section:

⚠️ PIPELINE PRE-LABELED INPUT:
When your input already contains Q./A. labels (added by the pre-processing
pipeline before this AI pass), treat those labels exactly as steno-sourced labels.
PRESERVE THEM. The prohibition at line 391 applies to AI-invented labels with
no source. Pipeline-assigned labels already exist in your input — R8 (verbatim
preservation) governs them. Do NOT remove, re-order, or re-assign labels you
find in your input unless you have a phonetic/semantic source that overrides them.

⚠️ DENSE INLINE BLOCKS:
When you encounter dense inline content (e.g., "Q. text A. text Q. text" on
a single line or in a single block), break it into proper speaker turns — one
utterance per turn. Re-label Q. and A. based on speaker context. Log every
structural change (turn break, re-label) to Proof of Work.

⚠️ SPEAKER LABEL PRESERVATION (addresses DEF-B):
PRESERVE MR. [LASTNAME]: speaker labels EXACTLY as they appear in source,
regardless of position (pre-examination, mid-examination, post-examination).
Do not strip, collapse, or normalize these labels. If a label appears
malformed (e.g., MR LASTNAME without period, lowercase), flag in Proof of
Work but preserve verbatim in output.

Patch 2 — ROUGH_DRAFT MODE line 592 (NEW in v1.1):
Current: "Q./A. format and speaker labels (universal)"
Replace with: "Q./A. format and speaker labels — preserve pipeline labels when present; assign based on speaker context when absent"

Patch 3 — Layer 11 lines 829-830 (CRITICAL carve-out):
Current:
[ ] No Q. without following A. before next Q.?
[ ] No two Q. lines in a row without A. between?

Replace with:
[ ] No Q. without following A. before next Q.?
    EXCEPTION: When input arrived with pipeline-assigned labels,
    preserve them. Long questions split across sentences may produce
    legitimate consecutive Q. lines. Flag for human review, do NOT auto-correct.
[ ] No two Q. lines in a row without A. between?
    EXCEPTION: Same as above. Preservation of pipeline labels overrides
    strict alternation. Flag-don't-fix.

Version bump: v4.1.md → v4.2.md. Archive v4.1 to MASTER_COPIES/archive/.

Loader update blast radius: Sonnet greps full repo for references to MASTER_DEPOSITION_ENGINE_v4.1.md and updates every occurrence.

---

### 5.3 ai_engine.py qa_anchor (lines 613-623)

Current (lines 615-621):
anchor_header = (
    f"RE-ANCHOR: You are mid-examination. "
    f"Last labeled line in previous chunk was {qa_anchor}. "
    f"Next expected label is {next_label}. "
    f"CRITICAL: Every line of testimony must begin with Q. or A. "
    f"Do not return any unlabeled testimony lines.\n\n"
)

Replace with:
anchor_header = (
    f"RE-ANCHOR: You are mid-examination. "
    f"Last labeled line in previous chunk was {qa_anchor}. "
    f"Next expected label is {next_label}. "
    f"PRESERVE existing Q./A. labels verbatim — do not reassign or remove them. "
    f"If a testimony line arrives unlabeled, assign based on context.\n\n"
)

First-chunk blind spot (NEW in v1.1): When qa_anchor=None, anchor_header=''. Chunk 1 receives zero Q/A guidance from ai_engine.py. Mitigation: the preservation rule at §5.2 is in the SYSTEM PROMPT (MASTER_DEPOSITION_ENGINE_v4.2.md), which applies to every chunk including chunk 1. No additional ai_engine.py change needed for chunk 1 coverage.

Verification required: Sonnet confirms no other code path in ai_engine.py re-adds the "every line must begin with Q. or A." instruction after anchor_header is consumed. Recon already confirmed this is the only occurrence.

---

### 5.4 acceptance_test.py (D-21 closure)

Add 5 new structural check tuples to CHECKS list, inserted after DEF-009b, before INFO-pages:

DEF-014 — Unlabeled testimony lines:
(
    'DEF-014',
    'Unlabeled testimony lines (no Q./A. prefix in testimony section)',
    r'^(?!Q\.|A\.|BY |MR\.|MS\.|THE |EXAMINATION|\(|\*|-|$|\s{10,})\S',
    0,
)

DEF-015 — Dense inline blocks:
(
    'DEF-015',
    'Multiple Q./A. markers on a single line (dense block not broken)',
    r'(Q\..*?A\.|A\..*?Q\.).*?(Q\.|A\.)',
    0,
)

DEF-016 — MR. LASTNAME preservation:
# Requires comparison between input and output — implement as separate function
# that counts MR. [LASTNAME]: occurrences in input vs output and fails if
# output count < input count. Sonnet proposes exact implementation.

DEF-017 — Examination headers preserved:
# Requires input/output comparison — counts EXAMINATION / CROSS-EXAMINATION /
# REDIRECT occurrences and fails if output count < input count.

DEF-018 — Attorney attribution preserved:
# Requires input/output comparison — counts BY MR. [NAME] occurrences and
# fails if output count < input count.

Regression risk (per Sonnet recon): No existing checks will false-red against correct v4.2 output. DEF-009a/b (double Q/A labels) remain valid — if anything, risk goes DOWN with Q/A authority transferred to AI.

---

## 6. Silent Failure Check Gate (NEW in v1.1)

Before Sonnet declares any step complete, it must answer:

"Is there any layer downstream of this change that could undo what I just did?"

Specific checks Sonnet performs before marking Step 1 complete:
- Does Layer 11 self-audit have the carve-out? If not, it will undo Step 1's preservation.
- Does ROUGH_DRAFT MODE still mandate strict Q/A format? If yes, it will undo Step 1.

Specific checks Sonnet performs before marking Step 2 complete:
- Does system prompt (v4.2) have the preservation rule? If not, chunk 1 has no anchor.
- Does any other code path re-add "every line must begin" instruction?

Specific checks Sonnet performs before marking Step 3 complete:
- Did all imports of label_qa get updated to qa_structure_detector?
- Does any test file still expect Q/A labeling output from this module?

Specific checks Sonnet performs before marking Step 4 complete:
- Do new DEF-014 through DEF-018 checks run against correct v4.2 output without false-failing?

If any silent-failure check fails, Sonnet reports to Scott before committing.

---

## 7. Test Plan

### 7.1 Automated (post-build, before merge)
- Run acceptance_test.py (with new D-21 checks) against Brandl chunk_01.
- Run existing regression suite — no regressions permitted.
- Run v4.2 prompt against LA_TestHarness (Landry/Bayou Petroleum synthetic) — confirm 17 planted errors still caught.
- Run full pipeline on a known-clean transcript — verify no regressions on previously-working output.

### 7.2 Manual verification on chunk_01 (Scott + MB)
- Dense-block breakup: confirm originally-cited inline Q. ... A. ... Q. ... block is broken into separate speaker turns.
- Q/A toggle: scan a continuous examination section. Confirm Q. and A. alternate by speaker turn, not per sentence.
- MR. LASTNAME: preservation: spot-check 3 pre-examination instances and 3 mid-examination instances. All 6 must be present and verbatim.
- Examination headers: confirm EXAMINATION BY MR. [NAME] appears correctly for each section.
- Proof of Work: confirm new structural changes are logged.
- First chunk: verify chunk 1 output is properly labeled despite qa_anchor=None.

### 7.3 Sign-off gate
MB review required before v4.2 is declared production-ready.

---

## 8. Rollback Plan

If post-fix run fails acceptance_test.py or MB review:

Revert sequence (reverse of rollout):
1. Revert Step 4 commit (acceptance_test.py)
2. Revert Step 3 commit (qa_structure_detector.py rename + scope cut)
3. Revert Step 2 commit (ai_engine.py qa_anchor rewrite)
4. Revert Step 1 commit (prompt v4.2)

Single-command revert:
git revert <commit4> <commit3> <commit2> <commit1> --no-edit

Data preservation: All failed-run outputs stored in /docs/evidence/2026-04-17_postfix_run/ for diagnostic review.

Re-attempt policy: No re-deploy until new evidence session identifies specific failure mode.

---

## 9. DEF-B Investigation (Rescoped in v1.1)

Sonnet recon finding: MR. LASTNAME stripping is NOT in label_qa.py or ai_engine.py. Grep confirmed zero position-based conditionals or caption-referenced name-stripping logic in either file.

Rescoped investigation targets:
- apply_ops.py — most likely culprit (applies transformations to output)
- format_final.py — possible (final formatting may normalize labels)
- validate_ops.py — possible (validation may strip "invalid" labels)

Investigation steps (separate session, after v4.2 lands):
1. Grep all three files for MR\., strip, normalize, position-based conditionals, caption handling.
2. Run v4.2 (post-fix) against chunk_01 with verbose logging enabled on these three files.
3. Identify which component strips the label.
4. Propose fix.
5. File as separate spec: SPEC-2026-04-XX-DEF-B-fix.

Blocker status: Per Sonnet opinion and Scott approval — DEF-B blocks v4.2 production release. The speaker-label preservation rule in §5.2 may resolve the symptom, but the root mechanism must be understood before release. Fix may not be complete until the downstream stripper is neutralized.

---

## 10. Open Items Sign-Off Status

- §3.1 — APPROVED (Scott, 2026-04-17)
- §3.2 — APPROVED (Scott, 2026-04-17)
- §3.3 — APPROVED (Scott, 2026-04-17)
- §3.4 — APPROVED (Scott, 2026-04-17)
- §9 — APPROVED (Scott, 2026-04-17)

All open items signed off. Spec is APPROVED FOR BUILD.

---

## 11. Layer 2 Completion Status

All Sonnet recon items from v1.0 §10 are complete. No outstanding Layer 2 items.

Sonnet build tasks for each step:
- Step 1: Grep repo for all references to MASTER_DEPOSITION_ENGINE_v4.1.md. Patch prompt per §5.2. Rename file. Update all loader references. Run silent-failure checks per §6. Commit.
- Step 2: Patch ai_engine.py lines 619-620 per §5.3. Run silent-failure checks. Commit.
- Step 3: Grep repo for all imports of label_qa. Rename file. Delete toggle logic per §5.1. Add sanity_check_speaker_turns() function. Update all imports. Run silent-failure checks. Commit.
- Step 4: Add 5 new check tuples to acceptance_test.py per §5.4. Implement input/output comparison helpers for DEF-016/017/018. Run silent-failure checks. Commit.

---

END OF SPEC v1.1

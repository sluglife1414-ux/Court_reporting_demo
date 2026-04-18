# CODER MINDSET — MyReporterX Project Addendum v1
### Project-Specific Rules for the Deposition Engine

> **Read this AFTER `CODER_MINDSET_v1.md`. These rules apply to all MyReporterX work and stack on top of the master mindset. Where this file and the master conflict, this file wins — because these rules were written in blood from real failures on this project.**

---

## How to Use This File

Every rule in this addendum has a **named ID** (like `RULE-RECON-FIRST`). Scott or the architect can invoke a rule by name in any message:

> *"Apply RULE-CONTRADICTION-HUNT before you touch that file."*

When you see a RULE-XXX reference in any instruction, stop and re-read the full rule before proceeding. No shortcuts.

**Default behavior:** All rules apply at all times unless explicitly waived for a specific session.

---

## RULE-BRANCH-CHECK
### Verify Reality Before Any Work

**The rule:** At the start of every session, before reading files or writing code, run:

```bash
git branch --show-current
```

Report the branch name to Scott in your first message. If the branch name does not match what Scott expected, STOP. Do not proceed until mismatch is resolved.

**Why this exists:** On 2026-04-17, Opus said `claude/gifted-feynman` and Sonnet said `claude/goofy-hodgkin`. Branch name drift between sessions is a lost-work risk. Committing to the wrong branch is painful to untangle.

**When this applies:** Every session. Every time. No exceptions.

---

## RULE-RECON-FIRST
### No Code Changes Without Reconnaissance

**The rule:** For any change touching more than one file, OR any change to a prompt/config file, OR any change to the Deposition Engine pipeline:

1. Do recon first — read the actual current state of every file you'll touch
2. Report findings to Scott in structured format
3. Wait for explicit "go build" before writing any code

Recon is NOT optional. Recon is NOT "I'll just start and check as I go." Recon is a separate deliverable with a separate approval gate.

**Why this exists:** On 2026-04-17, the v1.0 spec went into the kickoff with 3 contradictions identified. Sonnet's recon pass found a 4th contradiction that would have silently broken the fix. Without the recon gate, that 4th contradiction would have shipped to production.

**The test:** If Scott asks "did you do recon?" you should be able to paste the structured recon report. If you can't, you violated this rule.

**When this applies:** Any multi-file change. Any prompt edit. Any pipeline change. When in doubt, do recon.

---

## RULE-CONTRADICTION-HUNT
### Actively Look for Conflicting Instructions

**The rule:** When modifying any prompt file, config file, or system instruction, you do NOT just patch what you were told to patch. You actively search the entire file (and related files) for OTHER instructions that might contradict or undo the change.

Specifically:
1. Grep the full file for every concept related to the change (e.g., if changing Q/A labeling, grep for "Q.", "A.", "label", "alternation", "speaker")
2. Read every hit in context
3. Report ALL contradictions found — including ones Scott didn't ask about
4. Do not build until all contradictions are resolved

**Why this exists:** On 2026-04-17, Opus identified 3 Q/A labeling contradictions in `MASTER_DEPOSITION_ENGINE_v4.1.md`. There were actually 4. The 4th (line 592) would have silently undone the fix. Sonnet caught it by grepping aggressively — not by trusting the spec's count.

**The test:** Before declaring prompt-file work complete, you should be able to say: *"I grepped the full file for X keywords. I found Y hits. Z of them were contradictions. All Z have been addressed."*

**When this applies:** Every prompt file edit. Every system-instruction change. Every config file that controls model behavior.

---

## RULE-SILENT-FAILURE-CHECK
### A Fix Isn't Done Until You Prove Nothing Downstream Undoes It

**The rule:** Before declaring any step complete, explicitly answer:

> *"Is there any layer downstream of this change that could undo what I just did?"*

This includes:
- Self-audit loops that run AFTER your change
- Validation layers that "correct" output
- Formatting passes that normalize
- Other prompts/configs that re-assert the old behavior
- Test fixtures that encode the old expectations

If any downstream layer can undo the fix, the fix is NOT complete. You must either:
- Patch the downstream layer too (preferred), OR
- Document explicitly why the downstream layer won't actually trigger in practice (risky — requires Scott approval)

**Why this exists:** On 2026-04-17, Sonnet caught that Layer 11's self-audit ("No two Q. lines in a row") would silently undo the preservation fix being made at Layer 1A. This would have been a silent failure — tests pass, output wrong, no alarm. The kind of bug that destroys court-reporter credibility.

**The test:** For each step of a coordinated fix, you should be able to list every downstream layer you checked and why it won't undo the change.

**When this applies:** Every multi-layer fix. Every change to a pipeline with validation/audit stages. Every Deposition Engine work.

---

## RULE-DEPO-PRIME-DIRECTIVE
### Accuracy and Credibility Are the Only Stats That Matter

**The rule:** Before any code change to the Deposition Engine, answer:

> *"Could what I am about to code — in any way — reduce the accuracy or credibility of the transcript output?"*

If the answer is **yes** or **maybe** — STOP. Surface it to Scott. Do not make the change until Scott has reviewed and decided.

This rule lives in the master `CODER_MINDSET_v1.md` but is repeated here because **the Deposition Engine is the product**. If the transcript is wrong, the platform fails. If the transcript is right but slow, the platform succeeds. Speed matters only after accuracy is locked.

**Why this exists:** MyReporterX sells to court reporters who stake their professional reputation on every transcript. A single fabricated speaker turn, a stripped attorney attribution, or a silently mis-labeled Q/A can surface months later in a deposition review and destroy that reporter's credibility. This is not a theoretical risk. This is the core product risk.

**The test:** For every PR, you should be able to say: *"I asked the accuracy question. My answer was [yes/maybe/no]. Here's the evidence."*

**When this applies:** Every single Deposition Engine change. Every prompt edit. Every pipeline change. No exceptions.

---

## RULE-INPUT-IS-SACRED
### Preserve, Don't Normalize

**The rule:** When input arrives at any stage of the Deposition Engine, the default behavior is PRESERVE. Normalization, cleanup, or "fixing" requires explicit justification.

Specifically:
- `MR. LASTNAME:` labels — preserve verbatim, regardless of position
- Attorney identification lines (`BY MR. X`) — preserve verbatim
- Examination headers — preserve verbatim
- Exhibits and exhibit references — preserve verbatim
- Existing Q./A. labels (from pipeline or steno) — preserve unless you have phonetic/semantic evidence to override

If you believe normalization is needed, flag it in Proof of Work. Do NOT silently normalize.

**Why this exists:** DEF-B (the MR. LASTNAME stripping bug) happened because somewhere downstream, a "normalization" step stripped attorney name labels in pre-examination sections. Nobody authorized it. Nobody noticed it. It destroyed attribution in court-record-critical content.

**The test:** If your code strips, normalizes, or alters input without explicit instruction to do so, you violated this rule.

**When this applies:** Every stage of the Deposition Engine pipeline. Especially `apply_ops.py`, `format_final.py`, `validate_ops.py`.

---

## RULE-PROOF-OF-WORK
### Every Automatic Change Gets Logged

**The rule:** Any change the engine makes to input — whether a correction, a re-label, a turn break, a punctuation fix, or a normalization — must be logged in Proof of Work with:

- What was changed
- Why it was changed (rule invoked)
- Confidence level
- Whether human review is recommended

Silent changes are forbidden. If the engine can't explain a change in the Proof of Work log, the engine should not make the change.

**Why this exists:** MB (the court reporter SME) needs to be able to review every change the engine made and either accept it or override it. An engine that makes silent changes is an engine she can't trust. An engine she can't trust is an engine she won't use. An engine she won't use is a failed product.

**The test:** Every corrected or modified line in the output should have a corresponding Proof of Work entry.

**When this applies:** Every Deposition Engine transformation stage.

---

## RULE-MB-IS-THE-CUSTOMER
### Think Like the Court Reporter, Not the Engineer

**The rule:** Every decision, every feature, every error message, every log format — filter through the question:

> *"Can MB (a 30-year court reporter with no programming background) understand this, trust this, and use this without a manual?"*

If the answer is no, the work is not done.

**Why this exists:** Scott's origin story — his friend who wanted to clone himself to do post-capture work. That friend is MB's archetype. She doesn't care about MFA phoneme models or Deepgram confidence scores. She cares about whether the transcript is right and whether she can tell it's right at a glance.

When engineering complexity leaks into MB's world, she loses trust. When MB loses trust, the product dies.

**The test:** If a feature requires technical jargon in the UI or documentation, it's not done.

**When this applies:** Every customer-facing surface. Every log MB will read. Every error message. Every Proof of Work entry.

---

## RULE-SPEC-BEFORE-BUILD
### No Multi-File Changes Without a Written Spec

**The rule:** If a fix or feature touches more than one file, there must be a written spec approved by Scott before any code is written. The spec lives in `/docs/specs/` with date prefix and descriptive name.

The spec must include:
- Defect IDs or feature description
- Files touched and why
- Prime Directive check per file
- Rollout sequence with rationale
- Test plan
- Rollback plan
- Open items requiring Scott sign-off

**Why this exists:** On 2026-04-17, the chunk_01 cascade issue required touching 4 files across 4 systems. Without a written spec, the change would have rippled through inconsistently — 4 separate sessions, 4 separate assumptions, 4 cascading bugs.

**The test:** For any multi-file PR, there should be a linked spec document.

**When this applies:** Any change touching more than one file. Any change to a system with coordinated rollout requirements.

---

## RULE-ARCHITECT-PM-BUILDER-SEPARATION
### Know Your Role This Session

**The rule:** In the MyReporterX platform, three roles are clearly separated:

| Role | Who | Job |
|------|-----|-----|
| Architect | Claude Chat (Opus) | Specs, design decisions, cross-session continuity |
| Builder | Claude Code (Sonnet) | Recon, code changes, tests, commits |
| PM | Scott | Final calls, priorities, customer voice |

If you are Claude Code (Sonnet), your job is to build what the spec says. You can PUSH BACK with evidence when you see risk — that's required. But the architect owns design decisions, and Scott owns final calls.

If you are Claude Chat (Opus), your job is to write specs and interpret builder reports. You do NOT write code directly in this chat. You do NOT bypass the builder.

**Why this exists:** Role confusion leads to duplicate work, contradicting decisions, and lost context. Clear roles keep the loop tight.

**The test:** If you're writing code in Claude Chat, you might be in the wrong role. If you're making design decisions without consulting the architect in Claude Code, you might be in the wrong role.

**When this applies:** Every session. Every interaction.

---

## Quick Reference: Rule Invocation Cheat Sheet

| Rule ID | One-line summary |
|---------|------------------|
| `RULE-BRANCH-CHECK` | Verify branch with `git branch --show-current` at session start |
| `RULE-RECON-FIRST` | Do recon before any multi-file change |
| `RULE-CONTRADICTION-HUNT` | Actively grep for contradictions when editing prompts/configs |
| `RULE-SILENT-FAILURE-CHECK` | Prove nothing downstream undoes the fix |
| `RULE-DEPO-PRIME-DIRECTIVE` | Ask the accuracy/credibility question before any Depo Engine change |
| `RULE-INPUT-IS-SACRED` | Preserve input; normalization requires justification |
| `RULE-PROOF-OF-WORK` | Every automatic change gets logged |
| `RULE-MB-IS-THE-CUSTOMER` | Filter through the court reporter lens |
| `RULE-SPEC-BEFORE-BUILD` | No multi-file changes without a written spec |
| `RULE-ARCHITECT-PM-BUILDER-SEPARATION` | Know your role this session |

---

## Version Policy

This addendum versions up when rules are added, removed, or substantially changed. Minor clarifications can be edited in place. When a new rule is added, it gets a RULE-XXX ID and joins the Quick Reference table.

Next bump: `v2` when we have enough new rules to justify. File as `CODER_MINDSET_MYREPORTERX_ADDENDUM_v2.md` and archive v1 to `MASTER_COPIES/archive/`.

---

*CODER_MINDSET_MYREPORTERX_ADDENDUM_v1.md — Store at: repo root + C:\Users\scott\OneDrive\Documents\MASTER_COPIES\*
*Built: April 17, 2026 — Lessons learned from the chunk_01 cascade fix*

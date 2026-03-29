# ═══════════════════════════════════════════════════════════════════
# CURRENT_SPRINT.md — INSTRUCTIONS FOR CODE CLAUDES
# Deposition Transformation Engine
# ═══════════════════════════════════════════════════════════════════
# Written by: Project Lead Claude
# For:        Code Claudes working in Claude Code
# Updated:    2026-03-29
# ═══════════════════════════════════════════════════════════════════
# BEFORE YOU TOUCH ANYTHING:
#   1. Read CLAUDE.md fully — that is the technical ground truth.
#   2. Read this file fully — these are your exact tasks.
#   3. Do not invent scope. Do exactly what is written here.
#   4. When done with a task, say so clearly so Scott can log it.
# ═══════════════════════════════════════════════════════════════════

## SPRINT GOAL
Close the gap from 78% → 90%+ on the Easley benchmark.
The Easley depo (031326yellowrock-ROUGH_T_1.rtf, ~191K chars,
Yellow Rock v. Westlake) is the reference dataset.
117 manual corrections in PROOF_OF_WORK.txt = the answer key.

---

## CONTEXT YOU MUST HOLD

**The pipeline:**
```
extract_rtf.py  →  extracted_text.txt
steno_cleanup.py → cleaned_text.txt
ai_engine.py    → corrected_text.txt + correction_log.json
format_final.py → FINAL_DELIVERY/ (8 output files)
```

**The AI correction stage (ai_engine.py) is what we are optimizing.**
It reads cleaned_text.txt, calls Claude API in ~3,000-char chunks,
applies all engine rules, and outputs corrected_text.txt.

**The scoring target:**
correction_log.json output must match ≥ 90% of the 117 corrections
in PROOF_OF_WORK.txt. We are currently at 78%.

**Key gotcha — verbatim rule (KB-010):**
NEVER correct what the witness said. Only correct steno machine errors.
This was a critical failure in L1-001. A 30-year veteran flagged it
as a disqualifying error. Do not touch witness speech, ever.

**Key gotcha — two-pass mode:**
The Easley depo is 191K chars — well above the 100K SIZE GATE.
ai_engine.py must run in two-pass mode (see CLAUDE.md Layer 2, Steps F+G).
Pass 1 writes PROCESSING_NOTES.txt only. Pass 2a + 2b write everything else.
Do NOT try to produce all 8 output files in a single pass — it will hit
the 32K output token ceiling and produce nothing.

**Key gotcha — prompt caching:**
The system prompt (~47K tokens) is cached after chunk 1.
Subsequent chunks cost ~10% of chunk 1. Don't break this.
The cache_control block in correct_chunk() must stay intact.

---

## ⚠️ OPEN ITEMS THAT AFFECT YOUR WORK

These are unresolved. Do not make decisions on these — flag and wait:

- **KB-008:** Casing size notation (Style A vs Style B) is UNRESOLVED.
  Engine currently uses Style B as interim. Do not change this until
  Scott confirms the answer.
- **KB-006:** Casing physics rule scoring is disputed. Rule itself is
  valid — apply it. But do not adjust scoring expectations around it.
- **KB numbering:** Some entries use "LA-KB-" prefix, most use "KB-".
  Do not renumber until Scott decides. Keep as-is.

---

## ACTIVE TASKS

### TASK 1 — Verify pipeline scripts exist
**Status:** UNKNOWN — needs verification
**Files to check:** All in `C:\Users\scott\OneDrive\Documents\CR_Depo_Transform`

Check whether these scripts exist and are functional:
- `extract_rtf.py` (Stage 1)
- `steno_cleanup.py` (Stage 2)
- `format_final.py` (Stage 4)

For each one:
- If it exists → report what it does and its current version/status
- If it does not exist → report it as missing so Scott can decide priority

Do NOT build any of these yet. Report first.

---

### TASK 2 — Run scoring pass on Easley depo
**Status:** PENDING (do after Task 1 confirms pipeline is intact)
**Input:** 031326yellowrock-ROUGH_T_1.rtf
**Reference:** PROOF_OF_WORK.txt (117 manual corrections = answer key)
**Output:** Score report comparing correction_log.json to answer key

Steps:
1. Run full pipeline on Easley depo (two-pass mode — it's 191K chars)
2. Compare correction_log.json to PROOF_OF_WORK.txt
3. Report: how many of the 117 corrections did the engine catch?
4. Report: what categories are we missing? (objections, exhibits, verbatim, punctuation, etc.)
5. Do NOT modify any engine files during this task — observe only

The goal is a gap analysis, not a fix. We fix in Task 3.

---

### TASK 3 — Gap closure (do after Task 2 gap analysis)
**Status:** BLOCKED on Task 2
**Goal:** Improve score from 78% to 90%+

Based on Task 2 gap analysis, make targeted improvements to:
- `KNOWLEDGE_BASE.txt` — add new KB entries for confirmed missed patterns
- `ai_engine.py` — only if a specific rule application is broken in code
- Do NOT touch `MASTER_DEPOSITION_ENGINE_v4.md` without Scott's approval
- Do NOT touch any STATE_MODULE or HOUSE_STYLE_MODULE without Scott's approval

For every change you make:
- State what you changed
- State why (which missed corrections it addresses)
- State what KB entry it maps to (or that a new KB entry is needed)

---

## DONE THIS SPRINT
*(Project Lead Claude updates this when Scott confirms something shipped)*

| Task | Completed | Notes |
|------|-----------|-------|
| Project management system | 2026-03-29 | CLAUDE.md, PROJECT_BOARD.md, CURRENT_SPRINT.md created |

---

## HOW TO COMMUNICATE BACK

When you finish a task or hit a blocker, be explicit:

**If task complete:**
> ✅ TASK [#] DONE — [one line summary of what you did]
> Files changed: [list]
> Ready for: [what comes next]

**If blocked:**
> 🔴 BLOCKED ON TASK [#] — [what's blocking you]
> Need from Scott: [specific question or decision]

**If you find something unexpected:**
> ⚠️ FLAG — [what you found, where, why it matters]
> Recommendation: [what you think should happen]

Do not silently fix things outside your task scope.
Flag them and wait. Over-communicate. Scott wants to know everything.

---
*Written by: Project Lead Claude*
*Last updated: 2026-03-29*
*Next update: when Scott pings with new progress or decisions*

---

# ═══════════════════════════════════════════════════════════════════
# PM FULL BRIEFING — FROM CODE CLAUDE (mb_demo_engine_v4)
# Appended: 2026-03-29 by Claude Code (worktree: romantic-dubinsky)
# ═══════════════════════════════════════════════════════════════════
# PM — Read this before making any decisions. The project has moved
# significantly past what CLAUDE.md currently reflects.
# ═══════════════════════════════════════════════════════════════════

## ⚠️ CRITICAL REORIENTATION — TWO CODEBASES

The CLAUDE.md in this folder (`CR_Depo_Transform`) reflects an older
snapshot (circa 2026-03-22). The REAL production engine lives here:

**ACTIVE ENGINE:**
`C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\`

`CR_Depo_Transform\` = early sandbox / reference only.
All future code work happens in `mb_demo_engine_v4\`.

---

## WHAT THIS BUSINESS IS

Scott is building a **court reporter AI assist** business.

**The product:** Raw steno RTF → clean, formatted deposition PDF + 9
supporting files, ~90%+ quality, ~60 minutes runtime.

**The customer:** Court reporters (CRs) who produce deposition
transcripts. The engine augments their work — it does not replace them.
Their name, their brand, their certification. Our engine = their power tool.

**Current CRs in pipeline:**
| Reporter | Location | Specialty | Status |
|----------|----------|-----------|--------|
| MB (Marybeth E. Muir, CCR, RPR) | Louisiana | Civil, engineering/petroleum | Active client — reviewing output |
| AD (Alicia D'Alotto) | New York | Workers Comp Board (WCB) | Cold test complete |

---

## WHAT THE ENGINE PRODUCES (10 files per depo)

Every run drops these in `FINAL_DELIVERY/`:
1. `FINAL.pdf` — formatted deposition PDF (lawyer-ready)
2. `FINAL_TRANSCRIPT.txt` — clean full transcript
3. `CONDENSED.txt` — 4-line-per-page condensed version
4. `EXHIBIT_INDEX.txt`
5. `DEPOSITION_SUMMARY.txt` (Haiku AI, ~$0.06/depo)
6. `MEDICAL_TERMS_LOG.txt` (WC/medical cases)
7. `QA_FLAGS.txt` → being replaced by `build_review_sheet.py` (next build)
8. `PROOF_OF_WORK.txt`
9. `DELIVERY_CHECKLIST.txt`
10. `WORD_CONCORDANCE.txt` (3-column layout, 7 pages, speaker index)

---

## ARCHITECTURE — THE 3-PASS WORKFLOW (DESIGNED, PARTIALLY BUILT)

```
Pass 1 — AI Engine (ai_engine.py)
  → corrected_text.txt + correction_log.json
  → 122 corrections classified HIGH / MEDIUM / LOW

Pass 2 — Verify Agent (verify_agent.py) [BUILT, NOT YET RUN]
  → Targets only 62 HIGH confidence items
  → Second-opinion AI pass, catches AI's own errors

Pass 3 — Audio Agent (audio_agent.py) [DESIGNED, NOT BUILT]
  → Detects MP3/M4A in depo folder
  → Batches REVIEW gaps (unknown words, unclear audio)
  → Whisper API transcription at exact timestamps
  → Produces review_sheet.py (CR's listening queue)

CR approves → certified final
```

The Review Sheet (not yet built) = the CR's listening queue:
page/line + context + audio timestamp per gap. CR listens only to
the flagged moments, not the whole recording.

---

## COMPLETED DEPOS (PRODUCTION RUNS)

| Depo | Reporter | Pages (ours) | Pages (CR) | Gap | Status |
|------|----------|-------------|------------|-----|--------|
| Easley (Yellow Rock v. Westlake) | MB | 211 | 223 | 12 (known, acceptable) | ✅ Ready to send to MB |
| YellowRock/Brandl | MB | 318 | — | — | ✅ Complete |
| Fourman WCB (M.D.) | AD | 27 | 28 | 1 (steno content only) | ✅ Cold test baseline |

**Fourman** = first cold test of the NY WC format. All format bugs fixed.
27 vs AD's 28 pages — 1-page gap is content AD needs to supply from steno,
not an engine error. Parity confirmed.

---

## NEXT BUILDS (in priority order)

| # | Task | Who | Status |
|---|------|-----|--------|
| 1 | **MB meeting 3/30** — 30 min walkthrough | Scott | 🔴 TOMORROW |
| 2 | **Identify mystery RTF** Scott found | Scott + Code Claude | 🔴 Monday |
| 3 | **Leon folder setup** — copy engine to alicia_demo/, update config for CA WCAB | Code Claude | 🔴 Ready |
| 4 | **Run verify_agent.py on Fourman** — first 2-pass test | Code Claude | 🔴 Ready |
| 5 | **build_review_sheet.py** — page/line + audio timestamp, replaces QA_FLAGS | Code Claude | 🟡 |
| 6 | **Audio agent design** — Whisper API, batch REVIEW gaps | Code Claude + Scott | 🟡 |
| 7 | **HOUSE_STYLE_MODULE_dalotto.md** — AD's NY WC style rules | Code Claude | 🟡 |
| 8 | **Send Easley + Brandl to MB** — formal review, start feedback loop | Scott | 🔴 Waiting on Scott |

---

## LEON DEPO — NEXT TEST CASE

**Purpose:** First CA WCAB run + first audio agent test
**Folder:** `C:\Users\scott\OneDrive\Documents\alicia_demo\`
**RTF:** `0313Leon2026_T.rtf` (CaseCATalyst, March 13)
**Audio:** `-7849480339599919352.mp3` (iPhone Voice Memo, 13m 53s)
**Reporter:** AD (Alicia D'Alotto)
**State:** California WCAB (NOT NY — different state module needed)
**Note:** No AD final to compare against. Pure pipeline + audio agent test.

---

## BUSINESS MODEL CONTEXT (PM needs this for pricing/marketing)

**Positioning:** Augment CR brand, not replace. CR still certifies.
Engine removes the grunt work — steno artifact cleanup, formatting,
exhibit tracking, Q&A structure. CR's value add = judgment + certification.

**Economics (10-Cent Page Rule — design discipline, not pricing):**
- Actual API cost: ~$0.007/page (13x headroom under $0.10 ceiling)
- Every architecture decision stress-tested: can it survive $0.10/page?
- Current: YES. 93% of budget unused.

**Revenue model (TBD — PM to help think through):**
- Per-depo fee to CR? Monthly subscription? Revenue share?
- MB is the first real customer. Her feedback = product-market fit signal.
- Scott has NOT yet formally delivered output to MB for review.

**Key constraint:** CR delivers under their own name. Product must be
invisible to lawyers/clients. Engine = back office, not front office.

---

## SCOTT'S OPERATING RULES (PM must internalize these)

1. **Simple but no simpler.** Reliability > cleverness. 1969 Valiant, not a race car.
2. **Look before you dive.** Flag "pool has no water" before executing. One sentence, then proceed.
3. **FORK flag.** Hack vs right solution — surface it, let Scott decide. Log hacks as `[TECH DEBT]`.
4. **Mama Bear Rule.** Commit before every build. Both repos tracked. Codebase = baby.
5. **Buffet vs Pizza.** Scott unsure → show 2-3 options. Scott knows → execute, flag risks only.
6. **"Button it up" = full housekeeping.** Commit code, update bug table, update docs, report clean.

---

## HOW CODE CLAUDES COMMUNICATE BACK TO PM

When Code Claude finishes a task, it appends to this file using:

✅ TASK DONE — [summary]
Files changed: [list]
Ready for: [what's next]

🔴 BLOCKED — [what's blocking]
Need from Scott/PM: [specific question]

⚠️ FLAG — [unexpected finding]
Recommendation: [suggestion]

---
*PM Briefing written by: Code Claude (mb_demo_engine_v4 worktree)*
*Date: 2026-03-29*
*Source: memory system + cold_start_primer.md + project_next_steps.md*

# ═══════════════════════════════════════════════════════════════════
# PROJECT_BOARD.md — SCOTT + PROJECT LEAD CLAUDE
# Deposition Transformation Engine
# ═══════════════════════════════════════════════════════════════════
# THIS FILE IS FOR SCOTT + PROJECT LEAD CLAUDE ONLY.
# Code Claudes: read CLAUDE.md and CURRENT_SPRINT.md instead.
# ═══════════════════════════════════════════════════════════════════
# HOW TO USE:
#   Ping project lead Claude any time — session start, mid-day,
#   when something ships, when something breaks, or just to think.
#   Claude will update this board, rewrite CURRENT_SPRINT.md for
#   code Claudes, and keep the GitHub as the PM source of truth.
# ═══════════════════════════════════════════════════════════════════

## PROJECT SNAPSHOT
**Project:**      Deposition Transformation Engine
**Active repo:**  `C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\`
**GitHub:**       https://github.com/sluglife1414-ux/Court_reporting_demo (PRIVATE, branch: court_reporting)
**Job folder:**   `C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\` (Brandl active)
**Version:**      v4.1 (state-agnostic core, config-driven builds, 2-pass verify)
**Goal:**         90%+ automated depo cleanup, lawyer-ready output
**Run cost:**     ~$0.007/page actual — 13x headroom under $0.10 design ceiling
**Model:**        claude-sonnet-4-6 (AI pass), claude-haiku-4-5-20251001 (summary/verify)

---

## WHAT THIS BUSINESS IS

Scott is building a **court reporter AI assist** business.

**The product:** Raw steno RTF → clean formatted deposition PDF + 9 supporting files.
~90% quality. ~60 min runtime. $2–4 per full run.

**The model:** CR delivers under their own name. Engine is invisible to lawyers/clients.
Their brand. Their certification. Our engine = their power tool.

**Current CRs in pipeline:**
| Reporter | Location | Specialty | Status |
|----------|----------|-----------|--------|
| MB (Marybeth E. Muir, CCR, RPR) | Louisiana | Civil, engineering/petroleum | Active — Brandl defect fix in progress |
| AD (Alicia D'Alotto) | New York | Workers Comp Board (WCB) | Fourman cold test ✅ complete — on hold |

---

## WHAT THE ENGINE PRODUCES (10 files per depo)

Every run drops these in `FINAL_DELIVERY/`:
1. `FINAL.pdf` — formatted deposition PDF (lawyer-ready)
2. `FINAL_TRANSCRIPT.txt` — clean full transcript
3. `CONDENSED.txt` — 4-line-per-page condensed version
4. `EXHIBIT_INDEX.txt`
5. `DEPOSITION_SUMMARY.txt` (Haiku AI, ~$0.06/depo)
6. `MEDICAL_TERMS_LOG.txt` (WC/medical cases)
7. `QA_FLAGS.txt` → being replaced by `build_review_sheet.py` (backlog)
8. `PROOF_OF_WORK.txt`
9. `DELIVERY_CHECKLIST.txt`
10. `WORD_CONCORDANCE.txt` (3-column layout, speaker index)

---

## ARCHITECTURE — THE 3-PASS WORKFLOW

```
Pass 1 — AI Engine (ai_engine.py)
  → corrected_text.txt + correction_log.json
  → Classifications: HIGH / MEDIUM / LOW confidence

Pass 2 — Verify Agent (verify_agent.py) [BUILT, NOT YET RUN]
  → Targets only HIGH confidence items
  → Second-opinion AI pass, catches AI's own errors

Pass 3 — Audio Agent (audio_agent.py) [DESIGNED, NOT BUILT]
  → Detects MP3/M4A in depo folder
  → Batches REVIEW gaps (unknown words, unclear audio)
  → Whisper API transcription at exact timestamps
  → Produces build_review_sheet.py output (CR's listening queue)

CR approves → certified final
```

**Pre-AI step added 2026-04-15:**
```
label_qa.py — runs after steno_cleanup, before ai_engine
  → Detects testimony sections, assigns structural Q/A blocks
  → ⚠️ UNDER REVISION — Q/A assignment logic has cascade bug (DEF-A)
     Design spec required before next AI run
```

**CR state module system:**
- Each CR has their own `HOUSE_STYLE_MODULE_<name>.md`
- Each state has its own `STATE_SPECS/` config
- NEVER cross-load modules (AD's NY WC rules ≠ MB's LA civil rules)

---

## COMPLETED DEPOS

| Depo | Reporter | Pages (ours) | Pages (CR) | Gap | Status |
|------|----------|-------------|------------|-----|--------|
| Easley (Yellow Rock v. Westlake) | MB | 211 | 223 | 12 (known, acceptable) | ⏸ Holding — send after Brandl fix |
| YellowRock/Brandl | MB | 354 | 357 | 3 (cert/errata, not material) | ⚠️ Defects found — fix in progress |
| Fourman WCB (M.D.) | AD | 27 | 28 | 1 (steno content only) | ✅ Cold test baseline — on hold |

**Page gap note:** Gap is not a bug. MB's CaseCATalyst preserves short steno-stroke
line breaks; our engine reflows at 52 chars. 1-page Fourman gap = content AD must
supply from steno, not an engine error.

---

## 🔴 BLOCKERS — Nothing ships until these are resolved

| # | Blocker | Owner | Notes |
|---|---------|-------|-------|
| B-1 | Easley + Brandl not yet formally reviewed by MB | Scott | Holding until Brandl Q/A defects fixed. MB has not seen our output. |
| B-2 | Brandl Q/A cascade defects (DEF-A, DEF-A2, DEF-B) | Code Claude + Opus | Design spec required. 3-file coordinated fix. Do not run AI pass until resolved. |
| B-3 | Phone audio download blocked | Scott | Leon M4A stuck on phone. Can't test audio agent until resolved. |

---

## 🟡 OPEN ITEMS — Decisions needed

| # | Item | Owner | Notes |
|---|------|-------|-------|
| OI-1 | DEF-B mechanism (MR. name strip) | Code Claude | Context-dependent: pre-exam stripped, mid-exam preserved. Root cause unknown — investigation task for design phase. |
| OI-2 | DEF-014 acceptance test gap | Code Claude | File in DEFECT_LOG.md — structural Q/A checks needed. Scoped for design spec phase. |
| OI-3 | Leon CA WCAB state module | Scott | No STATE_MODULE_california_wcab.md exists. Needed for Leon run. On hold pending Brandl fix. |
| OI-4 | Revenue model | Scott + PM | Per-depo fee, monthly subscription, or revenue share? MB = first signal. |
| OI-5 | KB-008 casing size notation | Scott | Style A vs Style B still unresolved. Interim = Style B. |
| OI-6 | AD_QUESTIONS.md open items | Scott + AD | 6 open questions for AD before NY WC is production-ready. |

---

## 🟢 CURRENT SPRINT
→ See **CURRENT_SPRINT.md** for full code Claude instructions.

**Sprint goal:** Brandl Q/A defect fix — sync worktree, file DEF-014, then Opus design spec
**Active tasks:** See CURRENT_SPRINT.md

---

## ✅ SHIPPED — What's done and locked

| Date | What shipped | Notes |
|------|-------------|-------|
| 2026-03-25 | ai_engine.py v2.0 | Full chunked API pipeline, prompt caching, checkpoint/resume |
| 2026-03-25 | steno_cleanup.py | 8-step steno artifact cleanup |
| 2026-03-26 | extract_config.py | Auto-extracts 19 case metadata fields from transcript |
| 2026-03-26 | run_pipeline.py | One command runs all 9 steps; --skip-ai, --from, --dry-run flags |
| 2026-03-26 | audio_resolve POC | 4/4 PASS on Brat→Bright Spot. Silence-padding fix applied. |
| 2026-03-27 | Option B anchor injection | 333/333 Brandl items covered (292 exact, 31 approx, 10 unknown) |
| 2026-03-27 | test_regression.py | 36 tests, ~3 sec/run, in both repos |
| 2026-03-27 | build_summary.py | Haiku AI, 3-5 para narrative summary, ~$0.06/depo |
| 2026-03-27 | MB_REVIEW doc system | build_mb_review_v2.py — proof + action items for CR |
| 2026-03-28 | Fourman WCB cold test | 27 pages vs AD's 28. All format bugs fixed. git init done. |
| 2026-03-28 | specialist_verify.py | 6-agent verification pass |
| 2026-03-28 | HOUSE_STYLE_MODULE_dalotto.md | AD (NY WC) style seed |
| 2026-03-28 | AD_QUESTIONS.md | 6 open items for AD before Fourman ships |
| 2026-03-29 | PM coordination system | CLAUDE.md, PROJECT_BOARD.md, CURRENT_SPRINT.md |
| 2026-04-13–15 | DEF-001 through DEF-013 closed | Full defect sprint — see DEFECT_LOG.md |
| 2026-04-15 | label_qa.py | Pre-AI Q/A structure labeler — wired into run_pipeline.py |
| 2026-04-15 | acceptance_test.py | Pattern-based output checks. Brandl v5: PASS. Caveat: blind to Q/A structure. |
| 2026-04-15 | Brandl v5 acceptance test | 354 pages, zero bleed, all DEF-001..DEF-013 checks pass — BUT test is blind to Q/A structure (DEF-014). Output contains cascade defects. NOT shippable to MB as-is. |
| 2026-04-16 | Pipeline stability fixes (main) | SSL retry, run_pipeline os.path.exists, --from steno input check |
| 2026-04-17 | docs/evidence/2026-04-16_chunk_01_defects.md | April 16 session evidence preserved to disk |

---

## 📋 BACKLOG — Queued but not started

| Priority | Item | Notes |
|----------|------|-------|
| HIGH | Opus design spec: 3-file Q/A fix | label_qa.py + MASTER_DEPOSITION_ENGINE + ai_engine.py. Do not code without spec. |
| HIGH | Structural Q/A checks in acceptance_test.py | DEF-014. Empty Q label, Q/A ratio, cascade detection. |
| HIGH | Send Easley + Brandl to MB | Start feedback loop. Holding until Brandl Q/A fix confirmed clean. |
| HIGH | Audio agent (audio_agent.py) | Whisper API, detect MP3/M4A in folder, batch REVIEW gaps |
| MEDIUM | build_review_sheet.py | CR listening queue: page/line + audio timestamp per gap. Replaces QA_FLAGS.txt |
| MEDIUM | STATE_MODULE_california_wcab.md | Needed for Leon run |
| MEDIUM | AD_QUESTIONS.md resolution | Get answers from AD before NY WC goes to production |
| LOW | Multi-witness deposition handling | Currently single-witness only |
| LOW | Auto-glossary builder | Build glossary.txt from first-run corrections automatically |

---

## 🧠 DECISIONS LOG

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-25 | claude-sonnet-4-6 for AI pass | Cost vs quality — $2–4/run acceptable |
| 2026-03-25 | Chunk at paragraph boundaries | Preserves Q&A integrity — never split a Q/A pair |
| 2026-03-26 | --skip-ai flag required if corrected_text.txt exists | Protect 56 min of AI work from accidental overwrite |
| 2026-03-27 | 10-Cent Page Rule | Design discipline. $0.007 actual vs $0.10 ceiling = 13x headroom |
| 2026-03-27 | Mama Bear Rule | Commit before every build. Both repos. Codebase = baby. |
| 2026-03-28 | muir.md BLOCKED from NY runs | NY WC ≠ LA civil. Never cross-load style modules. |
| 2026-03-28 | "Agent" not "AI" in user-facing text | CR audience — "agent" is clearer and less alarming |
| 2026-03-28 | Review sheet = CR listening queue | Page/line + context + audio timestamp. CR listens only to flagged moments |
| 2026-03-28 | Fourman = 1-pass baseline | verify_agent.py not run intentionally — cold baseline first |
| 2026-04-17 | Hold Brandl/Easley delivery until Q/A fix confirmed | DEF-A cascade inverts speaker attribution — output not CR-ready |
| 2026-04-17 | Design spec before code on Q/A fix | Three-file conflict — touching one without the others makes it worse |

---

## 📝 SESSION LOG

**2026-04-17 (SYNC session — ramp-up + doc recovery)**
- Ramp-up revealed CURRENT_SPRINT.md and PROJECT_BOARD.md stale since 2026-03-30
- April 16 evidence session had no button-up note — protocol failure
- Evidence preserved: docs/evidence/2026-04-16_chunk_01_defects.md (commits 4e9a825, 485b98b)
- CURRENT_SPRINT.md and PROJECT_BOARD.md updated to reflect current state
- SYNC STEPs 3-5 still in progress

**2026-04-16 (Evidence-gathering session — no commits at session end)**
- Read-before-think protocol on Brandl chunk_01 baseline output
- Found DEF-A (Q/A cascade), DEF-A2 (empty Q label), DEF-B (MR. name strip)
- Identified DEF-E (colloquy intrusion) — parked
- Identified three-way prompt contradiction as root cause of cascade unpredictability
- Opus to design coordinated 3-file fix spec — deferred to next session when Scott is fresh. Spec depends on seeing April 16 commit diffs (SYNC STEP 4).
- 3 pipeline stability commits landed on main (SSL retry, run_pipeline fixes)
- ⚠️ Session ended without button-up note — evidence lost until 2026-04-17

**2026-04-13–15 (Defect sprint — Brandl)**
- DEF-001 through DEF-013 closed (see DEFECT_LOG.md)
- label_qa.py built and wired into pipeline
- acceptance_test.py built — Brandl v5: PASS, 354 pages, zero bleed
- ⚠️ Acceptance test later found to be blind to Q/A structural defects (DEF-014)

**2026-03-29 (PM system created)**
- CLAUDE.md, PROJECT_BOARD.md, CURRENT_SPRINT.md created for PM coordination

**2026-03-28 (Sessions 13-14 — Fourman WCB cold test)**
- Full cold run: 27 pages vs AD's 28 — parity confirmed ✅
- All 10 format bugs fixed
- git init on ad_foreman_0324
- specialist_verify.py built (not yet run on Fourman)
- Leon depo discovered (CA WCAB, alicia_demo/)
- Architecture: 3-pass workflow designed, review sheet spec'd

**2026-03-27 (Sessions 7-12)**
- Easley tip-to-tail rerun → 202 pages reproducible
- 10 format bugs found and fixed vs MB reference
- YellowRock/Brandl full run: 318 pages, 2,381 corrections
- Option B anchor injection: 333/333 items covered
- Regression harness: 36 tests in both repos
- MB_REVIEW doc system built

**2026-03-25–26 (Sessions 1-6)**
- ai_engine.py v2.0 rebuilt
- steno_cleanup.py 8 steps
- extract_config.py, run_pipeline.py created
- audio_resolve POC: 4/4 PASS
- Easley full run: 1,155 corrections, 51.7 min, 211 pages

---

## SCOTT'S OPERATING RULES (PM must internalize)

1. **Simple but no simpler.** Reliability > cleverness. 1969 Valiant, not a race car.
2. **Look before you dive.** Flag "pool has no water" before executing. One sentence, then proceed.
3. **FORK flag.** Hack vs right solution — surface it, let Scott decide. Log hacks as `[TECH DEBT]`.
4. **Mama Bear Rule.** Commit before every build. Both repos tracked. Codebase = baby.
5. **Buffet vs Pizza.** Scott unsure → show 2-3 options. Scott knows → execute, flag risks only.
6. **"Button it up" = full housekeeping.** Commit code, update bug table, update docs, report clean.

---

## HOW CODE CLAUDES COMMUNICATE BACK TO PM

When Code Claude finishes a task, it appends to CURRENT_SPRINT.md:

✅ TASK DONE — [summary]
Files changed: [list]
Ready for: [what's next]

🔴 BLOCKED — [what's blocking]
Need from Scott/PM: [specific question]

⚠️ FLAG — [unexpected finding]
Recommendation: [suggestion]

---
*Maintained by: Project Lead Claude + Scott*
*Last updated: 2026-04-17*
*Code Claudes: stay in CLAUDE.md and CURRENT_SPRINT.md*

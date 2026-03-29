# ═══════════════════════════════════════════════════════════════════
# PROJECT_BOARD.md — SCOTT + CLAUDE PROJECT LEAD
# Deposition Transformation Engine
# ═══════════════════════════════════════════════════════════════════
# THIS FILE IS FOR SCOTT + PROJECT LEAD CLAUDE ONLY.
# Code Claudes: read CLAUDE.md and CURRENT_SPRINT.md instead.
# ═══════════════════════════════════════════════════════════════════
# HOW TO USE:
#   Ping project lead Claude any time — session start, mid-day,
#   when something ships, when something breaks, or just to think.
#   Claude will update this board, maintain CLAUDE.md accuracy,
#   and rewrite CURRENT_SPRINT.md for the code Claudes.
# ═══════════════════════════════════════════════════════════════════

## PROJECT SNAPSHOT
**Project:**      Deposition Transformation Engine
**Root folder:**  `C:\Users\scott\OneDrive\Documents\CR_Depo_Transform`
**Job folder:**   `C:\Users\scott\OneDrive\Documents\ad_foreman_0324` (current active run)
**Version:**      v4.0 (state-agnostic core)
**Goal:**         90%+ automated depo cleanup, lawyer-ready output
**Benchmark:**    117 manual corrections on Easley depo (Yellow Rock v. Westlake)
**Current score:** 78% (L3-001, 2026-03-21) — target is 90%+
**Run cost:**     ~$2–4 per full Easley-length run
**Model:**        claude-sonnet-4-6

---

## 🔴 BLOCKERS — Nothing ships until these are resolved

| # | Blocker | Owner | Notes |
|---|---------|-------|-------|
| B-1 | KB-008 casing size notation unresolved | Scott | Style A vs Style B. Need Muir confirmation or Scott's call. Engine currently uses Style B as interim. |
| B-2 | KB-006 scoring dispute unresolved | Scott | Casing physics rule valid — but was it a planted test target in L3-001? SCORES_LOG may have answer. |

---

## 🟡 OPEN ITEMS — Decisions needed

| # | Item | Owner | Notes |
|---|------|-------|-------|
| OI-1 | KB numbering inconsistency | Scott + Claude | KB-001–011 use "KB-", 012–014 use "LA-KB-", 015 back to "KB-". Standardize? |
| OI-2 | NY WC engine config | Scott | ai_engine.py has LA modules commented out for NY WC but no NY WC version exists yet. Separate script or config flag? |
| OI-3 | SCORES_LOG location | Scott | Referenced in KB-009 as only valid performance measure. Where does it live — file, spreadsheet, notes? |
| OI-4 | format_final.py — does it exist? | Scott | Listed as Stage 4 of pipeline. Never uploaded. Built or still TODO? |
| OI-5 | extract_rtf.py — does it exist? | Scott | Stage 1. Same question. |
| OI-6 | steno_cleanup.py — does it exist? | Scott | Stage 2. Same question. |

---

## 🟢 CURRENT SPRINT
→ See **CURRENT_SPRINT.md** for full code Claude instructions.

**Sprint goal:** Close the gap from 78% → 90%+ on Easley benchmark
**Active tasks:** See CURRENT_SPRINT.md

---

## ✅ SHIPPED — What's done and locked

| Date | What shipped | Notes |
|------|-------------|-------|
| 2026-03-21 | MASTER_DEPOSITION_ENGINE_v4.md | State-agnostic rebuild. 13 layers. |
| 2026-03-21 | ai_engine.py v2.0 | Full chunked API pipeline, prompt caching, checkpoint/resume |
| 2026-03-21 | STATE_MODULE_louisiana_engineering.md | Louisiana engineering cases |
| 2026-03-21 | STATE_MODULE_nj_workers_comp.md | NJ workers comp |
| 2026-03-21 | HOUSE_STYLE_MODULE_muir.md | Marybeth Muir CCR RPR house style |
| 2026-03-22 | KB-010 (verbatim rule) | Learned from L1-001 audit — critical fix |
| 2026-03-22 | KB-011 (abrupt endings) | Learned from L1-001 audit |
| 2026-03-22 | LA-KB-012 (two-pass architecture) | Learned from PROD-RUN-001, Easley 191K chars |
| 2026-03-22 | LA-KB-013, LA-KB-014 | Steno artifact fixes now in steno_cleanup.py |
| 2026-03-23 | KB-015 (E-mail house style) | Muir confirmed spelling |
| 2026-03-29 | CLAUDE.md, PROJECT_BOARD.md, CURRENT_SPRINT.md | Project management system stood up |

---

## 📋 BACKLOG — Queued but not started

| Priority | Item | Notes |
|----------|------|-------|
| HIGH | HOUSE_STYLE_MODULE_dalotto.md | Alicia D'Alotto, NY WC reporter. Needed before NY WC production runs. |
| HIGH | STATE_MODULE_ny_wcb.md | NY Workers Comp Board rules. Paired with D'Alotto module. |
| HIGH | Benchmark run: get to 90%+ | Run ai_engine.py against Easley, score it, close the gap |
| MEDIUM | Auto-glossary builder | Build glossary.txt from first-run corrections automatically |
| MEDIUM | Billing/invoice output (FILE 9) | Add to FINAL_DELIVERY package |
| LOW | Audio timestamp cross-reference | Tie transcript lines to audio timestamps |
| LOW | Multi-witness deposition handling | Currently single-witness only |
| LOW | Web-based state module selector UI | Nice to have — not blocking anything |

---

## 🧠 DECISIONS LOG — What was decided and why

| Date | Decision | Rationale |
|------|----------|-----------|
| Pre-2026-03-29 | State-agnostic core (v4 rebuild) | Engine was too coupled to Louisiana. Now drop-in state modules. |
| Pre-2026-03-29 | GREGG + MARGIE excluded from API chunks | Too many tokens per chunk. Key rules captured in Layer 5, Layer 6, KB entries. Still used in co-work sessions. |
| Pre-2026-03-29 | claude-sonnet-4-6 not Opus | Cost vs quality tradeoff at $2–4/run |
| Pre-2026-03-29 | Chunk at paragraph boundaries | Preserves Q&A integrity — never split a Q/A pair |
| Pre-2026-03-29 | 100K char SIZE GATE | ~25K input tokens + 8 output files = hits 32K ceiling above 100K chars |
| 2026-03-22 | Two-pass mode | Hit token ceiling on 191K Easley depo. Pass 1 = read + notes. Pass 2 = write. |
| 2026-03-23 | E-mail not email | Muir house style confirmed in Cox depo (030626yellowrock-FINAL) |

---

## 📝 SESSION LOG — Running notes

**2026-03-29**
- Project management system created (PROJECT_BOARD, CLAUDE.md, CURRENT_SPRINT)
- 16 open items identified and catalogued
- KB-008 confirmed NOT Style B per Scott — answer still needed
- Project root established: `C:\Users\scott\OneDrive\Documents\CR_Depo_Transform`
- Architecture conversation started (job folders vs engine folder) — parked for now, not ready yet
- Next: work through open items list one by one

---
*Maintained by: Project Lead Claude + Scott*
*Code Claudes: stay in CLAUDE.md and CURRENT_SPRINT.md*

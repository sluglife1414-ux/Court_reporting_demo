# ═══════════════════════════════════════════════════════════════════
# CURRENT_SPRINT.md — INSTRUCTIONS FOR CODE CLAUDES
# Deposition Transformation Engine
# ═══════════════════════════════════════════════════════════════════
# Written by: Project Lead Claude
# For:        Code Claudes working in Claude Code
# Updated:    2026-03-30
# ═══════════════════════════════════════════════════════════════════
# BEFORE YOU TOUCH ANYTHING:
#   1. Read CLAUDE.md fully — technical ground truth.
#   2. Read this file fully — your exact tasks.
#   3. Do not invent scope. Do exactly what is written here.
#   4. When done with a task, say so clearly so Scott can log it.
# ═══════════════════════════════════════════════════════════════════

## SPRINT GOAL

Three parallel tracks:
1. **Leon folder setup** — copy engine to alicia_demo/, configure for CA WCAB
2. **verify_agent.py first run** — run on Fourman WCB, report results
3. **build_review_sheet.py** — CR listening queue, replaces QA_FLAGS.txt

---

## WHERE THINGS STAND (read before starting)

**Active engine:** `C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4\`
**GitHub:** https://github.com/sluglife1414-ux/Court_reporting_demo (PRIVATE, branch: court_reporting)
**Last cold run:** Fourman WCB (M.D.) — 27 pages vs AD's 28. All format bugs fixed. ✅

**The pipeline (run in order via run_pipeline.py):**
```
extract_rtf.py      → raw_text.txt
steno_cleanup.py    → cleaned_text.txt
ai_engine.py        → corrected_text.txt  (Claude API, ~56 min, checkpoints every chunk)
extract_config.py   → depo_config.json    (auto-extracts 19 case metadata fields)
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

**3-pass architecture (current design):**
```
Pass 1 — ai_engine.py         → corrected_text.txt + correction_log.json
Pass 2 — verify_agent.py      → second-opinion on HIGH confidence items [BUILT, NOT RUN]
Pass 3 — audio_agent.py       → Whisper API on REVIEW gaps [DESIGNED, NOT BUILT]
```

**Style module rule:** Each CR has their own HOUSE_STYLE_MODULE. NEVER cross-load.
muir.md = MB (LA civil). dalotto.md = AD (NY WC). They are different CRs in different states.

---

## ⚠️ OPEN ITEMS THAT AFFECT YOUR WORK

Do not resolve these without Scott's input — flag and wait:

- **AD_QUESTIONS.md** has 6 open items for Alicia D'Alotto. Do not finalize NY WC format
  until those are answered.
- **No STATE_MODULE_california_wcab.md exists.** Leon (alicia_demo/) is CA WCAB.
  You will need to create a stub — flag to Scott before going live on that run.
- **verify_agent.py has never been run.** Fourman is the baseline. Run it, report results,
  do NOT make judgment calls about what the agent gets wrong — report only.

---

## ACTIVE TASKS

### TASK 1 — Leon folder setup
**Status:** READY
**Folder:** `C:\Users\scott\OneDrive\Documents\alicia_demo\`
**RTF:** `0313Leon2026_T.rtf` (CaseCATalyst, March 13, California WCAB)
**Audio:** `-7849480339599919352.mp3` (iPhone Voice Memo, 13m 53s) — audio agent test PENDING

Steps:
1. Confirm the alicia_demo/ folder exists and RTF is there
2. Copy the pipeline scripts from mb_demo_engine_v4/ into alicia_demo/
   (or confirm run_pipeline.py can point at the folder — check first)
3. Create a stub `depo_config.json` for Leon — flag all fields you can't auto-detect
4. Create a stub `STATE_MODULE_california_wcab.md` — mark it DRAFT, flag to Scott
5. Do NOT run the AI pass yet — report ready state and wait

---

### TASK 2 — Run verify_agent.py on Fourman
**Status:** READY
**Folder:** `C:\Users\scott\OneDrive\Documents\ad_foreman_0324\`
**Script:** `verify_agent.py` (also in mb_demo_engine_v4/ as specialist_verify.py)
**Input:** correction_log.json from the Fourman run (122 corrections: 62 HIGH / 42 MED / 18 LOW)

Steps:
1. Confirm verify_agent.py exists in ad_foreman_0324/ (or copy from mb_demo_engine_v4/)
2. Run it against the Fourman correction_log.json
3. Report:
   - How many HIGH items did it agree with / flag / overturn?
   - Any new catches the AI pass missed?
   - Any false positives (things the agent called wrong that are actually right)?
4. Do NOT auto-apply changes — report only. Scott decides what to accept.

---

### TASK 3 — Build build_review_sheet.py
**Status:** READY TO DESIGN
**Purpose:** Replace QA_FLAGS.txt with a structured CR listening queue
**Output format (per gap):**
```
Page [X], Line [Y]
Context: "[5 words before] >>> [REVIEW WORD] <<< [5 words after]"
Audio timestamp: [MM:SS] (if audio file present in folder)
Action needed: [LISTEN / CONFIRM NAME / SUPPLY]
```

Steps:
1. Read QA_FLAGS.txt from the Fourman FINAL_DELIVERY/ to understand current format
2. Read format_final.py — find where [REVIEW] tags are generated and stripped
3. Design build_review_sheet.py to:
   - Read corrected_text.txt and find all [REVIEW] tags
   - Map each tag to page/line using line_map.json (if it exists) or derive from format
   - Extract 5-word context window around each tag
   - If an audio file exists in the folder, calculate approximate timestamp
     (timestamp = audio_length * (review_line / total_lines))
   - Output REVIEW_SHEET.txt in FINAL_DELIVERY/
4. Add build_review_sheet.py as a step in run_pipeline.py (after build_deliverables.py)
5. FORK: if timestamp calculation is complex, flag it — Scott may want to defer

---

## DONE THIS SPRINT

| Task | Completed | Notes |
|------|-----------|-------|
| PROJECT_BOARD.md updated | 2026-03-30 | Full state captured — PM bot now current |
| CURRENT_SPRINT.md updated | 2026-03-30 | Replaced stale 78%→90% sprint with current tasks |

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
*Last updated: 2026-03-30*
*Next update: when Scott pings with new progress or decisions*

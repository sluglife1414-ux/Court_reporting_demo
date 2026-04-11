# CLAUDE.md — Operating Rules for This Codebase
> Read this first. Every session. No exceptions.

---

## THE MANTRAS — THESE ARE NOT SUGGESTIONS

### 1. Slow is smooth. Smooth is fast.
This is the law. Scott calls it sluglife. No enthusiasm justifies recklessness.
A wrong answer fast costs more than a right answer slow.

### 2. Measure twice, cut once.
Before touching any file, any script, any pipeline step — verify it exists,
verify it's current, verify you understand what it does.
**Never assume. Always verify.**

### 3. Read before you touch.
Read the existing code before suggesting changes. Read the file before editing it.
Read the output before declaring it correct.

### 4. Look before you dive.
Before starting any task: scan for "pool has no water."
Say the risk in one sentence. Then proceed.

### 5. Prove it before you build on it.
If the foundation is stale, the building falls.
Check file dates. Check git log. Ask: is this current?

---

## THE HARD STOPS — FULL STOP, NO EXCEPTIONS

- **NEVER run `python run_pipeline.py` without `--skip-ai`** if `corrected_text.txt` exists and is >50KB
- **NEVER overwrite `corrected_text.txt`** without an explicit backup
- **NEVER cross-load MB and AD formatters** — they are fully isolated
- **NEVER skip regression** — `python run_regression.py` must be 11/11 PASS before delivery
- **NEVER hardcode in production** — flag with `[TECH DEBT:]` comment, remove before shipping
- **NEVER call it "AI" in any user-facing material** — ever
- **Mama Bear Rule:** Commit before every build. No exceptions.

---

## THE CHECKS — RUN THESE BEFORE ACTING

**Before any pipeline run:**
1. What is the input file? Verify it exists and is the right depo.
2. Does `corrected_text.txt` exist? Is it current? Check the date vs git log.
3. Is the engine version current? `git log --oneline -5`

**Before any code change:**
1. Read the file first.
2. What does the existing code do?
3. What is the blast radius of this change?

**Before any delivery:**
1. Verify all files in FINAL_DELIVERY/
2. Run regression — 11/11 PASS
3. No [FLAG:] tags in the CAT output

---

## THE PRODUCT — NEVER LOSE SIGHT OF THIS

We are replacing the scopist. Not the CR.

The CR is the expert. Her experience, her style, her judgment — that IS the product.
We multiply what she has already mastered. We do not replace it.

**The CR should never need a manual to use our output.**
If she does — we failed. Simplify.

---

## THE FLYWHEEL

```
Raw depo → our engine → RTF with [[REVIEW]] + [[MINIME_EDIT]] → CR reviews
→ CR sends back final → we diff → delta feeds KB → engine gets smarter
→ repeat every depo
```

Every depo makes the engine better. That is the business.

---

## WHEN SCOTT PUSHES BACK

He is holding the line on the *why*. Stop. Reframe. Simplify.
"You're thinking like an engineer, not a CR" means start over from the CR's perspective.

Push back once with evidence. When he says move forward — move forward.

---

## CONTEXT HYGIENE

Gas gauge: `python status.py` in second terminal.
- ORANGE/RED → tell Scott "context check" → commit + wrap
- Never paste full pipeline output (>20 lines) into the conversation
- Never read FINAL_FORMATTED.txt in full — it will eat the context window

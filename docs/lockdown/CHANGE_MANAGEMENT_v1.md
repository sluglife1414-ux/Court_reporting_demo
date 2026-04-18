# MyReporterX Change Management Playbook v1

**Status:** DRAFT v1 — Phase B of 2026-04-19 Lockdown
**Author:** Scott (founder, PM)
**Purpose:** One source of truth for how code moves through this project.
**Companion doc:** `docs/lockdown/2026-04-19_repo_state_baseline.md`
**Target location in repo:** `docs/lockdown/CHANGE_MANAGEMENT_v1.md`

---

## WHY THIS DOC EXISTS

On 2026-04-19 we caught a session drift that could have destroyed real work. The root cause was not bad code. It was **passive verification** — assuming the repo was in a certain state instead of confirming it.

This playbook exists so that never happens again.

The governing principle, in Scott's own words:

> **RULE-BINARY-VERIFY** — "On code there is no upside to 'I think so.' It must be binary yes or no. Panic, although not recommended, is better than lazy and passive."

Everything below is an application of that rule.

---

## PART 1 — RULE-BINARY-VERIFY (THE PRIME RULE)

### What it means

Every claim about the state of the codebase must be answered with **YES** or **NO**, backed by a command output you can see with your own eyes.

Not allowed:
- "I think we're on master."
- "It should be clean."
- "Pretty sure that was committed."
- "Probably pushed."

Always allowed:
- "YES — `git branch --show-current` returned `master`."
- "NO — `git status` shows 3 modified files."

### When it applies

- Before starting a session
- Before starting a sprint
- Before merging a branch
- Before deleting anything
- Before closing a session
- Any time a Claude Code bot says "done" — verify it

### The verification commands (memorize these four)

```
git branch --show-current       → which branch am I on?
git log -1 --oneline             → what is the last commit?
git status                       → is the tree clean?
git remote -v                    → where is origin pointing?
```

If you cannot answer all four with certainty, **stop and run them.**

---

## PART 2 — BRANCH RULES

### The branches that exist

| Branch | Purpose | Who writes to it |
|---|---|---|
| `master` | The real source of truth. Production-ready code only. | Scott merges. Nobody else. |
| `claude/<work-name>` | Short-lived Claude Code working branches. | Claude Code bots. |
| `archive/<date>_<name>` | Frozen snapshots of abandoned or paused work. | Scott, when archiving. |

### Naming rules

- Working branches: `claude/<descriptive-kebab-case>`
  - Good: `claude/audio-verify-pipeline`, `claude/nj-wc-module-fix`
  - Bad: `claude/goofy-hodgkin` (auto-generated gibberish — do not use)
- Archive branches: `archive/YYYY-MM-DD_<descriptive-name>`
  - Good: `archive/2026-04-18_tollgate-experiment`

### The merge rule (BINARY)

A branch merges to master only after **all four** are YES:

1. ✅ Does the code work? (tests pass or manual verify done)
2. ✅ Has Scott reviewed the diff?
3. ✅ Has Scott said "merge it"?
4. ✅ Is the working tree clean before merge?

If any answer is NO — do not merge.

### The deletion rule (BINARY)

A branch is deleted only after:

1. ✅ Is it a pure ancestor of master, OR has it been archived?
2. ✅ Has Scott said "delete it"?

If any answer is NO — do not delete.

### The stale branch rule

Any working branch inactive for more than 7 days gets flagged for review. Options: archive, merge, or delete.

---

## PART 3 — COMMIT RULES

### Message format

```
<type>: <short summary in 50 chars or less>

<optional longer explanation, wrapped at 72 chars>

<optional footer: references to tickets, sprint, related files>
```

### Types (use exactly these)

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `refactor:` — code change that neither adds a feature nor fixes a bug
- `test:` — adding or fixing tests
- `chore:` — maintenance, cleanup, dependency updates
- `lockdown:` — special tag for 2026-04-19 lockdown work

### Examples

Good:
```
lockdown: add change management playbook v1

First draft of CHANGE_MANAGEMENT_v1.md covering RULE-BINARY-VERIFY,
branch rules, commit rules, and session rules.

Related: docs/lockdown/2026-04-19_repo_state_baseline.md
```

Bad:
```
updates
```

### Commit size rule

**One logical change per commit.** If you find yourself writing "and also" in a commit message, split the commit.

### When to push

Push to origin at these moments:
- End of a working session
- Before switching machines
- Before asking for review
- After any merge to master

Do NOT push:
- Half-finished work with broken tests, unless to a clearly named WIP branch
- Secrets, API keys, `.env` files, credentials of any kind

---

## PART 4 — SESSION RULES

### Session-Start Check (MANDATORY)

Every Claude session — Chat or Code — starts with these four commands. No exceptions.

**CMD (your Windows laptop) OR VPS Terminal:**
```
git branch --show-current
git log -1 --oneline
git status
git remote -v
```

Answer these four binary questions:

1. ✅ / ❌ — Am I on the branch I expect?
2. ✅ / ❌ — Is the last commit the one I expect?
3. ✅ / ❌ — Is the working tree clean (or is the dirty state expected)?
4. ✅ / ❌ — Is origin pointing where I expect?

If all four are YES — proceed.
If any is NO — stop and investigate before touching code.

### Session-End Check (MANDATORY)

Every session ends with:

1. Run `git status` — is everything committed or intentionally left dirty?
2. Run `git log -5 --oneline` — what did this session produce?
3. Run `git push` if appropriate (see commit rules above).
4. Write a one-paragraph handoff note (see format below).

### Handoff Note Format

At the end of every session, write this into the chat so the next session can pick up:

```
=== SESSION HANDOFF — YYYY-MM-DD ===
Branch: <name>
Last commit: <short hash> <message>
Tree state: clean / dirty (explain)
What was accomplished: <bullets>
What is in progress: <bullets>
What is blocked: <bullets>
Next step: <one concrete action>
```

This is the same format Scott uses to start new sessions. The loop closes.

### The Coach K Rule

If Scott raises his hand — everything stops. No "let me just finish this." Hand up = full stop. Reassess, then continue or change direction.

---

## PART 5 — CLAUDE CODE BOT RULES

### Before a Claude Code bot writes any code

1. It must read `CODER_MINDSET_v1.md` and confirm.
2. It must run the Session-Start Check.
3. It must state in plain English what it is about to do.
4. It must wait for Scott's "go."

### While a Claude Code bot is working

1. One-to-two steps at a time. No sprints without permission.
2. No hardcoding in production. Ever.
3. Three-Brains Check before any change: can we build it / should we build it / is it worth building?
4. Deposition Engine Prime Directive: before any change, ask whether it could reduce transcript accuracy or credibility. Stop if yes or maybe.

### When a Claude Code bot says "done"

Scott applies RULE-BINARY-VERIFY. "Done" is not a claim — it is a testable state.

---

## PART 6 — EMERGENCY PROCEDURES

### If a session goes sideways

1. Hand up. Coach K rule.
2. Do not delete anything.
3. Do not force-push anything.
4. Run the four verification commands.
5. Capture output into the chat.
6. Re-baseline from there.

### If master looks wrong

1. Do NOT push anything to origin.
2. Verify locally with `git log --oneline -20`.
3. Compare against the baseline doc.
4. If divergent — archive the suspect branch, reset only after verified.

### If a branch is accidentally deleted

1. `git reflog` — the commit is probably still recoverable.
2. Check `.claude/worktrees/` for lingering state.
3. Do not panic-commit. Verify before restoring.

---

## PART 7 — REVIEW CADENCE

This doc is v1. It will be wrong in some places. That is expected.

- **Weekly:** 5-minute review. Is anything here being ignored? Is anything missing?
- **Monthly:** Formal revision. Bump version if changed (v1 → v2).
- **After any incident:** Immediate review. What rule failed? Add or tighten.

---

## SIGN-OFF

This playbook is active as of the date it is committed to master.

All prior rules, habits, and informal agreements are superseded by this document.

When in doubt — RULE-BINARY-VERIFY.

---

*End of CHANGE_MANAGEMENT_v1.md*

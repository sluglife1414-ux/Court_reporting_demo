# DEF-015-EXPANDED: Inline Q/A Bleed Backstop
## Spec v1.0 — 2026-04-18
**File:** `docs/specs/2026-04-18_def015_expanded_backstop_spec.md`
**Status:** DRAFT — awaiting Scott approval before implementation
**Sprint:** DEF-015-EXPANDED
**Author:** Claude Code (Sonnet 4.6), session 2026-04-18

---

## Background

Recon Passes 1–5 confirmed that the §5.2 DENSE INLINE BLOCKS rule in `MASTER_DEPOSITION_ENGINE_v4.2.md` is failing pervasively. The rule is prompt-only — the AI is instructed to break inline blocks, but there is no code backstop to catch failures. Full Brandl run (305 pages) produced **440 bleed lines** where a speaker turn ends and the next begins on the same formatted line instead of a separate block. The original acceptance test (DEF-015 narrow) only caught 18 of these because its regex required a block-start line with two labels and ≥20 chars between them.

**This sprint builds the code backstop.** The prompt rule (§5.2) stays as-is. We are not tuning the prompt. We are adding a deterministic post-AI layer that catches what the AI misses.

---

## 1. Pipeline Placement

### Current pipeline (relevant stages)

```
cleaned_text.txt
    ↓
[ai_engine.py]          ← AI applies §5.2 (prompt-only, fails ~440x per 354-page depo)
    ↓
corrected_text.txt
    ↓
[verify agents]         ← specialist verify, apply_verify
    ↓
[format_final.py]       ← formats to page/line layout → FINAL_FORMATTED.txt
    ↓
[build steps]           ← PDF, transcript, condensed, summary
```

### Where the backstop lives: between ai_engine.py and format_final.py

**New pipeline:**

```
cleaned_text.txt
    ↓
[ai_engine.py]
    ↓
corrected_text.txt
    ↓
[verify agents]
    ↓
[def015_backstop.py]    ← NEW: detect + fix inline bleed on corrected_text.txt
    ↓
corrected_text.txt      ← overwritten in place (with Proof of Work log)
    ↓
[format_final.py]
    ↓
FINAL_FORMATTED.txt
```

**Why before format_final, not after:**

1. `corrected_text.txt` is line-structured steno output — each block is a paragraph, blank-line separated. The bleed exists at the paragraph level here: a single paragraph contains multiple speaker turns. This is the cleanest place to detect and split.
2. `FINAL_FORMATTED.txt` wraps lines to 64-char columns with page/line numbers. Splitting turns there requires re-pagination — fragile and out of scope.
3. If we fix in `corrected_text.txt`, `format_final.py` gets clean single-turn paragraphs and produces correct output with zero bleed.
4. The verify agents run before this step — they may have already flagged some content for REVIEW. The backstop must preserve those flags and not disrupt verified content.

**New run_pipeline.py step:**

```python
('def015_backstop.py', 'backstop', 'DEF-015 bleed backstop → corrected_text.txt')
```

Inserted after `apply_verify` step, before `format_final`. Can be skipped with `--skip-backstop` flag for debugging.

---

## 2. Detector Logic

### 2.1 Input

Reads `corrected_text.txt` — the post-AI, post-verify corrected transcript. Paragraphs are separated by blank lines. Each paragraph is a single speaker block (Q. or A. labeled, or unlabeled colloquy/structural content).

### 2.2 Detection Approach

Split the file into paragraphs on blank lines. For each paragraph, scan for mid-paragraph Q./A. label occurrences that are NOT the opening label of that paragraph.

A **mid-paragraph label** is:
- A `Q.` or `A.` token
- Preceded by at least 6 characters of content
- Followed by 1–6 spaces and an uppercase letter (indicating start of turn content, not an abbreviation)
- NOT preceded by a newline within the paragraph (it's inline, not on its own line)

### 2.3 Primary Regex

```
MID_LABEL = re.compile(
    r'(?<=[^\n]{6,})'    # at least 6 chars of content before it on the same line
    r'[QA]\.'            # Q. or A. label
    r'\s{1,6}'           # 1-6 spaces (tab or spaces)
    r'[A-Z]'             # uppercase letter starting the turn content
)
```

Applied per-paragraph (not per-line), on the paragraph as a single string with internal newlines stripped. This catches both block-start bleed (where the opening line of the paragraph contains two labels) and continuation-line bleed (where a wrapped line mid-paragraph has a label starting a new turn).

### 2.4 False Positive Guards

Applied in order before any hit is processed. If any guard matches, skip this occurrence:

| Guard | Pattern | Example |
|---|---|---|
| Exhibit reference | `Exhibit\s+[QA]\.` | "Exhibit A." |
| Section reference | `Section\s+[QA]\.` | "Section Q." |
| Named exhibit | `\b[A-Z][a-z]+\s+[QA]\.` | "Paragraph A." |
| Q.E.D. | `Q\.E\.D` | "Q.E.D." |
| Capitalized abbreviation run | `[A-Z]\.\s*[QA]\.` preceded by another single capital | "J. Q. Adams" — capital initial followed by Q. |
| Quote artifact | mid-label appears inside quotation marks `"..."` or `'...'` | "he said 'Q. what is your name'" |
| Short isolated token | the `[QA].` is preceded AND followed by punctuation with < 3 chars of content | e.g., "per Q." at end of sentence |

**Conservative rule:** If a guard fires and the occurrence is ambiguous, classify as UNCERTAIN (tag for review) rather than auto-fix.

### 2.5 Classification: Mode A vs Mode B

After a mid-label occurrence passes the guards:

**Mode A** (run-on blob fragment) — content before the mid-label is ≥ 40 chars:
- The paragraph is a long run-on block where the AI labeled turns but failed to break them
- Multiple sentences of content before the stray label
- Example: `"A.   That 's the same thing. Q. Okay. So I have just restated that differently. Q. Okay."`

**Mode B** (short interjection) — content before the mid-label is < 40 chars:
- The opening answer is a brief utterance — yes, no, correct, uh-huh, a number, a name
- Immediately followed by the next question with little or no sentence-ending punctuation
- Example: `"A.   Uh-huh. Q. Describe their period of ownership"`
- Example: `"A.   Greenspoint. Q. Okay. Did your office"`

**Uncertain** — either mode where:
- No sentence-ending punctuation (`.`, `?`, `!`) immediately before the stray label
- The content before the stray label is ambiguous (could be a sentence fragment, a name, an abbreviation)
- The guard heuristics fire but don't definitively rule it out

### 2.6 Detector Output

A list of `BleedHit` objects, one per detected mid-label occurrence:

```
BleedHit:
  paragraph_index: int           # 0-based index into paragraph list
  char_offset: int               # char position of the stray label within paragraph
  stray_label: str               # 'Q' or 'A'
  mode: str                      # 'A', 'B', or 'UNCERTAIN'
  prefix_text: str               # content before the stray label (for PoW)
  suffix_text: str               # content starting at the stray label (for PoW)
  confidence: str                # 'HIGH', 'MEDIUM', 'LOW'
```

---

## 3. Mode A Auto-Fixer (run-on blob fragments)

### 3.1 Trigger Condition

`mode == 'A'` AND `confidence != 'LOW'`.

Low-confidence Mode A hits → demote to UNCERTAIN and tag (see §5).

### 3.2 Split Logic

**Step 1 — Find the split point:**
The split point is the char position of the stray label (`BleedHit.char_offset`). Everything before it stays in the current paragraph. Everything from the stray label onward becomes a new paragraph.

**Step 2 — Clean the split point:**
- Strip trailing whitespace from the end of the first fragment
- If the first fragment ends mid-sentence (no `.`, `?`, `!` in last 15 chars), flag as LOW confidence → demote to UNCERTAIN
- If first fragment ends with a sentence terminator, proceed

**Step 3 — Assign labels to the new paragraph:**
The stray label (`Q.` or `A.`) becomes the opening label of the new paragraph. This is already present — no re-labeling needed in most cases.

**Step 4 — Check for chained bleeds:**
After splitting, run the detector again on both new paragraphs. If either still contains a stray label, apply the fixer recursively (max depth: 5 iterations to prevent infinite loops). If max depth reached → demote remaining hits to UNCERTAIN.

**Step 5 — Reconstruct paragraph:**
```
[original paragraph up to split point, trimmed]
\n\n
[new paragraph from stray label onward]
```

### 3.3 Re-labeling Logic

The stray label inherits the label from the mid-paragraph occurrence. No inference needed — the AI already labeled it. The fixer is purely splitting, not re-labeling.

**Exception:** If the detected label conflicts with strict Q/A alternation (e.g., two consecutive Q. blocks with no A. between), do NOT auto-fix — demote to UNCERTAIN and tag.

### 3.4 Formatting After Split

The new paragraph follows the same formatting convention as other paragraphs in `corrected_text.txt`:
- Opening label on first line: `Q.   [content]` or `A.   [content]`
- Continuation lines: indented 5 spaces (matching existing format)
- Blank line before and after (paragraph separator)

### 3.5 Failure Mode: Demote to UNCERTAIN

Auto-fixer demotes to UNCERTAIN (tag for review) when:
- No sentence-ending punctuation before the split point
- First fragment < 10 chars after label (nearly empty turn)
- Chaining depth > 5
- Label conflicts with strict alternation
- Any guard was borderline (fired partially)

---

## 4. Mode B Classifier

### 4.1 Safe-to-Auto-Fix Mode B

A Mode B hit is **safe to auto-fix** when ALL of the following hold:

1. The content before the stray label ends with a clear sentence terminator (`.`, `?`, `!`) optionally followed by whitespace
2. The content before the stray label is a recognizable short utterance pattern:
   - Affirmatives: `Yes.`, `Correct.`, `Right.`, `True.`, `Exactly.`
   - Negatives: `No.`, `Incorrect.`, `Wrong.`
   - Acknowledgments: `Okay.`, `Sure.`, `Understood.`, `Fine.`, `Agreed.`
   - Hedge: `I don't know.`, `I'm not sure.`, `Maybe.`
   - Interjections: `Uh-huh.`, `Mm-hmm.`, `Yeah.`
   - Short factual: a proper name, a number, a year, a city name — followed by `.`
3. The stray label (`Q.` or `A.`) is followed by ≥ 5 chars of turn content (not just trailing whitespace)

**Examples of safe Mode B:**
- `A.   Greenspoint. Q. Okay. Did your office` → split after "Greenspoint."
- `A.   Yes. Q. Okay. The way I look at it` → split after "Yes."
- `A.   Correct. Q. For example, a well that` → split after "Correct."

### 4.2 Uncertain Mode B

A Mode B hit is **uncertain** when ANY of the following:

1. No sentence terminator before the stray label
   - Example: `A.   Uh-huh Q. Describe their period` (no period after "Uh-huh")
2. The content before the label could be a fragment rather than a complete utterance
   - Example: `A.   Year-and-a-half, till 2006. Q. Okay.` — "Year-and-a-half, till 2006." is a complete answer, but the comma after "Year-and-a-half" makes it slightly ambiguous
3. The utterance before the label is an incomplete sentence (contains a conjunction or preposition at the end: "and", "but", "from", "in", "the")
   - Example: `uh-huh describe their period of ownership from` — "from" at end signals fragment
4. The label `A.` follows content that could itself be a question (contains `?`) — ambiguous speaker assignment
5. The content is fewer than 3 words AND has no terminator

**Uncertain Mode B → tag for review** (see §5). Do not auto-fix.

### 4.3 Edge Cases — Decisions Locked (2026-04-18)

**Edge case 1 — Chained rapid exchanges (3+ turns on one line):**

`A. Yes. Q. And? A. No. Q. Okay.` — **Always tag. Never auto-split chains.**

When the detector finds 3 or more speaker label occurrences within a single paragraph (including the opening label), classify the entire paragraph as UNCERTAIN regardless of Mode A/B. Insert a single `[REVIEW-NNN: possible turn break]` tag at the first stray label position. Do not attempt recursive splitting on chained paragraphs. Rationale: chain-splitting requires correctly assigning every intermediate turn; one misassignment corrupts the legal record across multiple lines.

**Edge case 2 — Interrupted questions (Q. fragment — A. answer):**

`Q. And did you — A. Yes.` — **Auto-split ONLY when an em-dash (—) or double-hyphen (--) immediately precedes the stray speaker label.**

Trigger condition: `(—|--)\s*[QA]\.\s+[A-Z]` — the dash is the explicit structural marker that the interruption is intentional. Without the dash, treat as UNCERTAIN and tag. With the dash: split at the dash, include the dash at the end of the first fragment (it's part of the transcript record), begin the new paragraph at the stray label.

**Edge case 3 — Witness self-correction (HARD GUARD — NEVER split here):**

`A. It was 2004 — no, 2005. Q. Are you sure?`

This is a legal record accuracy issue. A self-correction inside an A. block is part of the witness's answer. Splitting it would manufacture a false speaker turn in a court transcript — a Prime Directive violation.

**Hard guard: if the detector sees a dash (— or --) followed by any self-correction token within an A. block, the entire paragraph is EXEMPT from auto-fix and from tagging.**

Self-correction token list (case-insensitive, must appear within 6 words after the dash):
```
no, wait, actually, scratch that, strike that, correction, I mean, I meant,
let me rephrase, I misspoke, withdraw, retract, I should say, rather
```

Detection pattern:
```python
SELF_CORRECTION_RE = re.compile(
    r'(—|--)\s*'
    r'(?:no,?|wait,?|actually,?|scratch\s+that|strike\s+that|correction,?'
    r'|i\s+mean|i\s+meant|let\s+me\s+rephrase|i\s+misspoke|withdraw|retract'
    r'|i\s+should\s+say|rather)',
    re.IGNORECASE
)
```

If `SELF_CORRECTION_RE` matches anywhere in a paragraph before a stray label:
- Do NOT split
- Do NOT tag
- Log to PoW as `action: "exempt_self_correction"`
- Move on

This guard runs BEFORE Mode A/B classification, BEFORE all other guards.

**Edge cases 4–5 (unchanged from draft):**

4. **Colloquy interjection** — `A. That is correct. MR. MADIGAN: Objection. Q. You may answer.` — not a Q/A bleed, it's a correct objection sequence. Guard must catch this before DEF-015 fires. Detection: if the content between two Q/A labels contains `MR.\s+[A-Z]+:` or `MS.\s+[A-Z]+:`, classify as UNCERTAIN and tag rather than auto-split.
5. **Numbers that look like labels** — `...the answer is 42. A. I agree.` — "A." here IS a real label, safe to split. But `...question A. in Exhibit 3` — the "A." is NOT a label. Guard must distinguish. The exhibit guard in §2.4 handles this.

---

## 5. Inline Review Tag System

### 5.1 Tag Format

```
[REVIEW-NNN: possible turn break]
```

- `NNN` = zero-padded sequential integer, unique per document, starting at `001`
- Exact string: no variant punctuation, no trailing space inside brackets
- Total format is consistent and Ctrl+F friendly

### 5.2 Placement

Tag is placed **at the exact character position of the suspected break point** — immediately before the stray label, inline in the text:

**Before:**
```
A.   Uh-huh Q. Describe their period of ownership from
```

**After:**
```
A.   Uh-huh [REVIEW-001: possible turn break] Q. Describe their period of ownership from
```

The tag sits between the end of the first turn's content and the start of the stray label. One space before the tag, one space after (to allow clean deletion).

### 5.3 Clean Deletion Rule

When the CR removes the tag (Ctrl+F, delete), the result is:

```
A.   Uh-huh Q. Describe their period of ownership from
```

Which is the original text, unmodified. The CR then manually decides whether to break the line. No orphaned whitespace (single space before and after is the same as the space that would separate words).

If the CR wants to accept the implied break instead:
1. Delete the tag
2. Press Enter before `Q.`

That's a 2-keystroke workflow. No manual reformatting needed beyond that.

### 5.4 Tag Uniqueness

Tag IDs (`NNN`) are:
- Sequential within a single document run
- Reset to `001` for every new document
- Never reused within a document even if an earlier tag is resolved
- Logged to Proof of Work with full context

### 5.5 Tag Registry (in Proof of Work)

Each tag gets a Proof of Work entry (see §6). The registry is a list of all tag IDs for that document so a search-and-replace tool can find and remove all tags in one pass at end-of-review.

---

## 6. Proof of Work Integration

### 6.1 Output File

The backstop writes to `PROOF_OF_WORK_BACKSTOP.json` in the job's `FINAL_DELIVERY/` directory. This is separate from the existing `PROOF_OF_WORK.txt` (which is human-readable and written by the AI pass).

**Why separate:** The backstop PoW must be machine-readable for the future per-CR learning loop. Mixing it into the human-readable PoW would require parsing. Separate file = clean interface.

### 6.2 Schema

```json
{
  "document": "Brandl_YellowRock",
  "run_date": "2026-04-18",
  "engine_version": "v4.2",
  "backstop_version": "1.0",
  "summary": {
    "total_hits_detected": 440,
    "auto_fixed_mode_a": 0,
    "auto_fixed_mode_b": 0,
    "tagged_uncertain": 0,
    "false_positive_guards_fired": 0
  },
  "fixes": [
    {
      "fix_id": "FIX-001",
      "mode": "B",
      "confidence": "HIGH",
      "action": "auto_fix",
      "paragraph_index": 47,
      "input_text": "A.   Greenspoint. Q. Okay. Did your office ever have occasion...",
      "output_paragraph_1": "A.   Greenspoint.",
      "output_paragraph_2": "Q.   Okay. Did your office ever have occasion...",
      "split_reason": "Mode B safe: 'Greenspoint.' ends with period, recognized short-factual pattern",
      "alternation_check": "PASS"
    }
  ],
  "tags": [
    {
      "tag_id": "REVIEW-001",
      "mode": "B",
      "confidence": "LOW",
      "action": "tagged",
      "paragraph_index": 112,
      "input_text": "A.   Uh-huh Q. Describe their period of ownership from",
      "tag_reason": "Mode B uncertain: no terminator after 'Uh-huh', content before label is ambiguous",
      "stray_label": "Q",
      "prefix_chars": 12
    }
  ]
}
```

### 6.3 Machine-Readable Design Constraints

- All string values are UTF-8 clean (no control chars)
- `input_text` is always the full paragraph text before any fix, verbatim
- `output_paragraph_1` and `output_paragraph_2` are the exact strings written to `corrected_text.txt`
- `tag_reason` is a structured string: `"Mode [A/B] uncertain: [specific reason]"` — parseable by regex
- No free-text fields that require NLP to interpret
- Schema version field included for future compatibility

### 6.4 Do NOT Build the Learning System

The PoW schema above is designed so that a future per-CR learning script can ingest it without rework. The script is not being built in this sprint. No hooks, no callbacks, no training loops. Just log the data in the right format.

---

## 7. Test Plan

### 7.1 Primary Acceptance Test: Brandl goes from 440 → ~0 wide hits + N tagged

Run the wide detector on the backstop output (`corrected_text.txt` after backstop, before format_final):

**Target:**
- Wide-detector hits on backstop output: `≤ tagged_count` (i.e., every remaining hit has a `[REVIEW-NNN]` tag in it)
- Auto-fixed hits: none remain in output (confirmed by wide detector returning 0 untagged hits)
- Tagged uncertain hits: all have `[REVIEW-NNN]` present at the exact location

**Verification script:** `python acceptance_test.py --wide --input corrected_text.txt`

Proposed new acceptance check entry:
```python
('DEF-015-WIDE', 'Untagged inline Q/A bleed (wide detector)', wide_detector_regex, 0)
```
Where `wide_detector_regex` is the formalized version from §2.3 that EXCLUDES lines already containing `[REVIEW-NNN]` tags.

### 7.2 No False Positives

Manual spot-check of 20 random paragraphs from the auto-fixed set. Verify:
- Each split paragraph makes sense as a standalone speaker turn
- No legitimate sentence was broken mid-thought
- No colloquy interjection was misidentified as a bleed

CR review (MB) of all tagged items before final delivery — this is the human-in-the-loop backstop for uncertain cases.

### 7.3 Proof of Work Completeness

Verify that `PROOF_OF_WORK_BACKSTOP.json`:
- `summary.auto_fixed_mode_a + summary.auto_fixed_mode_b + summary.tagged_uncertain == summary.total_hits_detected`
- Every `fix_id` in `fixes[]` has a corresponding paragraph in the output that is now clean
- Every `tag_id` in `tags[]` has a corresponding `[REVIEW-NNN]` in the output
- No duplicate tag IDs

### 7.4 Regression: All currently-passing checks still PASS

Run `python acceptance_test.py` on the final `FINAL_FORMATTED.txt` output (after backstop + format_final).

Current passing checks: DEF-011, DEF-004a/b, DEF-012a/b, DEF-013a/b, DEF-005a/b, DEF-009a/b, DEF-014, DEF-016, DEF-017, DEF-018 — all must remain PASS.

DEF-015 narrow: must drop from 18 → 0. (If tagged items appear in FINAL_FORMATTED with their tags, the narrow detector should not fire on them since `[REVIEW-NNN]` breaks the `[QA]\.\s{1,6}[A-Z].{20,}` pattern.)

---

## 8. Out of Scope

The following are explicitly excluded from this sprint:

1. **L7057 format_final.py blob** — line 7057 of Brandl FINAL_FORMATTED.txt is a ~3,000-word steno block collapsed onto a single line by format_final.py. This is a format_final defect, not an AI Q/A bleed defect. Separate ticket required.

2. **Per-CR learning loop** — the Proof of Work schema in §6 lays the data foundation. No learning system, training pipeline, or feedback mechanism is built in this sprint. Not even a stub.

3. **§5.2 prompt changes** — this sprint is code-backstop only. The §5.2 rule in MASTER_DEPOSITION_ENGINE_v4.2.md stays as-is. If this sprint succeeds, a follow-on prompt refinement may be valuable, but it's not in scope here.

4. **Other depos / CR profiles** — the backstop is written generically but will be validated only on Brandl/MB. AD (Alicia D'Alotto) and future CRs will be validated in their own sprints.

5. **DEF-B (attorney label stripping)** — separate defect, separate sprint. The backstop must not interfere with `MR. LASTNAME:` speaker labels.

6. **Performance optimization** — the backstop processes `corrected_text.txt` line by line. At 354 pages / ~3,300 lines, runtime should be < 1 second. No optimization needed.

7. **UI / CR-facing changes** — the `[REVIEW-NNN]` tag is designed to be CR-friendly in CAT software, but no CAT integration work is in scope.

---

## 9. Risks and Unknowns

### R1 — Mode B classification accuracy (HIGH RISK)
The safe vs. uncertain boundary in §4 is based on punctuation heuristics. Short answers without terminal punctuation ("Uh-huh", "No", numbers, years) are the hardest cases. Over-aggressive classification → auto-fixes that break legitimate text. Under-aggressive → too many `[REVIEW-NNN]` tags that annoy the CR.

**Mitigation (DECIDED 2026-04-18):** Start conservative. Target **≤ 3 tags per page** on the first run. Over-flagging is acceptable — tags MB always accepts become silent auto-fixes in the next sprint. Do not loosen the classifier until MB has reviewed at least one full delivery and reported back which tag patterns are safe to promote.

**Calibration loop:** After first Brandl delivery, ask MB: "Which of these [REVIEW-NNN] tags did you always split? Which did you always merge?" Patterns she always splits → promote to Mode B safe list. Patterns she always merges → add to self-correction or FP guard lists.

### R2 — Chained bleeds in a single paragraph (MEDIUM RISK)
Some paragraphs may have 3+ turns crammed in (e.g., `A. Yes. Q. Okay. A. Right. Q. And then?`). The recursive splitter handles this up to depth 5, but the alternation check could fire incorrectly on the intermediate fragments. Need to test with synthetic examples.

### R3 — Verify agent flags in corrected_text.txt (MEDIUM RISK)
The verify agents may have inserted `[FLAG:]`, `[REVIEW]`, `[[REVIEW]]`, or other tags into `corrected_text.txt` before the backstop runs. The backstop must not misinterpret these as bleed or strip them.

**Guard required:** Skip any paragraph that contains an existing verify-agent tag. Log as "skipped — pre-existing flag." Don't touch it.

### R4 — corrected_text.txt paragraph structure (LOW-MEDIUM RISK)
The backstop assumes paragraphs in `corrected_text.txt` are blank-line separated and that each paragraph is a single speaker block. If the verify agents or the AI have produced non-standard paragraph structure (e.g., multi-block paragraphs, missing blank lines), the detector may mis-fire.

**Mitigation:** Add a pre-flight check: count paragraphs, verify each is ≤ 500 chars on average (as a sanity signal). If the file looks malformed, log a WARNING and run in tag-only mode (no auto-fixes).

### R5 — Tag volume in Brandl output (LOW RISK)
440 hits with a conservative classifier could produce 100+ `[REVIEW-NNN]` tags. That may be too many for MB to review efficiently. First run should report the projected tag count before inserting any tags, so Scott can decide whether to loosen the auto-fix threshold.

### R6 — Acceptance test regime changes (LOW RISK)
The new `DEF-015-WIDE` acceptance check (§7.1) will fire on every existing test fixture that hasn't been processed by the backstop. Need to update the regression suite to run backstop before the wide check, or to run the wide check only on backstop-processed output.

---

## Summary

| Item | Decision |
|---|---|
| Backstop placement | Post-verify, pre-format_final (operates on corrected_text.txt) |
| Detector | Wide — paragraph-level, mid-label scan, 7 FP guards |
| Mode A auto-fix | Split at stray label, preserve labels, chain up to depth 5 |
| Mode B auto-fix | Only when safe: terminal punctuation + known short-utterance pattern |
| Uncertain → tag | `[REVIEW-NNN: possible turn break]` inline at break point |
| Proof of Work | Separate `PROOF_OF_WORK_BACKSTOP.json`, machine-readable, future-learning-safe |
| Test target | 440 bleed → 0 untagged + N tagged, all passing checks still pass |
| Out of scope | L7057, learning loop, §5.2 prompt, DEF-B, other CR profiles |
| Highest risk | Mode B classification threshold — needs MB calibration input |

**All open items resolved 2026-04-18.** Spec is implementation-ready.

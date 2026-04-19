# qa_line_splitter.py

**Purpose:** Eliminate DEF-015 (dense inline Q/A blocks) by splitting collapsed multi-turn lines into separate lines after the AI correction pass.

**Prime directive:** Adds structure only. Never modifies, deletes, or reorders content words.

---

## Pipeline position

```
ai_engine.py  →  [qa_line_splitter.py]  →  def015_backstop.py  →  format_final.py
```

Not yet wired into `run_pipeline.py`. Manual use only until CSA approves integration.

---

## What it does

The AI correction pass sometimes writes multiple Q/A speaker turns onto a single output line:

```
Q. Were they in Houston? [REVIEW-031: possible turn break] A. Were they in Houston? Q. They were -- Denver? A. Denver. Q. Okay. ...
```

The splitter detects lines containing **2 or more Q/A turn boundaries** (`\b[QA]\.\s`) and inserts a line break at each boundary:

```
Q. Were they in Houston? [REVIEW-031: possible turn break]
A. Were they in Houston?
Q. They were -- Denver?
A. Denver.
Q. Okay. ...
```

---

## What it does NOT split

| Pattern | Example | Reason |
|---------|---------|--------|
| `Mr.` / `Mrs.` / `Dr.` | `Mr. Smith` | Word boundary: `\b` won't match mid-word |
| Decimals | `2.5 percent` | Not `Q` or `A` |
| `ESQ.` | `J. PEACOCK, ESQ.` | `Q` in `ESQ` has no word boundary before it |
| Attorney colloquy | `MR. MADIGAN:` | No Q/A followed by dot |
| `[REVIEW: ...]` bracket content | `[REVIEW-031: Q. note]` | Bracket content is masked before splitting |

---

## Usage

```bash
# Default: reads/writes corrected_text.txt in CWD, backs up original
python qa_line_splitter.py

# Explicit paths
python qa_line_splitter.py --input corrected_text.txt --output corrected_split.txt

# Dry run: stats only, no files written
python qa_line_splitter.py --dry-run
```

### Output summary

```
Lines input   : 1624
Lines output  : 1680
Lines split   : 7
Warnings      : 0
Backup written: corrected_text.txt.pre_split_2026-04-19
Output written: corrected_text.txt
```

---

## Backup

Before any in-place write, the script creates:

```
corrected_text.txt.pre_split_YYYY-MM-DD
```

---

## Warnings

If a split fragment starts with a token not in the expected set (`Q.`, `A.`, `MR.`, `MS.`, `MRS.`, `DR.`, `THE`, `BY`, `(`, `[`), the splitter logs:

```
[WARN] unexpected leading token at line 620: 'some fragment...'
```

Processing continues. Warnings do not abort the run.

---

## Tests

```bash
cd C:\Users\scott\OneDrive\Documents\mb_demo_engine_v4
pytest test_qa_line_splitter.py -v
```

All tests must pass before pipeline wiring.

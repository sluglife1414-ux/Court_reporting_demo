"""
label_qa.py — Pre-AI Q/A Structure Labeler
============================================
Runs AFTER steno_cleanup.py, BEFORE ai_engine.py.

Problem this solves:
  The sgngl extraction produces continuous testimony with no Q./A. labels and
  no blank-line separators between exchanges. The AI engine (implicit KEEP) only
  emits correction ops — it doesn't restructure the text. So format_final.py's
  Q/A toggle never fires, and all testimony formats as colloquy under the last
  speaker label (producing ~200 pages instead of ~357).

What this script does:
  Reads cleaned_text.txt. Finds testimony sections (after EXAMINATION / BY MR.
  lines). For each content line in a testimony section, assigns a Q. or A. label
  based on an alternating toggle, and emits each sentence as its own blank-
  separated block. Preamble (caption, index, appearances, stipulation) is
  passed through unchanged.

  After this step the AI engine sees pre-labeled Q/A content. With implicit KEEP
  it preserves the labels and only emits steno-correction ops. format_final.py
  then gets properly structured input and produces correct page count.

  Labels are APPROXIMATE — the toggle alternates Q/A on every sentence, which
  won't match the real exchange boundaries exactly. The AI pass and the CR's
  review correct any mis-labeling.

Usage:
  python label_qa.py            # reads/writes cleaned_text.txt in CWD
  python label_qa.py --dry-run  # prints stats only, no write
"""

import re
import sys
import os

# ── Sentence boundary split ────────────────────────────────────────────────────
# Split after . ? ! when followed by whitespace + uppercase / ( / "
# Avoids splitting: Mr. Mrs. Dr. vs. etc. + decimal numbers (3.5) + abbreviations
_SENT_SPLIT_RE = re.compile(
    r'(?<=[.?!])\s+(?=[A-Z(\"])',
)
_ABBREV_RE = re.compile(
    r'\b(?:Mr|Mrs|Ms|Dr|Jr|Sr|Prof|St|vs|etc|e\.g|i\.e|cf|No|Vol|Dept|Exh)\.$',
    re.IGNORECASE,
)


def split_sentences(text):
    """
    Split text at sentence boundaries. Returns list of sentence strings.
    Keeps punctuation attached to the sentence it ends.
    Conservative: if a candidate split point follows a known abbreviation,
    don't split there.
    """
    if len(text) < 80:
        # Short enough — keep as one block
        return [text] if text.strip() else []

    parts = _SENT_SPLIT_RE.split(text)
    if len(parts) == 1:
        return [text]

    # Re-join any part that ends with an abbreviation into the next part
    result = []
    buf = parts[0]
    for part in parts[1:]:
        if _ABBREV_RE.search(buf.rstrip()):
            buf = buf + ' ' + part
        else:
            result.append(buf)
            buf = part
    if buf:
        result.append(buf)

    return [s for s in result if s.strip()]


# ── Block-type detection ───────────────────────────────────────────────────────

def classify(line):
    """Return the type of a stripped, non-empty line."""
    s = line.strip()
    if not s:
        return 'blank'
    if re.match(r'^BY\s+(MR\.|MS\.)', s):
        return 'by'
    if re.match(r'^(MR\.|MS\.|MRS\.|THE\s+(?:VIDEOGRAPHER|COURT\s+REPORTER|WITNESS))', s):
        return 'speaker'
    if re.match(r'^EXAMINATION', s):
        return 'examination'
    if re.match(r'^Q\.\s', s) or s == 'Q.':
        return 'q'
    if re.match(r'^A\.\s', s) or s == 'A.':
        return 'a'
    if re.match(r'^\(Whereupon,', s, re.IGNORECASE):
        return 'whereupon'
    if re.match(r'^[-*]{3,}', s) or re.match(r'^\*\s+\*', s):
        return 'structural'
    return 'content'


# ── Main ───────────────────────────────────────────────────────────────────────

def label_qa(lines):
    """
    Process cleaned_text lines and return labeled lines.
    Returns (out_lines, stats_dict).
    """
    out = []
    stats = {
        'q_labels_added': 0,
        'a_labels_added': 0,
        'existing_q_kept': 0,
        'existing_a_kept': 0,
        'colloquy_blocks': 0,
        'sentences_split': 0,
        'preamble_lines': 0,
    }

    in_testimony   = False   # True after first EXAMINATION / BY MR. line
    qa_toggle      = 'Q'     # alternates Q → A → Q ...
    last_was_blank = True    # track whether previous output line was blank

    def emit(text):
        nonlocal last_was_blank
        out.append(text)
        last_was_blank = not text.strip()

    def ensure_blank():
        """Emit a blank line if the last output line wasn't blank."""
        if not last_was_blank:
            emit('')

    def emit_qa_block(text, label):
        """Emit one Q. or A. labeled block followed by a blank."""
        ensure_blank()
        emit(f'{label}.\t{text}')
        emit('')

    for raw in lines:
        s = raw.strip()
        kind = classify(s)

        # ── Blank lines ──
        if kind == 'blank':
            ensure_blank()
            continue

        # ── Structural markers (asterisks, dashes) ──
        if kind == 'structural':
            ensure_blank()
            emit(s)
            continue

        # ── EXAMINATION header ──
        if kind == 'examination':
            ensure_blank()
            emit(s)
            in_testimony = True
            # Don't change qa_toggle here; BY MR. below resets it
            continue

        # ── BY MR./MS. line ──
        if kind == 'by':
            ensure_blank()
            emit(s)
            in_testimony = True
            qa_toggle = 'Q'
            continue

        # ── Speaker label (MR./MS./THE WITNESS etc.) ──
        if kind == 'speaker':
            ensure_blank()
            emit(s)
            stats['colloquy_blocks'] += 1
            # Do NOT turn off in_testimony — examination continues after colloquy.
            # The toggle keeps going: next content block gets current qa_toggle.
            continue

        # ── Already-labeled Q./A. ──
        if kind in ('q', 'a'):
            ensure_blank()
            emit(s)
            emit('')
            if kind == 'q':
                stats['existing_q_kept'] += 1
                qa_toggle = 'A'
            else:
                stats['existing_a_kept'] += 1
                qa_toggle = 'Q'
            continue

        # ── (Whereupon, ...) parenthetical ──
        if kind == 'whereupon':
            ensure_blank()
            emit(s)
            continue

        # ── Content lines ──
        if not in_testimony:
            # Preamble — caption, index, appearances, stipulation
            stats['preamble_lines'] += 1
            emit(s)
            continue

        # Testimony content: split into sentences, label each
        sentences = split_sentences(s)
        if len(sentences) > 1:
            stats['sentences_split'] += len(sentences) - 1
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            emit_qa_block(sent, qa_toggle)
            if qa_toggle == 'Q':
                stats['q_labels_added'] += 1
                qa_toggle = 'A'
            else:
                stats['a_labels_added'] += 1
                qa_toggle = 'Q'

    return out, stats


def main():
    dry_run = '--dry-run' in sys.argv

    input_path = 'cleaned_text.txt'
    if not os.path.exists(input_path):
        print(f'[label_qa] ERROR: {input_path} not found in {os.getcwd()}')
        sys.exit(1)

    with open(input_path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    print(f'[label_qa] Input:  {input_path} ({len(lines)} lines)')

    out_lines, stats = label_qa(lines)

    q_total  = stats['q_labels_added']  + stats['existing_q_kept']
    a_total  = stats['a_labels_added']  + stats['existing_a_kept']
    print(f'[label_qa] Q. blocks: {q_total:4d}  ({stats["q_labels_added"]} added, {stats["existing_q_kept"]} kept)')
    print(f'[label_qa] A. blocks: {a_total:4d}  ({stats["a_labels_added"]} added, {stats["existing_a_kept"]} kept)')
    print(f'[label_qa] Colloquy speaker labels: {stats["colloquy_blocks"]}')
    print(f'[label_qa] Sentences split from long lines: {stats["sentences_split"]}')
    print(f'[label_qa] Preamble lines (unchanged): {stats["preamble_lines"]}')
    print(f'[label_qa] Output: {len(out_lines)} lines  (input was {len(lines)})')

    if dry_run:
        print('[label_qa] Dry-run mode — no file written.')
        return

    # Write in-place
    with open(input_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(line.rstrip() for line in out_lines))
        f.write('\n')

    print(f'[label_qa] Wrote labeled cleaned_text.txt')


if __name__ == '__main__':
    main()

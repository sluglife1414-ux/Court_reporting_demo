"""
qa_structure_detector.py — Q/A Structure Detector + Post-AI Sanity Check
=========================================================================
Renamed from label_qa.py. Role changed in v4.2 (SPEC-2026-04-17-chunk01-3file).

Previous role (removed):
  Assigned approximate Q./A. labels to testimony content via alternating toggle.
  This was defective — toggle flipped per sentence, not per speaker turn,
  producing misattributed labels that propagated through to final output.

New role:
  1. Structural normalization — pass cleaned_text.txt through with blank-line
     separators between structural blocks. Does NOT assign Q./A. labels.
     AI is sole Q/A labeling authority.
  2. Post-AI sanity check — after AI pass completes, verify AI did not hallucinate
     speaker turns beyond the structural cues present in input.

Structural elements detected and tracked (but not modified):
  - EXAMINATION / CROSS-EXAMINATION / REDIRECT headers
  - BY MR./MS. [NAME] attorney identification lines
  - MR./MS./THE WITNESS speaker labels
  - Existing Q./A. blocks (from steno — preserved verbatim)
  - (Whereupon, ...) parentheticals

Usage:
  python qa_structure_detector.py            # reads/writes cleaned_text.txt in CWD
  python qa_structure_detector.py --dry-run  # prints stats only, no write
"""

import re
import sys
import os

# ── Sentence boundary split ────────────────────────────────────────────────────
# Retained — used by split_sentences() (utility) and sanity_check_speaker_turns().
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


# ── Main structural pass ───────────────────────────────────────────────────────

def detect_structure(lines):
    """
    Process cleaned_text lines and return structurally normalized lines.

    Normalizes blank-line separation between structural blocks.
    Does NOT assign Q./A. labels — AI handles Q/A authority (v4.2).

    Returns (out_lines, stats_dict).
    stats_dict is used by sanity_check_speaker_turns() to establish input baseline.
    """
    out = []
    stats = {
        'structural_headers': 0,   # EXAMINATION / BY MR. headers found
        'speaker_labels': 0,        # MR./MS./THE WITNESS labels found
        'existing_qa_blocks': 0,    # Q./A. blocks already present (from steno)
        'content_lines': 0,         # unlabeled content lines (AI will assign Q/A)
    }

    last_was_blank = True    # track whether previous output line was blank

    def emit(text):
        nonlocal last_was_blank
        out.append(text)
        last_was_blank = not text.strip()

    def ensure_blank():
        """Emit a blank line if the last output line wasn't blank."""
        if not last_was_blank:
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
            stats['structural_headers'] += 1
            continue

        # ── BY MR./MS. line ──
        if kind == 'by':
            ensure_blank()
            emit(s)
            stats['structural_headers'] += 1
            continue

        # ── Speaker label (MR./MS./THE WITNESS etc.) ──
        if kind == 'speaker':
            ensure_blank()
            emit(s)
            stats['speaker_labels'] += 1
            continue

        # ── Already-labeled Q./A. (from steno — preserved verbatim) ──
        if kind in ('q', 'a'):
            ensure_blank()
            emit(s)
            emit('')
            stats['existing_qa_blocks'] += 1
            continue

        # ── (Whereupon, ...) parenthetical ──
        if kind == 'whereupon':
            ensure_blank()
            emit(s)
            continue

        # ── Content line — pass through without labeling ──
        # AI is sole Q/A authority. Labels assigned during AI correction pass.
        stats['content_lines'] += 1
        emit(s)

    return out, stats


# ── Post-AI sanity check ───────────────────────────────────────────────────────

def sanity_check_speaker_turns(ai_output_lines, input_stats):
    """
    Post-AI guardrail. Counts distinct Q./A. speaker turns in AI output
    vs. structural cues present in input. Flags for human review if AI
    produced turns beyond tolerance.

    Heuristic: flag if AI Q/A turn count exceeds estimated expected turns
    by more than TOLERANCE_MULTIPLIER (20% buffer).

    NOTE: Spec §5.1 called for +2σ tolerance. +2σ requires per-depo variance
    data not yet collected. Using 20% buffer as documented substitute.
    Flagged for v5 upgrade once variance data is available from production runs.
    (SPEC-2026-04-17-chunk01-3file §5.1)

    Args:
        ai_output_lines (list[str]): lines from AI-corrected output file
        input_stats (dict): stats dict returned by detect_structure() —
            keys: structural_headers, speaker_labels, existing_qa_blocks,
                  content_lines

    Returns:
        tuple(passed: bool, details: dict)
            passed   — True if within tolerance; False if over threshold
            details  — dict for Proof of Work logging; includes flag_message
                       if passed is False

    Does NOT block delivery. Caller logs details to Proof of Work and continues.
    """
    TOLERANCE_MULTIPLIER = 1.20   # 20% buffer; upgrade to +2σ in v5

    # Count Q./A. speaker turns in AI output
    qa_turn_re = re.compile(r'^[QA]\.\s+', re.MULTILINE)
    ai_turns = len(qa_turn_re.findall('\n'.join(ai_output_lines)))

    # Estimate expected turns from input structural cues:
    #   - Each structural header (EXAMINATION/BY MR.) signals a new Q/A section
    #   - Existing Q/A blocks from steno are preserved (already counted)
    #   - Content lines represent testimony AI must label — each becomes a turn
    input_cue_count = (
        input_stats.get('structural_headers', 0) * 2   # heuristic: ~2 turns per section start
        + input_stats.get('existing_qa_blocks', 0)
        + input_stats.get('content_lines', 0)
    )

    threshold = max(input_cue_count * TOLERANCE_MULTIPLIER, 10)   # floor of 10

    passed = ai_turns <= threshold
    details = {
        'ai_turn_count': ai_turns,
        'input_cue_count': input_cue_count,
        'threshold': round(threshold, 1),
        'tolerance_multiplier': TOLERANCE_MULTIPLIER,
        'passed': passed,
        'flag_message': (
            None if passed else
            f'[QA-SANITY] AI produced {ai_turns} Q/A turns vs. '
            f'{input_cue_count} input cues (threshold {threshold:.0f}). '
            f'Review for hallucinated speaker turns.'
        ),
        'heuristic_note': (
            'Using 20% buffer heuristic (SPEC-2026-04-17-chunk01-3file \u00a7'
            '5.1). Upgrade to +2\u03c3 formula in v5 once per-depo variance '
            'data available.'
        ),
    }
    return passed, details


def main():
    dry_run = '--dry-run' in sys.argv

    input_path = 'cleaned_text.txt'
    if not os.path.exists(input_path):
        print(f'[qa_structure_detector] ERROR: {input_path} not found in {os.getcwd()}')
        sys.exit(1)

    with open(input_path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    print(f'[qa_structure_detector] Input:  {input_path} ({len(lines)} lines)')

    out_lines, stats = detect_structure(lines)

    print(f'[qa_structure_detector] Structural headers (EXAMINATION/BY MR.): {stats["structural_headers"]}')
    print(f'[qa_structure_detector] Speaker labels (MR./MS./THE WITNESS):     {stats["speaker_labels"]}')
    print(f'[qa_structure_detector] Existing Q/A blocks (from steno):          {stats["existing_qa_blocks"]}')
    print(f'[qa_structure_detector] Content lines (unlabeled, AI assigns Q/A): {stats["content_lines"]}')
    print(f'[qa_structure_detector] Output: {len(out_lines)} lines  (input was {len(lines)})')

    if dry_run:
        print('[qa_structure_detector] Dry-run mode — no file written.')
        return

    # Write in-place
    with open(input_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(line.rstrip() for line in out_lines))
        f.write('\n')

    print(f'[qa_structure_detector] Wrote normalized cleaned_text.txt')


if __name__ == '__main__':
    main()

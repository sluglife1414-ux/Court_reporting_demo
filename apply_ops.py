"""
apply_ops.py — Assemble corrected text from a validated op list.

Called only AFTER validate_ops.py has returned ok=True.
Walks the op list in span order, replacing or keeping each token span.

Punctuation and capitalization are NOT added here — that's the formatter's job.
This file only performs word-level substitutions as directed by the validated ops.

Usage:
    cleaned_text = apply_ops(ops, tokens)
"""

from typing import List, Tuple
from tokenize_chunk import BLANK_TOKEN


def apply_ops(
    ops: list,
    tokens: List[Tuple[int, str, bool]],
) -> str:
    """
    Walk validated ops and produce the corrected chunk text.

    KEEP   -> emit raw tokens verbatim
    REWORD -> emit op["to"] text
    FLAG   -> emit raw tokens verbatim + [[REVIEW: reason]] tag inline

    Returns plain text string preserving paragraph structure.
    """
    # Sort ops by span start so we can walk in document order
    sorted_ops = sorted(ops, key=lambda op: op["span"][0])

    # Build a lookup: token_index -> op
    token_to_op = {}
    for op in sorted_ops:
        start, end = op["span"]
        for i in range(start, end + 1):
            token_to_op[i] = op

    parts = []
    prev_was_blank = False
    seen_ops = set()  # track which ops we've already emitted (for REWORD/FLAG spans)

    for idx, word, is_blank in tokens:
        op = token_to_op.get(idx)
        if op is None:
            # Should not happen after coverage check passes — emit raw as safety net
            if is_blank:
                parts.append("\n\n")
            else:
                parts.append(word + " ")
            continue

        op_type = op["op"]
        span_start = op["span"][0]

        if is_blank:
            # Blank tokens (paragraph breaks) — always preserve
            parts.append("\n\n")
            prev_was_blank = True
            continue

        prev_was_blank = False

        if op_type == "KEEP":
            # Emit raw token
            parts.append(word + " ")

        elif op_type == "REWORD":
            # Only emit the replacement text once, at the START of the span
            if span_start not in seen_ops:
                to_text = op.get("to", "").strip()
                if to_text:
                    parts.append(to_text + " ")
                # If to_text is empty (explicit deletion — rare) — emit nothing
                seen_ops.add(span_start)
            # For subsequent tokens in this span — already emitted, skip

        elif op_type == "FLAG":
            # Emit raw tokens verbatim, then add [[REVIEW: reason]] after the last token
            parts.append(word + " ")
            if idx == op["span"][1]:  # last token in this span
                reason = op.get("reason", "flagged for review")
                parts.append(f"[[REVIEW: {reason}]] ")

    result = "".join(parts)

    # Clean up spacing artifacts
    import re
    result = re.sub(r'  +', ' ', result)         # collapse double spaces
    result = re.sub(r' \n', '\n', result)         # no trailing space before newline
    result = re.sub(r'\n +\n', '\n\n', result)    # no spaces on blank lines
    result = result.strip()

    return result


def ops_to_corrections_log(
    ops: list,
    tokens: List[Tuple[int, str, bool]],
    chunk_num: int,
    line_start: int,
) -> list:
    """
    Convert validated ops into the existing correction_log format
    so the downstream pipeline (build_cr_review.py, etc.) still works.

    Returns a list of correction dicts compatible with ai_engine.py format.
    """
    from tokenize_chunk import get_span_words

    corrections = []
    for op in ops:
        if op["op"] == "KEEP":
            continue  # no log entry for unchanged spans

        start, end = op["span"]
        original = get_span_words(tokens, start, end)
        corrected_text = op.get("to", original)
        source = op.get("source", "")
        reason = op.get("reason", "")
        confidence_val = op.get("confidence", None)

        # Map source to confidence level
        if op["op"] == "FLAG":
            confidence = "LOW"
            corrected_text = f"{original} [[REVIEW: {reason}]]"
        elif confidence_val is not None:
            # Numeric confidence (0.0–1.0) -> level
            if confidence_val >= 0.90:
                confidence = "HIGH"
            elif confidence_val >= 0.75:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
        elif source in ("raw_steno", "case_dict", "names_lock", "house_style"):
            confidence = "HIGH"
        elif source in ("kb",):
            confidence = "MEDIUM"
        elif source in ("phonetic_match",):
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        corrections.append({
            "line_approx":   line_start + start,
            "original":      original,
            "corrected":     corrected_text,
            "confidence":    confidence,
            "reason":        f"[{source}] {reason}",
            "source":        source,
        })

    return corrections


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from tokenize_chunk import tokenize_chunk

    sample = """Q. and you arrived on scene at what time

A. it was approximate ly 14 hundred hours

Q. who was the incident commander

A. that would of been chief montz jack montz"""

    tokens = tokenize_chunk(sample)

    ops = [
        {"op": "KEEP",   "span": [0,  10]},
        {"op": "REWORD", "span": [11, 12], "from": "approximate ly", "to": "approximately",
         "source": "raw_steno", "reason": "rejoined split token"},
        {"op": "REWORD", "span": [13, 15], "from": "14 hundred hours", "to": "1400 hours",
         "source": "house_style", "reason": "time format"},
        {"op": "KEEP",   "span": [16, 24]},
        {"op": "REWORD", "span": [25, 25], "from": "of", "to": "have",
         "source": "raw_steno", "reason": "would of -> would have"},
        {"op": "KEEP",   "span": [26, 27]},
        {"op": "REWORD", "span": [28, 30], "from": "montz jack montz", "to": "Jack Montz",
         "source": "names_lock", "reason": "duplicate surname"},
    ]

    result = apply_ops(ops, tokens)
    print("=== APPLIED OUTPUT ===")
    print(result)
    print("\n=== CORRECTIONS LOG ===")
    for c in ops_to_corrections_log(ops, tokens, chunk_num=0, line_start=100):
        print(f"  {c}")

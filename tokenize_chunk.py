"""
tokenize_chunk.py — Assign stable token indexes to a raw steno chunk.

The token index is the ground truth the ops schema uses for coverage checking.
We assign one index per whitespace-delimited word in the raw chunk, preserving
paragraph breaks as a special BLANK token.

Why words, not lines:
  Steno has no reliable line structure — one Q/A exchange may span many
  "lines" or be one long string. Word-level spans are stable across all
  steno formats.

Usage:
    tokens = tokenize_chunk(raw_chunk_text)
    annotated = annotate_chunk(raw_chunk_text)   # returns text with [N] indexes

Returns:
    tokens      — list of (index, word, is_blank) tuples
    annotated   — string with token indexes inline, for feeding to Agent B
"""

import re
from typing import List, Tuple


# A token is either a word or a BLANK (paragraph break).
# We distinguish blanks so the coverage check can verify them.
BLANK_TOKEN = "¶"


def tokenize_chunk(text: str) -> List[Tuple[int, str, bool]]:
    """
    Split raw steno chunk into indexed tokens.

    Returns list of (index, word, is_blank):
        index    — 0-based integer, global within this chunk
        word     — the actual word string (or BLANK_TOKEN for paragraph breaks)
        is_blank — True if this is a paragraph separator

    Paragraph breaks (two or more newlines in a row) become a single BLANK token.
    Single newlines within a paragraph are treated as spaces.
    """
    # Normalize: collapse 3+ newlines to 2, strip trailing whitespace per line
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)

    tokens = []
    idx = 0

    # Split into paragraph blocks first
    blocks = re.split(r'\n\n+', text)

    for block_num, block in enumerate(blocks):
        # Add blank token between paragraphs (not before first)
        if block_num > 0:
            tokens.append((idx, BLANK_TOKEN, True))
            idx += 1

        # Tokenize words within the block
        words = block.split()
        for word in words:
            tokens.append((idx, word, False))
            idx += 1

    return tokens


def annotate_chunk(text: str) -> str:
    """
    Return the raw chunk text with token indexes prepended to each token.
    Format: [N]word for words, [N]¶ for paragraph breaks.

    This is what gets sent to Agent B so it can reference token spans.
    Example:
        Input:  "Q. and you arrived\n\nA. yes"
        Output: "[0]Q. [1]and [2]you [3]arrived\n\n[4]¶\n\n[5]A. [6]yes"
    """
    tokens = tokenize_chunk(text)
    out_parts = []
    blank_pending = False

    for idx, word, is_blank in tokens:
        if is_blank:
            out_parts.append(f"\n\n[{idx}]¶\n\n")
        else:
            out_parts.append(f"[{idx}]{word} ")

    return "".join(out_parts).strip()


def tokens_to_text(tokens: List[Tuple[int, str, bool]]) -> str:
    """Reconstruct raw text from a token list (for apply_ops.py)."""
    parts = []
    for idx, word, is_blank in tokens:
        if is_blank:
            parts.append("\n\n")
        else:
            parts.append(word + " ")
    return "".join(parts).strip()


def get_span_words(tokens: List[Tuple[int, str, bool]], start: int, end: int) -> str:
    """Return the raw words for a token span [start, end] inclusive."""
    span_words = []
    for idx, word, is_blank in tokens:
        if start <= idx <= end:
            if not is_blank:
                span_words.append(word)
    return " ".join(span_words)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = """Q. and you arrived on scene at what time

A. it was approximate ly 14 hundred hours

Q. who was the incident commander

A. that would of been chief montz jack montz"""

    print("=== TOKENS ===")
    for tok in tokenize_chunk(sample):
        print(f"  {tok}")

    print("\n=== ANNOTATED (sent to Agent B) ===")
    print(annotate_chunk(sample))

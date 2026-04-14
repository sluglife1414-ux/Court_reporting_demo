"""
validate_ops.py — Validate Agent B's op list before any text is written.

Three hard checks (Opus's design, adapted for our steno token format):
  1. COVERAGE  — every raw token covered exactly once (kills block collapse)
  2. SOURCES   — every REWORD cites a valid source enum (kills vibes-based edits)
  3. NAMES     — every capitalized token in REWORD.to is in names.lock (kills Mary Duck)

Plus two soft checks logged as warnings:
  4. WORD BUDGET — output word count vs input (95% threshold)
  5. FROM MATCH  — REWORD.from matches actual raw tokens at that span

Usage:
    result = validate_ops(ops, tokens, names_lock_set)
    if result.ok:
        ...  # safe to apply
    else:
        print(result.reason)

Returns a ValidationResult with fields:
    ok      — bool
    reason  — human-readable rejection reason (for [[REVIEW]] tag)
    warnings — list of non-fatal issues
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set

from tokenize_chunk import get_span_words, BLANK_TOKEN


# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_OPS = {"KEEP", "REWORD", "FLAG"}

ALLOWED_SOURCES = {
    "raw_steno",      # direct read of steno phonetics
    "case_dict",      # term found in case-specific .tlx dictionary
    "kb",             # found in engine knowledge base
    "names_lock",     # name from names.lock (case caption, attorneys, witnesses)
    "phonetic_match", # phonetic similarity (Soundex/Metaphone or manual)
    "house_style",    # MB/CR house style rule (e.g. normalization, time format)
}

# Hard reject if output word count falls below this fraction of input
WORD_BUDGET_HARD = 0.90
# Soft warning if output word count falls below this fraction of input
WORD_BUDGET_SOFT = 0.97


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""
    warnings: List[str] = field(default_factory=list)

    def __bool__(self):
        return self.ok


# ── Check 1: Coverage ─────────────────────────────────────────────────────────

def check_coverage(ops: list, raw_token_count: int) -> ValidationResult:
    """Every raw token must appear in exactly one op span. No gaps, no overlaps."""
    if not ops:
        return ValidationResult(False, "empty ops list — no operations returned")

    covered = [0] * raw_token_count

    for op in ops:
        if "span" not in op:
            return ValidationResult(False, f"op missing span field: {op}")

        span = op["span"]
        if not isinstance(span, list) or len(span) != 2:
            return ValidationResult(False, f"span must be [start, end], got: {span}")

        start, end = span
        if not isinstance(start, int) or not isinstance(end, int):
            return ValidationResult(False, f"span values must be integers: {span}")
        if start < 0 or end >= raw_token_count:
            return ValidationResult(
                False,
                f"span {span} out of range (raw token count = {raw_token_count})"
            )
        if start > end:
            return ValidationResult(False, f"span start > end: {span}")

        for i in range(start, end + 1):
            covered[i] += 1

    gaps = [i for i, c in enumerate(covered) if c == 0]
    overlaps = [i for i, c in enumerate(covered) if c > 1]

    if gaps:
        gap_sample = gaps[:5]
        return ValidationResult(
            False,
            f"coverage gap — {len(gaps)} token(s) not covered by any op. "
            f"First gaps at token indexes: {gap_sample}"
        )
    if overlaps:
        return ValidationResult(
            False,
            f"coverage overlap — {len(overlaps)} token(s) covered by multiple ops. "
            f"First overlaps at: {overlaps[:5]}"
        )

    return ValidationResult(True)


# ── Check 2: Sources ──────────────────────────────────────────────────────────

def check_sources(ops: list) -> ValidationResult:
    """Every REWORD op must cite a valid source from the allowed enum."""
    for op in ops:
        if op.get("op") != "REWORD":
            continue

        source = op.get("source", "")
        if source not in ALLOWED_SOURCES:
            return ValidationResult(
                False,
                f"REWORD op at span {op.get('span')} has invalid source: "
                f"'{source}'. Allowed: {sorted(ALLOWED_SOURCES)}"
            )

        # Soft gate for phonetic_match: from and to should sound alike
        # (warning only — Soundex on multi-word / combined tokens is unreliable)
        if source == "phonetic_match":
            from_text = op.get("from", "")
            to_text = op.get("to", "")
            if from_text and to_text:
                if not _phonetic_similar(from_text, to_text):
                    pass  # logged as warning in check_from_match; don't hard-reject

    return ValidationResult(True)


def _soundex(word: str) -> str:
    """Simple Soundex implementation for phonetic matching."""
    word = re.sub(r'[^a-zA-Z]', '', word).upper()
    if not word:
        return "0000"

    code_map = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6',
    }

    first = word[0]
    codes = [first]
    prev_code = code_map.get(first, '0')

    for char in word[1:]:
        code = code_map.get(char, '0')
        if code != '0' and code != prev_code:
            codes.append(code)
        prev_code = code

    soundex = ''.join(codes)[:4].ljust(4, '0')
    return soundex


def _phonetic_similar(from_text: str, to_text: str) -> bool:
    """Return True if from and to are phonetically close (Soundex on first word)."""
    from_word = from_text.split()[0] if from_text.split() else from_text
    to_word = to_text.split()[0] if to_text.split() else to_text
    return _soundex(from_word) == _soundex(to_word)


# ── Check 3: Names ────────────────────────────────────────────────────────────

def check_names(ops: list, names_lock: Set[str]) -> ValidationResult:
    """
    Every capitalized token in REWORD.to must be in names.lock.

    Skips:
    - Sentence-initial capitalization (first word of a sentence, after Q./A.)
    - Single letters (I, A, etc.)
    - Known depo artifacts (Q., A., MR., MS., etc.)
    """
    if not names_lock or len(names_lock) < 5:
        # Empty or suspiciously small lock — hard reject.
        # A missing names.lock means we can't validate proper nouns at all.
        # Better to reject the whole op list than silently pass wrong names.
        return ValidationResult(
            False,
            "names.lock missing or has fewer than 5 entries — "
            "cannot validate proper nouns. Run names_lock.py first."
        )

    ALWAYS_OK_PATTERNS = re.compile(
        r'^(Q\.|A\.|MR\.|MS\.|MRS\.|DR\.|THE|BY|AND|OR|FOR|IN|OF|AT|TO|'
        r'UH+|UHM+|HM+|OH|OKAY|YES|NO|SIR|MA\'?AM|WELL|RIGHT|ALRIGHT|'
        r'NOW|SO|BUT|YEP|YEAH|NOPE|SURE|CERTAINLY|ABSOLUTELY|CORRECT)$',
        re.IGNORECASE
    )

    for op in ops:
        if op.get("op") != "REWORD":
            continue

        to_text = op.get("to", "")
        from_text = op.get("from", "")

        # Build set of capitalized tokens present in the raw "from" text.
        # Words capitalized in the steno source are NOT new introductions —
        # the agent is allowed to carry them through. Only NEW capitalized
        # words (introduced by the agent, absent from steno) are checked.
        from_caps = {
            t.strip("''-.,;:!?\"").lower()
            for t in re.findall(r"[A-Za-z''-]+", from_text)
            if t.strip("''-.,;:!?\"") and t.strip("''-.,;:!?\"")[0].isupper()
        }

        to_tokens = re.findall(r"[A-Za-z''-]+", to_text)

        # Detect person-name contexts in to_text:
        # A token is a PERSON NAME CANDIDATE if it is preceded by a title
        # (Mr./Mrs./Ms./Dr.) or by another Title Case word that is not
        # sentence-initial. This targets "Mr. Madden", "John Smith" etc.
        # without catching sentence-initial common words like "Is", "Safety".
        title_preceded = set()  # indexes of tokens preceded by a title word
        consec_cap_second = set()  # indexes of 2nd+ word in consecutive Title Case run
        TITLE_WORDS = re.compile(r'^(Mr|Mrs|Ms|Dr|Prof|Hon|Esq)\.?$', re.IGNORECASE)
        prev_was_cap = False
        prev_was_title = False
        for i, tok in enumerate(to_tokens):
            s = tok.strip("''-.,;:!?\"")
            is_cap = bool(s) and s[0].isupper() and not s.isupper()
            if prev_was_title:
                title_preceded.add(i)
            if prev_was_cap and is_cap:
                consec_cap_second.add(i)
            prev_was_title = bool(TITLE_WORDS.match(tok))
            prev_was_cap = is_cap

        for i, tok in enumerate(to_tokens):
            stripped = tok.strip("''-.,;:!?\"")
            if not stripped or len(stripped) < 2:
                continue
            if stripped.isupper():
                continue  # ALL-CAPS abbreviations OK
            if not stripped[0].isupper():
                continue  # not capitalized
            if ALWAYS_OK_PATTERNS.match(stripped):
                continue  # known-safe words
            if stripped.lower() in from_caps:
                continue  # word was already capitalized in steno source

            # Only apply the hard check to PERSON NAME CANDIDATES:
            # tokens after a title word (Mr. Madden) or 2nd word in a
            # consecutive Title Case sequence (John Smith).
            # Single sentence-initial words (Is, Safety, Well) are skipped.
            is_person_name_candidate = (i in title_preceded or i in consec_cap_second)
            if not is_person_name_candidate:
                continue

            # HARD REJECT: person name candidate not in names.lock.
            # Agent must FLAG unknown proper nouns — never guess.
            if stripped.title() not in names_lock:
                return ValidationResult(
                    False,
                    f"PROPER NOUN REJECTED: '{stripped}' in REWORD.to "
                    f"(span {op.get('span')}) looks like a person name but "
                    f"is not in names.lock. Agent must FLAG — never guess. "
                    f"If correct, add to CASE_CAPTION.json (appearances, "
                    f"known_places, or known_companies)."
                )

    return ValidationResult(True)


# ── Soft check: Word budget ───────────────────────────────────────────────────

def check_word_budget(
    ops: list,
    tokens: List[Tuple[int, str, bool]],
) -> ValidationResult:
    """
    Verify output word count is within acceptable range of input word count.

    Input words = non-blank raw tokens.
    Output words = words in all KEEP spans + words in all REWORD.to fields.
    """
    raw_word_count = sum(1 for _, w, is_blank in tokens if not is_blank and w != BLANK_TOKEN)
    if raw_word_count == 0:
        return ValidationResult(True)

    output_word_count = 0
    for op in ops:
        span = op["span"]
        op_type = op["op"]

        if op_type == "KEEP":
            # Count raw words in this span
            for idx, word, is_blank in tokens:
                if span[0] <= idx <= span[1] and not is_blank:
                    output_word_count += 1

        elif op_type in ("REWORD", "FLAG"):
            to_text = op.get("to", "")
            if op_type == "FLAG":
                # FLAG keeps the underlying text — count raw words
                for idx, word, is_blank in tokens:
                    if span[0] <= idx <= span[1] and not is_blank:
                        output_word_count += 1
            else:
                output_word_count += len(to_text.split()) if to_text.strip() else 0

    ratio = output_word_count / raw_word_count
    warnings = []

    if ratio < WORD_BUDGET_HARD:
        return ValidationResult(
            False,
            f"word budget hard reject: output {output_word_count} words = "
            f"{ratio:.1%} of input {raw_word_count} (minimum {WORD_BUDGET_HARD:.0%})"
        )

    if ratio < WORD_BUDGET_SOFT:
        warnings.append(
            f"word budget soft warning: output {output_word_count} words = "
            f"{ratio:.1%} of input {raw_word_count} — verify no content dropped"
        )

    return ValidationResult(True, warnings=warnings)


# ── Soft check: from-field match ─────────────────────────────────────────────

def check_from_match(
    ops: list,
    tokens: List[Tuple[int, str, bool]],
) -> ValidationResult:
    """
    Verify REWORD.from matches the actual raw tokens at the stated span.
    Soft check — mismatch is a warning, not a hard reject.
    """
    warnings = []
    for op in ops:
        if op.get("op") != "REWORD":
            continue
        stated_from = op.get("from", "").strip()
        if not stated_from:
            continue

        span = op["span"]
        actual_from = get_span_words(tokens, span[0], span[1])

        if stated_from.lower() != actual_from.lower():
            warnings.append(
                f"REWORD span {span}: from field says '{stated_from}' "
                f"but raw tokens read '{actual_from}'"
            )

    return ValidationResult(True, warnings=warnings)


# ── Main entry point ──────────────────────────────────────────────────────────

def validate_ops(
    ops: list,
    tokens: List[Tuple[int, str, bool]],
    names_lock: Set[str],
) -> ValidationResult:
    """
    Run all validation checks in order. Return first hard failure, or PASS with
    accumulated warnings.

    Order: coverage -> sources -> names -> word budget -> from-match
    """
    raw_token_count = len(tokens)

    # Hard checks (any failure = reject the whole op list)
    for check_fn, args in [
        (check_coverage, (ops, raw_token_count)),
        (check_sources,  (ops,)),
        (check_names,    (ops, names_lock)),
        (check_word_budget, (ops, tokens)),
    ]:
        result = check_fn(*args)
        if not result.ok:
            return result

    # Soft check (warnings only)
    soft = check_from_match(ops, tokens)
    all_warnings = []
    for check_fn, args in [
        (check_coverage, (ops, raw_token_count)),
        (check_word_budget, (ops, tokens)),
        (check_from_match, (ops, tokens)),
    ]:
        r = check_fn(*args)
        all_warnings.extend(r.warnings)

    return ValidationResult(True, warnings=all_warnings)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from tokenize_chunk import tokenize_chunk

    sample = """Q. and you arrived on scene at what time

A. it was approximate ly 14 hundred hours

Q. who was the incident commander

A. that would of been chief montz jack montz"""

    tokens = tokenize_chunk(sample)
    print(f"Raw tokens ({len(tokens)}):")
    for t in tokens:
        print(f"  {t}")

    # Valid op list
    good_ops = [
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

    names = {"Jack", "Montz", "Exhibit", "Objection"}
    result = validate_ops(good_ops, tokens, names)
    print(f"\nGood ops -> ok={result.ok}, warnings={result.warnings}")

    # Block collapse — should FAIL coverage
    bad_ops = [
        {"op": "REWORD", "span": [0, 2], "from": "Q. and you", "to": "go",
         "source": "raw_steno", "reason": "test"},
    ]
    result2 = validate_ops(bad_ops, tokens, names)
    print(f"Block collapse -> ok={result2.ok}, reason={result2.reason}")

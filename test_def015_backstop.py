"""
test_def015_backstop.py — Unit tests for def015_backstop.py
============================================================
Written BEFORE implementation. Per CODER_MINDSET: write the test, then the code.
All tests fail until def015_backstop.py exists and passes them.

Test corpus drawn from real Brandl 440-hit investigation (2026-04-18).
These are actual patterns observed in corrected_text.txt and FINAL_FORMATTED.txt,
not synthetic approximations.

USAGE:
    python test_def015_backstop.py          # run all tests
    python test_def015_backstop.py -v       # verbose (show paragraph text on failure)

EXIT: 0 = all pass, 1 = one or more failures
"""

import sys
import re

# ── Import the module under test ──────────────────────────────────────────────
# Will ImportError until def015_backstop.py exists — that's expected.
try:
    from def015_backstop import (
        split_paragraphs,
        detect_bleed,
        classify_hit,
        apply_fix,
        tag_paragraph,
        SELF_CORRECTION_RE,
        BleedHit,
    )
    IMPORT_OK = True
except ImportError as e:
    IMPORT_OK = False
    IMPORT_ERROR = str(e)

# ── Test runner ────────────────────────────────────────────────────────────────

VERBOSE = '-v' in sys.argv
results = []

def record(name, passed, detail=''):
    mark = 'PASS' if passed else 'FAIL'
    msg = f'  [{mark}]  {name}'
    if detail and (not passed or VERBOSE):
        msg += f'\n         {detail}'
    print(msg)
    results.append((name, passed))


def assert_eq(name, got, expected, detail=''):
    ok = got == expected
    record(name, ok, detail or f'expected {expected!r}, got {got!r}')


def assert_in(name, needle, haystack, detail=''):
    ok = needle in haystack
    record(name, ok, detail or f'{needle!r} not found in output')


def assert_not_in(name, needle, haystack, detail=''):
    ok = needle not in haystack
    record(name, ok, detail or f'{needle!r} unexpectedly found in output')


def assert_count(name, pattern, text, expected_count, detail=''):
    found = len(re.findall(pattern, text))
    ok = found == expected_count
    record(name, ok, detail or f'pattern {pattern!r}: expected {expected_count}, found {found}')


# ── Guard: import must succeed ────────────────────────────────────────────────

def test_import():
    record('import def015_backstop', IMPORT_OK,
           IMPORT_ERROR if not IMPORT_OK else '')


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 1: Mode A — run-on blob fragments (>=40 chars before stray label)
# These must be AUTO-SPLIT. No [REVIEW] tag in output.
# ═════════════════════════════════════════════════════════════════════════════

def test_mode_a_1():
    """
    Classic run-on: AI labeled turns but left them in one paragraph.
    Input from Brandl: long answer block where AI missed a turn boundary.
    Two turns only (A. opener + one stray Q.) -> Mode A -> auto-split.
    Expected: split into two paragraphs, no tag.
    """
    para = (
        "A.   That's the same thing as what I just described earlier in my testimony. "
        "Q. Okay. So I have just restated that differently than you did."
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_a_1: detect_bleed finds hits in run-on blob', len(hits) >= 1, f'hits={hits}')

    if hits:
        hit = hits[0]
        assert_eq('mode_a_1: first hit classified as Mode A', hit.mode, 'A')
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_a_1: no [REVIEW] tag in auto-fixed output', '[REVIEW-', result['text'])
        # Output must contain two separate Q./A. blocks
        paras_out = split_paragraphs(result['text'])
        record('mode_a_1: output has >=2 paragraphs after split',
               len(paras_out) >= 2, f'got {len(paras_out)} paragraphs')


def test_mode_a_2():
    """
    Run-on with two stray labels in sequence (chained within same blob).
    Not a 3-turn chain (only 2 stray labels, so 3 turns total including opener).
    Edge: chain detection must NOT trigger at exactly 2 stray labels (chain guard
    triggers at 3+ turns total = 2+ stray labels). Update: per spec §4.3 edge 1,
    3+ turns total = always tag. 2 stray labels = 3 turns total -> CHAIN -> tag.
    """
    para = (
        "A.   Yes, that is correct. "
        "Q. And the well was drilled in 2004? "
        "A. Correct, it was 2004."
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_a_2: detect_bleed finds >=2 hits in triple-turn blob', len(hits) >= 2, f'hits={hits}')
    # 3 turns total -> chain rule -> must tag, not auto-split
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('mode_a_2: chain -> [REVIEW] tag present', '[REVIEW-', result['text'])
        assert_eq('mode_a_2: chain -> action is tagged not split',
                  result['actions'][0]['action'], 'tagged')


def test_mode_a_3():
    """
    Long answer blob, one stray Q. deep in the paragraph (real Brandl pattern:
    dense reconstruction of stipulation block). Stray label has 80+ chars before it.
    Must auto-split.
    """
    para = (
        "A.   We have reviewed the title work and the production records and the "
        "operating agreements going back to 1987 and I am satisfied that the chain "
        "of title is clean. Q. And that review was completed before the closing date?"
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_a_3: detect_bleed hits long-prefix stray label', len(hits) == 1, f'hits={hits}')
    if hits:
        assert_eq('mode_a_3: classified Mode A (prefix >=40 chars)', hits[0].mode, 'A')
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_a_3: auto-fixed, no REVIEW tag', '[REVIEW-', result['text'])
        # Second paragraph must start with Q.
        paras_out = split_paragraphs(result['text'])
        record('mode_a_3: second paragraph starts with Q.',
               len(paras_out) >= 2 and paras_out[1].strip().startswith('Q.'),
               f'second para: {paras_out[1][:40] if len(paras_out) >= 2 else "missing"}')


def test_mode_a_4():
    """
    Run-on but no sentence terminator before the stray label — must demote to UNCERTAIN.
    Demonstrates the LOW confidence path.
    """
    para = (
        "A.   He was working on the platform at the time and the crew was "
        "also present Q. What time did the incident occur?"
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_a_4: detect_bleed fires on no-terminator run-on', len(hits) == 1, f'hits={hits}')
    if hits:
        assert_eq('mode_a_4: no terminator -> LOW confidence', hits[0].confidence, 'LOW')
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('mode_a_4: LOW confidence -> [REVIEW] tag', '[REVIEW-', result['text'])


def test_mode_a_5():
    """
    Stray label with first fragment < 10 chars after opening label — demote to UNCERTAIN.
    Edge: nearly-empty first turn.
    """
    para = "A.   Yes. Q. That is fine. A. Agreed."
    hits = detect_bleed(para, paragraph_index=0)
    # 3 turns total -> chain guard fires before mode classification
    record('mode_a_5: triple-turn triggers chain guard', len(hits) >= 2, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('mode_a_5: chain -> [REVIEW] tag', '[REVIEW-', result['text'])


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 2: Mode B safe — short interjections, clean punctuation -> AUTO-SPLIT
# ═════════════════════════════════════════════════════════════════════════════

def test_mode_b_safe_1():
    """
    Real Brandl hit: 'A.   Greenspoint. Q. Okay. Did your office ever have occasion'
    Short factual answer (city name + period) -> safe Mode B -> auto-split.
    """
    para = "A.   Greenspoint. Q. Okay. Did your office ever have occasion to do work"
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_safe_1: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        assert_eq('mode_b_safe_1: classified Mode B', hits[0].mode, 'B')
        assert_eq('mode_b_safe_1: safe -> HIGH or MEDIUM confidence',
                  hits[0].confidence in ('HIGH', 'MEDIUM'), True)
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_b_safe_1: auto-fixed, no REVIEW tag', '[REVIEW-', result['text'])
        paras_out = split_paragraphs(result['text'])
        record('mode_b_safe_1: splits into 2 paragraphs',
               len(paras_out) == 2, f'got {len(paras_out)}')
        record('mode_b_safe_1: first para is clean A. block',
               paras_out[0].strip() == 'A.   Greenspoint.',
               f'got: {paras_out[0].strip()!r}')


def test_mode_b_safe_2():
    """
    Real Brandl hit: 'A.   Yes. Q. Okay. The way I look at it'
    Affirmative + period -> safe Mode B.
    """
    para = "A.   Yes. Q. Okay. The way I look at it, the agreement was clear."
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_safe_2: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        assert_eq('mode_b_safe_2: classified Mode B', hits[0].mode, 'B')
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_b_safe_2: auto-fixed, no REVIEW tag', '[REVIEW-', result['text'])


def test_mode_b_safe_3():
    """
    'A.   Correct. Q. For example, a well that was drilled in 2002'
    Acknowledgment with period -> safe Mode B.
    """
    para = "A.   Correct. Q. For example, a well that was drilled in 2002."
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_safe_3: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_b_safe_3: auto-fixed', '[REVIEW-', result['text'])


def test_mode_b_safe_4():
    """
    'A.   No. Q. Are you sure about that?'
    Negative with period -> safe Mode B.
    """
    para = "A.   No. Q. Are you sure about that?"
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_safe_4: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_b_safe_4: auto-fixed', '[REVIEW-', result['text'])


def test_mode_b_safe_5():
    """
    'A.   2004. Q. And the work was completed in 2004?'
    Short year answer + period -> safe Mode B (short-factual pattern).
    """
    para = "A.   2004. Q. And the work was completed in that same year?"
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_safe_5: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('mode_b_safe_5: short year answer auto-fixed', '[REVIEW-', result['text'])


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 3: Mode B uncertain — should produce [REVIEW] tags, no auto-split
# ═════════════════════════════════════════════════════════════════════════════

def test_mode_b_uncertain_1():
    """
    Real Brandl hit (Mode B uncertain): 'A.   Uh-huh Q. Describe their period of ownership'
    No terminal punctuation after 'Uh-huh' -> uncertain -> tag.
    """
    para = "A.   Uh-huh Q. Describe their period of ownership from the acquisition."
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_uncertain_1: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        assert_eq('mode_b_uncertain_1: classified Mode B', hits[0].mode, 'B')
        assert_eq('mode_b_uncertain_1: no terminator -> LOW confidence',
                  hits[0].confidence, 'LOW')
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('mode_b_uncertain_1: [REVIEW] tag present', '[REVIEW-', result['text'])
        assert_eq('mode_b_uncertain_1: action is tagged',
                  result['actions'][0]['action'], 'tagged')


def test_mode_b_uncertain_2():
    """
    Fragment ending with preposition — incomplete sentence.
    'A.   Year-and-a-half, till 2006. Q. Okay.'
    Has terminator but comma-heavy phrasing makes it borderline.
    Implementation should tag this (conservative rule).
    """
    para = "A.   Year-and-a-half, till 2006. Q. Okay. Did they continue after that?"
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_uncertain_2: detect_bleed fires', len(hits) >= 1, f'hits={hits}')
    # This one is explicitly "slightly ambiguous" per spec §4.2 — implementation
    # may classify as safe or uncertain. Test: if uncertain, REVIEW tag present.
    # If safe, output has 2 clean paragraphs. Either is acceptable — just no crash.
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        record('mode_b_uncertain_2: output is non-empty string',
               bool(result['text'].strip()))


def test_mode_b_uncertain_3():
    """
    Answer ends with a conjunction — clear fragment, must tag.
    'A.   We were working on the well and Q. When exactly did you arrive?'
    """
    para = "A.   We were working on the well and Q. When exactly did you arrive?"
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_uncertain_3: detect_bleed fires on conjunction-end', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('mode_b_uncertain_3: fragment ending -> [REVIEW] tag', '[REVIEW-', result['text'])


def test_mode_b_uncertain_4():
    """
    Answer is fewer than 3 words with no terminator — must tag.
    'A.   Mm-hmm Q. So you agree with that statement?'
    """
    para = "A.   Mm-hmm Q. So you agree with that statement?"
    hits = detect_bleed(para, paragraph_index=0)
    record('mode_b_uncertain_4: detect_bleed fires', len(hits) >= 1, f'hits={hits}')
    if hits:
        assert_in('mode_b_uncertain_4: no terminator -> [REVIEW] tag',
                  '[REVIEW-', apply_fix(para, hits, tag_counter_start=1)['text'])


def test_mode_b_uncertain_5():
    """
    Tag counter increments correctly across multiple paragraphs.
    Two uncertain hits: first gets REVIEW-003, second gets REVIEW-004 (counter_start=3).
    """
    para1 = "A.   Uh-huh Q. First question about ownership."
    para2 = "A.   Mm-hmm Q. Second question about the well."
    hits1 = detect_bleed(para1, paragraph_index=0)
    hits2 = detect_bleed(para2, paragraph_index=1)
    record('mode_b_uncertain_5: both paragraphs have hits',
           len(hits1) >= 1 and len(hits2) >= 1)
    if hits1 and hits2:
        r1 = apply_fix(para1, hits1, tag_counter_start=3)
        r2 = apply_fix(para2, hits2, tag_counter_start=r1['next_counter'])
        assert_in('mode_b_uncertain_5: first tag is REVIEW-003', '[REVIEW-003:', r1['text'])
        assert_in('mode_b_uncertain_5: second tag is REVIEW-004', '[REVIEW-004:', r2['text'])


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 4: Self-correction guard — MUST NOT split or tag (Prime Directive)
# ═════════════════════════════════════════════════════════════════════════════

def test_self_correction_1():
    """
    Classic self-correction: 'A. It was 2004 — no, 2005. Q. Are you sure?'
    The dash + 'no,' is the self-correction marker. Entire paragraph must be EXEMPT.
    No split, no tag. PoW action = 'exempt_self_correction'.
    """
    para = "A.   It was 2004 — no, 2005. Q. Are you sure about that date?"
    hits = detect_bleed(para, paragraph_index=0)
    # Detector may or may not find hits — self-correction guard fires in apply_fix
    result = apply_fix(para, hits or [], tag_counter_start=1)
    assert_not_in('self_correction_1: no [REVIEW] tag', '[REVIEW-', result['text'])
    record('self_correction_1: paragraph text unchanged',
           result['text'].strip() == para.strip(),
           f'expected unchanged, got: {result["text"][:80]!r}')
    if result['actions']:
        assert_eq('self_correction_1: action is exempt_self_correction',
                  result['actions'][0]['action'], 'exempt_self_correction')


def test_self_correction_2():
    """
    'A.   The meeting was on Thursday — wait, actually it was Friday. Q. Are you certain?'
    'wait' and 'actually' are both in the self-correction token list.
    """
    para = (
        "A.   The meeting was on Thursday — wait, actually it was Friday. "
        "Q. Are you certain about that?"
    )
    result = apply_fix([], [], tag_counter_start=1)  # dummy to check RE first
    # Primary: verify SELF_CORRECTION_RE fires on this text
    match = SELF_CORRECTION_RE.search(para)
    record('self_correction_2: SELF_CORRECTION_RE matches "— wait"', match is not None,
           f'pattern did not match: {para[:80]!r}')
    # Full pipeline check
    hits = detect_bleed(para, paragraph_index=0)
    result = apply_fix(para, hits or [], tag_counter_start=1)
    assert_not_in('self_correction_2: no [REVIEW] tag', '[REVIEW-', result['text'])
    record('self_correction_2: paragraph unchanged',
           result['text'].strip() == para.strip())


def test_self_correction_3():
    """
    'A.   I believe it was Section A — scratch that, Section B of the agreement.'
    'scratch that' in self-correction list. Real legal transcript pattern.
    """
    para = (
        "A.   I believe it was Section A — scratch that, Section B of the agreement. "
        "Q. So Section B is the controlling provision?"
    )
    match = SELF_CORRECTION_RE.search(para)
    record('self_correction_3: SELF_CORRECTION_RE matches "— scratch that"',
           match is not None)
    hits = detect_bleed(para, paragraph_index=0)
    result = apply_fix(para, hits or [], tag_counter_start=1)
    assert_not_in('self_correction_3: no [REVIEW] tag', '[REVIEW-', result['text'])
    record('self_correction_3: paragraph unchanged',
           result['text'].strip() == para.strip())


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 5: Interrupted questions with em-dash -> auto-split
# ═════════════════════════════════════════════════════════════════════════════

def test_interrupted_q_1():
    """
    'Q. And did you — A. Yes.'
    Em-dash precedes stray A. label -> auto-split.
    First paragraph keeps the fragment + dash. Second paragraph is 'A.   Yes.'
    """
    para = "Q.   And did you — A. Yes, I was present at the time."
    hits = detect_bleed(para, paragraph_index=0)
    record('interrupted_q_1: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('interrupted_q_1: em-dash trigger -> no [REVIEW] tag',
                      '[REVIEW-', result['text'])
        paras_out = split_paragraphs(result['text'])
        record('interrupted_q_1: splits into 2 paragraphs',
               len(paras_out) == 2, f'got {len(paras_out)}')
        record('interrupted_q_1: second para starts with A.',
               len(paras_out) >= 2 and paras_out[1].strip().startswith('A.'),
               f'second para: {paras_out[1][:40] if len(paras_out) >= 2 else "missing"}')


def test_interrupted_q_2():
    """
    Double-hyphen variant: 'Q. Did you ever see -- A. No, never.'
    Double-hyphen (--) is also a valid interrupt trigger.
    """
    para = "Q.   Did you ever see -- A. No, never, not once."
    hits = detect_bleed(para, paragraph_index=0)
    record('interrupted_q_2: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('interrupted_q_2: double-hyphen trigger -> no [REVIEW] tag',
                      '[REVIEW-', result['text'])
        paras_out = split_paragraphs(result['text'])
        record('interrupted_q_2: splits into 2 paragraphs',
               len(paras_out) == 2, f'got {len(paras_out)}')


def test_interrupted_q_no_dash():
    """
    Stray A. mid-question WITHOUT a dash — must NOT auto-split.
    Should tag instead (ambiguous: could be a bleed, could be legitimate steno artifact).
    'Q. Did you ever work for the company A. No I did not.'
    No dash -> UNCERTAIN -> tag.
    """
    para = "Q.   Did you ever work for the company A. No, I did not."
    hits = detect_bleed(para, paragraph_index=0)
    record('interrupted_q_no_dash: detect_bleed finds hit', len(hits) >= 1, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('interrupted_q_no_dash: no dash -> [REVIEW] tag', '[REVIEW-', result['text'])


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 6: Chained exchanges (3+ turns) — must TAG, never auto-split
# ═════════════════════════════════════════════════════════════════════════════

def test_chain_1():
    """
    3-turn chain: A opener + 2 stray labels.
    'A. Yes. Q. And? A. No.'
    Per spec §4.3 edge 1: always tag, never chain-split.
    """
    para = "A.   Yes. Q. And did that apply? A. No, it did not apply in this case."
    hits = detect_bleed(para, paragraph_index=0)
    record('chain_1: detect_bleed finds >=2 hits (3-turn chain)', len(hits) >= 2, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_in('chain_1: chain -> [REVIEW] tag present', '[REVIEW-', result['text'])
        record('chain_1: only ONE tag inserted (at first stray label)',
               result['text'].count('[REVIEW-') == 1,
               f'found {result["text"].count("[REVIEW-")} tags')
        assert_eq('chain_1: action is tagged (not split)',
                  result['actions'][0]['action'], 'tagged')


def test_chain_2():
    """
    4-turn chain: 'A. Yes. Q. Really? A. Yes. Q. Okay.'
    Still tags once at the first stray label. No recursive split attempt.
    """
    para = (
        "A.   Yes, that is correct. "
        "Q. Really? "
        "A. Yes, absolutely. "
        "Q. Okay. Let me move on."
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('chain_2: detect_bleed finds >=3 hits (4-turn chain)', len(hits) >= 3, f'hits={hits}')
    if hits:
        result = apply_fix(para, hits, tag_counter_start=5)
        assert_in('chain_2: [REVIEW-005] tag present', '[REVIEW-005:', result['text'])
        record('chain_2: only one tag for the whole chain',
               result['text'].count('[REVIEW-') == 1)


def test_chain_3():
    """
    Chain guard: 2 turns only (opener + 1 stray label) = NOT a chain.
    Must be evaluated as Mode A or B normally, not forced to chain-tag path.
    """
    para = "A.   That is correct. Q. And do you have documentation for that claim?"
    hits = detect_bleed(para, paragraph_index=0)
    record('chain_3: detect_bleed finds exactly 1 hit (2 turns, not a chain)',
           len(hits) == 1, f'hits={hits}')
    if hits:
        # 2 turns = not a chain. Should be Mode B safe (period after "correct").
        result = apply_fix(para, hits, tag_counter_start=1)
        assert_not_in('chain_3: 2-turn paragraph is NOT chain-tagged', '[REVIEW-', result['text'])


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 7: False positive guards — must NOT fire on legitimate text
# ═════════════════════════════════════════════════════════════════════════════

def test_fp_exhibit_a():
    """
    'Please refer to Exhibit A. The document shows the chain of title.'
    'A.' here is an exhibit reference, not a speaker label.
    No bleed hit should be generated.
    """
    para = "Q.   Please refer to Exhibit A. The document shows the chain of title."
    hits = detect_bleed(para, paragraph_index=0)
    record('fp_exhibit_a: no hit on Exhibit A. reference', len(hits) == 0,
           f'got hits: {hits}')


def test_fp_qed():
    """
    'Q.E.D.' must not trigger the Q. detector.
    """
    para = "A.   The proof is complete, Q.E.D., as we demonstrated in the earlier exhibit."
    hits = detect_bleed(para, paragraph_index=0)
    record('fp_qed: no hit on Q.E.D.', len(hits) == 0, f'got hits: {hits}')


def test_fp_clean_paragraph():
    """
    A normal, well-formed Q. paragraph with no bleed.
    Must produce zero hits.
    """
    para = (
        "Q.   Can you describe for the jury what your role was at the company "
        "during the period from 2001 through 2006?"
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('fp_clean_q: no hit on clean Q. paragraph', len(hits) == 0, f'got hits: {hits}')


def test_fp_clean_a():
    """
    A normal, well-formed A. paragraph. Zero hits.
    """
    para = (
        "A.   My role was as a petroleum engineer responsible for overseeing "
        "drilling operations on the outer continental shelf."
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('fp_clean_a: no hit on clean A. paragraph', len(hits) == 0, f'got hits: {hits}')


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 8: Proof of Work output structure
# ═════════════════════════════════════════════════════════════════════════════

def test_pow_fix_structure():
    """
    Auto-fix produces a PoW action entry with required fields.
    """
    para = "A.   Yes. Q. And do you confirm that statement?"
    hits = detect_bleed(para, paragraph_index=7)
    if not hits:
        record('pow_fix_structure: no hits found — skip', True, 'no hits to test')
        return
    result = apply_fix(para, hits, tag_counter_start=1)
    required_fields = {'fix_id', 'mode', 'confidence', 'action',
                       'paragraph_index', 'input_text', 'split_reason'}
    if result['actions']:
        action = result['actions'][0]
        missing = required_fields - set(action.keys())
        record('pow_fix_structure: all required PoW fields present',
               len(missing) == 0, f'missing: {missing}')


def test_pow_tag_structure():
    """
    Tag action produces a PoW entry with required fields.
    """
    para = "A.   Uh-huh Q. Can you explain what happened next?"
    hits = detect_bleed(para, paragraph_index=12)
    if not hits:
        record('pow_tag_structure: no hits found — skip', True)
        return
    result = apply_fix(para, hits, tag_counter_start=1)
    required_fields = {'tag_id', 'mode', 'confidence', 'action',
                       'paragraph_index', 'input_text', 'tag_reason', 'stray_label'}
    if result['actions']:
        action = result['actions'][0]
        missing = required_fields - set(action.keys())
        record('pow_tag_structure: all required PoW tag fields present',
               len(missing) == 0, f'missing: {missing}')


def test_pow_exempt_structure():
    """
    Exempt (self-correction) action produces a PoW entry with action='exempt_self_correction'.
    """
    para = "A.   It was March — no, April of 2005. Q. Are you certain?"
    hits = detect_bleed(para, paragraph_index=3)
    result = apply_fix(para, hits or [], tag_counter_start=1)
    if result['actions']:
        assert_eq('pow_exempt_structure: exempt action type',
                  result['actions'][0]['action'], 'exempt_self_correction')
    else:
        # Self-correction guard may suppress hit before apply_fix sees it
        record('pow_exempt_structure: paragraph unchanged (guard fired pre-fix)',
               result['text'].strip() == para.strip())


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 9: Caption-block guard — paragraphs that don't open with Q./A. must be
# returned untouched. No splits, no tags, no hits.
# ═════════════════════════════════════════════════════════════════════════════

def test_caption_block_real_para12():
    """
    Real Brandl para 12: law firm caption header.
    Contains Q. and A. tokens embedded in attorney names / addresses,
    but the paragraph does NOT open with a Q. or A. label.
    Must be returned completely untouched — no hit, no tag, no split.
    """
    para = (
        "ATTORNEY FOR PLAINTIFF: SHER GARNER CAHILL RICHTER KLEIN & HILBERT, L.L.C. "
        "909 Poydras Street Suite 2800 New Orleans, Louisiana 70112 Q. TREY PEACOCK, ESQ. "
        "A. ATTORNEY FOR DEFENDANT: FRILOT L.L.C. 1100 Poydras Street Suite 3700 "
        "New Orleans, Louisiana 70163 Q. KEVIN R. TULLY, ESQ."
    )
    hits = detect_bleed(para, paragraph_index=12)
    record('caption_block_real: detect_bleed returns no hits', len(hits) == 0,
           f'got {len(hits)} hits — caption block incorrectly processed')

    result = apply_fix(para, hits, tag_counter_start=1)
    assert_not_in('caption_block_real: no [REVIEW] tag in output', '[REVIEW-', result['text'])
    record('caption_block_real: paragraph text unchanged',
           result['text'].strip() == para.strip(),
           f'paragraph was modified — should be untouched')


def test_caption_block_colloquy_only():
    """
    Fabricated colloquy-only paragraph: MR. SMITH: We have no Q. about this.
    The Q. appears inside a sentence, not as an opening speaker label.
    Paragraph opens with MR. SMITH:, not Q. or A.
    Must be returned completely untouched.
    """
    para = "MR. SMITH: We have no Q. about this matter. A. It is stipulated."
    hits = detect_bleed(para, paragraph_index=0)
    record('caption_colloquy: detect_bleed returns no hits on MR. X: paragraph',
           len(hits) == 0,
           f'got {len(hits)} hits — colloquy-only paragraph incorrectly processed')

    result = apply_fix(para, hits, tag_counter_start=1)
    assert_not_in('caption_colloquy: no [REVIEW] tag', '[REVIEW-', result['text'])
    record('caption_colloquy: paragraph unchanged',
           result['text'].strip() == para.strip())


def test_caption_block_whereupon():
    """
    (Whereupon, ...) parenthetical — structural, not Q./A.
    No Q./A. opener. Must pass through untouched even if Q. or A. appear inside.
    """
    para = "(Whereupon, Exhibit Q. was marked for identification.)"
    hits = detect_bleed(para, paragraph_index=0)
    record('caption_whereupon: no hits on Whereupon block', len(hits) == 0,
           f'got {len(hits)} hits')
    result = apply_fix(para, hits, tag_counter_start=1)
    record('caption_whereupon: paragraph unchanged',
           result['text'].strip() == para.strip())


def test_caption_block_qa_opener_still_processed():
    """
    Sanity check: a paragraph that DOES open with Q. must still be processed normally.
    This test ensures the guard doesn't accidentally silence legitimate Q. blocks.
    """
    para = "Q.   Are you the attorney of record? A. Yes, I represent the plaintiff."
    hits = detect_bleed(para, paragraph_index=0)
    record('caption_qa_opener: Q. opener is still detected', len(hits) >= 1,
           f'Q.-opening paragraph got 0 hits -- guard too aggressive')


# =============================================================================
# GROUP 10: R3 verify-tag guard — open-bracket-colon format [REVIEW: ...]
# Bug: VERIFY_TAG_RE matched close-bracket forms only (REVIEW], [[REVIEW]]).
# The verify agent writes [REVIEW: reason text] (open-bracket-colon, no close
# bracket before the reason). R3 was a dead guard until this fix.
# =============================================================================

def test_r3_open_bracket_colon_real_brandl():
    """
    Real Brandl para 79 pattern: Q.-opening paragraph with verify-agent tag in
    the format [REVIEW: verify-agent flag ? reason text ? reporter confirm].
    Paragraph also contains stray speaker labels (genuine chain bleed).
    R3 guard must catch it and return [] — paragraph untouched.
    """
    # Exact format from Brandl corrected_text.txt para 79
    para = (
        "Q.   All right, Mr. Brandl, we were talking about your work. "
        "You're [REVIEW: verify-agent flag ? extensive reconstruction with insertions; "
        "multiple steno gaps without audio confirmation ? reporter confirm] "
        "currently doing consulting work. A. Yes, that is correct. "
        "Q. Let me go back to your background."
    )
    hits = detect_bleed(para, paragraph_index=79)
    record('r3_open_bracket_real: detect_bleed returns [] for [REVIEW: ...] paragraph',
           len(hits) == 0,
           f'got {len(hits)} hits -- R3 guard not catching open-bracket-colon format')
    result = apply_fix(para, hits, tag_counter_start=1)
    assert_not_in('r3_open_bracket_real: no [REVIEW-NNN] backstop tag inserted', '[REVIEW-', result['text'])
    record('r3_open_bracket_real: paragraph text unchanged',
           result['text'].strip() == para.strip())


def test_r3_open_bracket_colon_fabricated():
    """
    Fabricated paragraph with short [REVIEW: reason] tag plus stray label.
    Tests the minimal case: any [REVIEW: followed by content must trigger R3.
    """
    para = (
        "A.   The well was drilled in 2004. [REVIEW: possible date error -- "
        "reporter verify] Q. And was it completed in the same year?"
    )
    hits = detect_bleed(para, paragraph_index=0)
    record('r3_fabricated: detect_bleed returns [] for fabricated [REVIEW: ...] paragraph',
           len(hits) == 0,
           f'got {len(hits)} hits -- R3 not catching short open-bracket-colon tag')
    result = apply_fix(para, hits, tag_counter_start=1)
    record('r3_fabricated: paragraph unchanged',
           result['text'].strip() == para.strip())


def test_r3_old_formats_still_caught():
    """
    Regression: the old close-bracket and double-bracket formats that VERIFY_TAG_RE
    originally caught must still be caught after adding the new alternation.
    Tests: [FLAG:], REVIEW], [[REVIEW]], [REVIEW-001:
    """
    flag_para = "A.   [FLAG: steno artifact -- verify] This testimony was reconstructed. Q. Okay."
    review_close = "A.   Some testimony here. REVIEW] Q. And then what happened?"
    review_double = "A.   [[REVIEW]] This block needs reporter review. Q. Moving on."
    review_numbered = "A.   [REVIEW-001: possible turn break] Q. Did you confirm that?"

    for label, para in [
        ('FLAG format', flag_para),
        ('REVIEW] close-bracket', review_close),
        ('[[REVIEW]] double-bracket', review_double),
        ('[REVIEW-001: numbered tag', review_numbered),
    ]:
        hits = detect_bleed(para, paragraph_index=0)
        record(f'r3_regression {label}: returns [] (R3 catches it)',
               len(hits) == 0,
               f'got {len(hits)} hits -- regression: {label} no longer caught by R3')


# ═════════════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════════════

def run_all():
    print('\n-- test_def015_backstop.py -----------------------------------------\n')
    test_import()

    if not IMPORT_OK:
        print('\n  [BLOCKED] Cannot run tests — import failed. Build def015_backstop.py first.\n')
        sys.exit(1)

    print('\nGroup 1: Mode A — run-on blob fragments (auto-split)')
    test_mode_a_1()
    test_mode_a_2()
    test_mode_a_3()
    test_mode_a_4()
    test_mode_a_5()

    print('\nGroup 2: Mode B safe — short interjections (auto-split)')
    test_mode_b_safe_1()
    test_mode_b_safe_2()
    test_mode_b_safe_3()
    test_mode_b_safe_4()
    test_mode_b_safe_5()

    print('\nGroup 3: Mode B uncertain — should produce [REVIEW] tags')
    test_mode_b_uncertain_1()
    test_mode_b_uncertain_2()
    test_mode_b_uncertain_3()
    test_mode_b_uncertain_4()
    test_mode_b_uncertain_5()

    print('\nGroup 4: Self-correction guard (Prime Directive — never split)')
    test_self_correction_1()
    test_self_correction_2()
    test_self_correction_3()

    print('\nGroup 5: Interrupted questions with em-dash (auto-split)')
    test_interrupted_q_1()
    test_interrupted_q_2()
    test_interrupted_q_no_dash()

    print('\nGroup 6: Chained exchanges 3+ turns (tag only, never split)')
    test_chain_1()
    test_chain_2()
    test_chain_3()

    print('\nGroup 7: False positive guards (no hits on clean text)')
    test_fp_exhibit_a()
    test_fp_qed()
    test_fp_clean_paragraph()
    test_fp_clean_a()

    print('\nGroup 8: Proof of Work output structure')
    test_pow_fix_structure()
    test_pow_tag_structure()
    test_pow_exempt_structure()

    print('\nGroup 9: Caption-block guard (no Q./A. opener = untouched)')
    test_caption_block_real_para12()
    test_caption_block_colloquy_only()
    test_caption_block_whereupon()
    test_caption_block_qa_opener_still_processed()

    print('\nGroup 10: R3 verify-tag guard -- open-bracket-colon [REVIEW: ...] format')
    test_r3_open_bracket_colon_real_brandl()
    test_r3_open_bracket_colon_fabricated()
    test_r3_old_formats_still_caught()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    failed = total - passed
    print(f'\n-- {passed}/{total} passed  {"OK" if failed == 0 else str(failed) + " FAILED"} -----\n')
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    run_all()

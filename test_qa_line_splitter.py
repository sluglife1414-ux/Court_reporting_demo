"""
test_qa_line_splitter.py — Test suite for qa_line_splitter.py
All tests must pass before pipeline wiring.
"""

import pytest
from qa_line_splitter import split_line, process_lines, mask_brackets, count_boundaries

# ---------------------------------------------------------------------------
# RCA fixture — exact line 620 from chunk_02 corrected_text.txt
# ---------------------------------------------------------------------------
RCA_LINE = (
    'Q. Were they in Houston? [REVIEW-031: possible turn break] '
    'A. Were they in Houston? Q. They were -- Denver? A. Denver. '
    'Q. Okay. What were -- what were you doing there? Working consulting? '
    'A. Working well site, primarily completing wells, doing workovers. '
    'Q. Particular geographic location? A. Southeast Texas, Southwest Louisiana. '
    'Q. Were you involved mostly with drilling operations or something else with Aspect Resources? '
    'A. Involved in drilling operations. Q. What were you involved in? '
    'A. Production. [REVIEW: verify-agent flag — Extensive multi-speaker reconstruction '
    'with steno duplication cleanup — reporter confirm]'
)

RCA_EXPECTED = [
    'Q. Were they in Houston? [REVIEW-031: possible turn break] ',
    'A. Were they in Houston? ',
    'Q. They were -- Denver? ',
    'A. Denver. ',
    'Q. Okay. What were -- what were you doing there? Working consulting? ',
    'A. Working well site, primarily completing wells, doing workovers. ',
    'Q. Particular geographic location? ',
    'A. Southeast Texas, Southwest Louisiana. ',
    'Q. Were you involved mostly with drilling operations or something else with Aspect Resources? ',
    'A. Involved in drilling operations. ',
    'Q. What were you involved in? ',
    'A. Production. [REVIEW: verify-agent flag — Extensive multi-speaker reconstruction '
    'with steno duplication cleanup — reporter confirm]',
]


# ---------------------------------------------------------------------------
# mask_brackets
# ---------------------------------------------------------------------------

class TestMaskBrackets:
    def test_masks_review_tag(self):
        line = 'Q. Foo? [REVIEW-031: possible turn break] A. Bar.'
        masked, ph = mask_brackets(line)
        assert '[REVIEW-031' not in masked
        assert len(ph) == 1

    def test_masks_verify_flag(self):
        line = 'A. Something. [REVIEW: verify-agent flag — details] Q. Next?'
        masked, ph = mask_brackets(line)
        assert 'verify-agent' not in masked
        assert len(ph) == 1

    def test_no_brackets_unchanged(self):
        line = 'Q. Simple question? A. Simple answer.'
        masked, ph = mask_brackets(line)
        assert masked == line
        assert ph == {}

    def test_multiple_brackets(self):
        line = '[REVIEW-001: foo] A. Yes. [REVIEW-002: bar] Q. Next?'
        masked, ph = mask_brackets(line)
        assert len(ph) == 2
        assert '[REVIEW-001' not in masked
        assert '[REVIEW-002' not in masked


# ---------------------------------------------------------------------------
# Basic split behavior
# ---------------------------------------------------------------------------

class TestSplitLine:
    def test_basic_two_turn_split(self):
        line = 'Q. What is your name? A. John Smith.'
        result = split_line(line)
        assert len(result) == 2
        # Trailing space preserved per spec (space before A. boundary becomes trailing)
        assert result[0].rstrip() == 'Q. What is your name?'
        assert result[1] == 'A. John Smith.'

    def test_three_turn_split(self):
        line = 'Q. Yes or no? A. Yes. Q. Why?'
        result = split_line(line)
        assert len(result) == 3
        assert result[0].startswith('Q.')
        assert result[1].startswith('A.')
        assert result[2].startswith('Q.')

    def test_single_turn_unchanged(self):
        line = 'Q. Just one question here with no collapse.'
        result = split_line(line)
        assert result == [line]

    def test_single_answer_unchanged(self):
        line = 'A. Just one answer here.'
        result = split_line(line)
        assert result == [line]

    def test_empty_line_unchanged(self):
        result = split_line('')
        assert result == ['']

    def test_blank_line_unchanged(self):
        result = split_line('   ')
        assert result == ['   ']

    def test_rca_line_620(self):
        result = split_line(RCA_LINE)
        assert len(result) == 12
        # Verify each expected fragment is present (stripped for comparison)
        for i, expected in enumerate(RCA_EXPECTED):
            assert result[i].rstrip() == expected.rstrip(), \
                f'Fragment {i} mismatch:\n  got:      {result[i]!r}\n  expected: {expected!r}'

    def test_review_tag_preserved_in_fragment(self):
        line = 'Q. Foo? [REVIEW-031: possible turn break] A. Bar.'
        result = split_line(line)
        assert len(result) == 2
        assert '[REVIEW-031: possible turn break]' in result[0]
        assert result[1].startswith('A.')

    def test_verify_flag_preserved_in_last_fragment(self):
        line = 'Q. First? A. Second. [REVIEW: verify-agent flag — details]'
        result = split_line(line)
        assert len(result) == 2
        assert '[REVIEW: verify-agent flag — details]' in result[1]

    def test_review_tag_qa_inside_bracket_not_split(self):
        # Q. and A. inside a bracket must NOT trigger a split
        line = 'Q. Foo? [REVIEW-005: Q. internal note A. something] A. Bar.'
        result = split_line(line)
        # Should split into 2, not 4
        assert len(result) == 2
        assert '[REVIEW-005: Q. internal note A. something]' in result[0]


# ---------------------------------------------------------------------------
# Must NOT split
# ---------------------------------------------------------------------------

class TestNoSplitCases:
    def test_mr_name_not_split(self):
        line = 'A. I work for Mr. Smith at the firm.'
        result = split_line(line)
        assert result == [line]

    def test_dr_name_not_split(self):
        line = 'A. Dr. Jones examined the patient.'
        result = split_line(line)
        assert result == [line]

    def test_mrs_not_split(self):
        line = 'A. Mrs. Henderson was present.'
        result = split_line(line)
        assert result == [line]

    def test_decimal_not_split(self):
        line = 'A. The rate was 2.5 percent per year.'
        result = split_line(line)
        assert result == [line]

    def test_esq_not_split(self):
        line = 'BY: J. HOKE PEACOCK, ESQ. appearing for Westlake.'
        result = split_line(line)
        assert result == [line]

    def test_attorney_colloquy_not_split(self):
        # MR. MADIGAN: lines should not split
        line = 'MR. MADIGAN: Objection to the form of the question.'
        result = split_line(line)
        assert result == [line]

    def test_ms_attorney_not_split(self):
        line = 'MS. HANDY: We reserve all rights.'
        result = split_line(line)
        assert result == [line]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_idempotent_basic(self):
        line = 'Q. What is your name? A. John Smith.'
        first_pass  = split_line(line)
        second_pass = []
        for frag in first_pass:
            second_pass.extend(split_line(frag))
        assert first_pass == second_pass

    def test_idempotent_rca_line(self):
        first_pass  = split_line(RCA_LINE)
        second_pass = []
        for frag in first_pass:
            second_pass.extend(split_line(frag))
        assert first_pass == second_pass

    def test_idempotent_three_turn(self):
        line = 'Q. Yes or no? A. Yes. Q. Why? A. Because.'
        first_pass  = split_line(line)
        second_pass = []
        for frag in first_pass:
            second_pass.extend(split_line(frag))
        assert first_pass == second_pass


# ---------------------------------------------------------------------------
# process_lines (full file processor)
# ---------------------------------------------------------------------------

class TestProcessLines:
    def test_blank_lines_preserved(self):
        lines = ['Q. Foo? A. Bar.\n', '\n', 'A. Standalone.\n']
        out, n_split, warns = process_lines(lines)
        assert '\n' in out
        assert n_split == 1

    def test_single_turn_lines_pass_through(self):
        lines = ['Q. One question.\n', 'A. One answer.\n']
        out, n_split, warns = process_lines(lines)
        assert n_split == 0
        assert out == lines

    def test_split_count_accurate(self):
        # Per spec: count >= 2 boundaries → split. A single-turn line has 1 boundary.
        lines = [
            'Q. First? A. Yes. Q. Second? A. No.\n',  # 4 boundaries → split
            'Q. Third and only question.\n',           # 1 boundary → no split
            'Q. Fourth? A. Definitely. Q. Fifth?\n',   # 3 boundaries → split
        ]
        out, n_split, warns = process_lines(lines)
        assert n_split == 2  # lines 1 and 3 split, line 2 not

    def test_output_line_count_increases(self):
        lines = ['Q. A? A. B. Q. C? A. D.\n']
        out, n_split, warns = process_lines(lines)
        assert len(out) == 4
        assert n_split == 1

    def test_no_content_lost(self):
        lines = [RCA_LINE + '\n']
        out, n_split, warns = process_lines(lines)
        combined = ''.join(frag.rstrip('\n') for frag in out)
        # Every word from original should be in output (order preserved)
        assert 'Were they in Houston?' in combined
        assert 'Denver' in combined
        assert 'Southeast Texas' in combined
        assert 'steno duplication cleanup' in combined

    def test_process_lines_idempotent(self):
        lines = [RCA_LINE + '\n', '\n', 'Q. Simple?\n']
        out1, _, _ = process_lines(lines)
        out2, n2, _ = process_lines(out1)
        assert out1 == out2
        assert n2 == 0  # second pass splits nothing

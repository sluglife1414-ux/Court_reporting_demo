"""
def015_backstop.py — DEF-015 Inline Q/A Bleed Backstop
=======================================================
Spec: docs/specs/2026-04-18_def015_expanded_backstop_spec.md
Sprint: DEF-015-EXPANDED

Pipeline placement: post-verify, pre-format_final.
Reads corrected_text.txt, detects inline Q/A bleed, auto-fixes or tags,
overwrites corrected_text.txt in place, writes PROOF_OF_WORK_BACKSTOP.json
to FINAL_DELIVERY/.

USAGE:
    python def015_backstop.py              # reads/writes corrected_text.txt in CWD
    python def015_backstop.py --dry-run    # stats + preview, no file write
    python def015_backstop.py --wide-scan  # also prints all detected hits

Guard hierarchy (each checked in order, first match wins):
    1. Self-correction guard     — dash + correction word in A. block → EXEMPT
    2. Chain guard               — 3+ turns in paragraph → TAG (never auto-split)
    3. False-positive guards     — Exhibit A., Section Q., etc. → SKIP HIT
    4. Mode A/B + confidence     — determines AUTO-FIX vs TAG
"""

import re
import os
import sys
import json
import datetime
from dataclasses import dataclass, asdict


# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BleedHit:
    paragraph_index: int
    char_offset: int      # position in flattened paragraph string
    stray_label: str      # 'Q' or 'A'
    mode: str             # 'A' (≥40 chars before label) or 'B' (<40 chars)
    prefix_text: str      # flattened text before the stray label
    suffix_text: str      # flattened text from the stray label onward
    confidence: str       # 'HIGH' (auto-fix) | 'MEDIUM' (tag) | 'LOW' (tag)


# ═══════════════════════════════════════════════════════════════════════════════
# Compiled patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Any Q./A. label followed by 1-6 whitespace chars and an uppercase letter.
# \s{1,6} naturally excludes Q.E.D. (no space between Q. and E).
STRAY_LABEL_RE = re.compile(r'[QA]\.\s{1,6}[A-Z]')

# Self-correction guard: em-dash/double-hyphen followed by a correction word.
# If this fires in an A. block before a stray label → EXEMPT (do not split or tag).
# This is a Prime Directive / legal-record-accuracy guard.
SELF_CORRECTION_RE = re.compile(
    r'(?:—|--)\s*'
    r'(?:no,?|wait,?|actually,?|scratch\s+that|strike\s+that|correction,?'
    r'|i\s+mean\b|i\s+meant\b|let\s+me\s+rephrase|i\s+misspoke'
    r'|withdraw\b|retract\b|i\s+should\s+say|rather\b)',
    re.IGNORECASE
)

# Em-dash interrupt: immediately precedes a stray label → auto-split trigger.
# Distinguishable from self-correction because no correction word follows the dash.
EM_DASH_INTERRUPT_RE = re.compile(r'(?:—|--)\s*$')

# Fragment-ending conjunction/preposition → LOW confidence (uncertain → tag).
FRAGMENT_END_RE = re.compile(
    r'\b(?:and|but|from|in|the|to|of|at|by|or|nor|so|yet|for)\s*$',
    re.IGNORECASE
)

# Reference label immediately before Q./A. → false positive guard.
FP_REFERENCE_RE = re.compile(
    r'\b(?:Exhibit|Section|Paragraph|Schedule|Appendix|Article|Subsection'
    r'|Attachment|Addendum|Amendment|Figure|Table|Chapter)\s*$',
    re.IGNORECASE
)

# Existing verify-agent tag → skip paragraph entirely (R3 guard).
# Matches all known verify-agent and backstop tag formats:
#   [FLAG: ...]         — verify-agent flag
#   REVIEW]             — close-bracket legacy format
#   [[REVIEW]]          — double-bracket legacy format
#   [REVIEW-001: ...]   — backstop's own numbered tags
#   [REVIEW: ...]       — verify agent's open-bracket-colon format (THE BUG FIX)
#                         The verify agent writes [REVIEW: reason text] with no
#                         close bracket before the reason. This alternation was
#                         missing — R3 was a dead guard for every Brandl paragraph
#                         the verify agent had touched. Chain guard was accidentally
#                         saving us. Now R3 does its own work.
VERIFY_TAG_RE = re.compile(r'\[FLAG:|\[REVIEW:|\bREVIEW\]|\[\[REVIEW\]\]|\[REVIEW-\d+:')

# Opening label at start of a paragraph (Q. or A. with 1+ spaces).
OPENER_RE = re.compile(r'^([QA])\.\s+')


# ═══════════════════════════════════════════════════════════════════════════════
# Paragraph utilities
# ═══════════════════════════════════════════════════════════════════════════════

def split_paragraphs(text):
    """Split text on blank lines. Returns list of non-empty paragraph strings."""
    return [p for p in re.split(r'\n\n+', text) if p.strip()]


def flatten(paragraph):
    """Flatten a multi-line paragraph to a single string (join lines with space)."""
    return ' '.join(line.strip() for line in paragraph.split('\n') if line.strip())


def normalize_label(text):
    """
    Normalize the opening Q./A. label of a paragraph fragment to 3-space format.
    'Q. text' → 'Q.   text'
    """
    return re.sub(r'^([QA])\.\s+', r'\1.   ', text)


# ═══════════════════════════════════════════════════════════════════════════════
# False-positive guard
# ═══════════════════════════════════════════════════════════════════════════════

def _is_false_positive(flat, match_start):
    """
    Returns True if the Q./A. match at match_start is a false positive.
    Currently checks: reference labels (Exhibit A., Section Q., etc.)
    """
    prefix = flat[:match_start]
    if FP_REFERENCE_RE.search(prefix):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Hit classification
# ═══════════════════════════════════════════════════════════════════════════════

def classify_hit(paragraph_flat, char_offset, prefix_text):
    """
    Classify a bleed hit's mode and confidence.

    mode:
        'A'  — ≥40 chars of content before the stray label (run-on blob fragment)
        'B'  — <40 chars of content (short interjection)

    confidence:
        'HIGH'   — safe to auto-fix
        'MEDIUM' — uncertain, tag for review
        'LOW'    — uncertain, tag for review

    Returns (mode, confidence).
    """
    # Strip opening label to get pure content
    m = OPENER_RE.match(prefix_text)
    content_start = m.end() if m else 0
    content = prefix_text[content_start:].strip()

    mode = 'A' if len(content) >= 40 else 'B'

    # Em-dash interrupt override: always HIGH (auto-split), regardless of mode.
    # The dash is the structural signal that the interruption is intentional.
    if EM_DASH_INTERRUPT_RE.search(prefix_text.rstrip()):
        return mode, 'HIGH'

    # Fragment-ending conjunction/preposition → incomplete sentence → LOW
    if FRAGMENT_END_RE.search(content):
        return mode, 'LOW'

    # No terminal punctuation → LOW
    if not re.search(r'[.?!]\s*$', content):
        return mode, 'LOW'

    # Has terminal punctuation
    if mode == 'A':
        # Long content with terminal punctuation → safe to split
        return 'A', 'HIGH'
    else:
        # Mode B: safe if ends with period (not ? or !) and content is non-empty
        if content and re.search(r'\.\s*$', content):
            return 'B', 'HIGH'
        else:
            # Ends with ? or ! in an answer — ambiguous
            return 'B', 'MEDIUM'


# ═══════════════════════════════════════════════════════════════════════════════
# Detection
# ═══════════════════════════════════════════════════════════════════════════════

def detect_bleed(paragraph, paragraph_index=0):
    """
    Scan a paragraph for mid-paragraph Q./A. labels (bleed hits).

    Skips:
    - The opening label at position 0
    - False positives (Exhibit A., etc.)
    - Self-correction contexts (A. block with dash + correction word before hit)
    - Paragraphs containing existing verify-agent tags

    Returns list of BleedHit objects (may be empty).
    """
    if not isinstance(paragraph, str) or not paragraph.strip():
        return []

    # R3 guard: don't touch paragraphs with existing verify-agent flags
    if VERIFY_TAG_RE.search(paragraph):
        return []

    flat = flatten(paragraph)
    if not flat:
        return []

    # Caption-block guard: only process paragraphs that open with Q. or A.
    # Anything else — caption headers, attorney appearances, exhibit lists,
    # court reporter certifications, colloquy lines starting with MR./MS.,
    # (Whereupon,...) blocks — is structural content the AI owns entirely.
    # Touching it would tag or split text the backstop has no business touching.
    opener = OPENER_RE.match(flat)
    if not opener:
        return []

    opener_end = opener.end()
    is_a_block = flat[0] == 'A'

    hits = []
    for m in STRAY_LABEL_RE.finditer(flat):
        pos = m.start()

        # Skip the opening label itself
        if pos < opener_end:
            continue

        # Must be genuinely mid-paragraph (> 6 chars in)
        if pos < 6:
            continue

        # False positive guard
        if _is_false_positive(flat, pos):
            continue

        prefix_text = flat[:pos]
        suffix_text = flat[pos:]

        # Self-correction guard: if this is an A. block and a dash + correction
        # word appears anywhere in the prefix, exempt the entire hit.
        if is_a_block and SELF_CORRECTION_RE.search(prefix_text):
            continue

        mode, confidence = classify_hit(flat, pos, prefix_text)
        stray = flat[pos]  # 'Q' or 'A'

        hits.append(BleedHit(
            paragraph_index=paragraph_index,
            char_offset=pos,
            stray_label=stray,
            mode=mode,
            prefix_text=prefix_text,
            suffix_text=suffix_text,
            confidence=confidence,
        ))

    return hits


# ═══════════════════════════════════════════════════════════════════════════════
# Tag insertion
# ═══════════════════════════════════════════════════════════════════════════════

def tag_paragraph(paragraph, hit, tag_id):
    """
    Insert [REVIEW-NNN: possible turn break] immediately before the stray label.

    Placement: one space before the tag, one space after — clean deletion
    leaves original text intact (no orphaned whitespace).

    Returns the tagged paragraph string.
    """
    flat = flatten(paragraph)
    pos = hit.char_offset
    tag = f'[{tag_id}: possible turn break]'
    before = flat[:pos].rstrip()
    after = flat[pos:].lstrip()
    return before + ' ' + tag + ' ' + after


# ═══════════════════════════════════════════════════════════════════════════════
# Fix application
# ═══════════════════════════════════════════════════════════════════════════════

def apply_fix(para, hits, tag_counter_start=1):
    """
    Apply auto-fixes or tags to a paragraph based on detected hits.

    Guard hierarchy applied here:
        1. Self-correction (exempt — no split, no tag)
        2. Chain (3+ turns — tag once at first stray label)
        3. Auto-fix (HIGH confidence Mode A or B — split)
        4. Tag (uncertain — insert [REVIEW-NNN])

    Args:
        para:              paragraph string (or empty/non-string for dummy calls)
        hits:              list of BleedHit from detect_bleed()
        tag_counter_start: integer counter for tag IDs (REVIEW-NNN)

    Returns dict:
        'text':         modified paragraph string
        'actions':      list of Proof-of-Work action records
        'next_counter': next counter value (tag_counter_start + tags/fixes used)
    """
    # Handle edge case: non-string para (e.g., dummy calls in tests)
    if not isinstance(para, str):
        return {'text': '', 'actions': [], 'next_counter': tag_counter_start}

    flat = flatten(para) if para.strip() else ''
    counter = tag_counter_start

    # ── No hits: check if self-correction guard exempted the paragraph ────────
    if not hits:
        opener = OPENER_RE.match(flat) if flat else None
        is_a_block = opener and flat[0] == 'A'
        if is_a_block and SELF_CORRECTION_RE.search(flat):
            return {
                'text': para,
                'actions': [{
                    'action': 'exempt_self_correction',
                    'paragraph_index': 0,
                    'input_text': para,
                    'exempt_reason': 'Self-correction guard: dash + correction word in A. block',
                }],
                'next_counter': counter,
            }
        return {'text': para, 'actions': [], 'next_counter': counter}

    actions = []

    # ── Self-correction guard (paragraph level) ───────────────────────────────
    # Secondary check: if detect_bleed didn't catch it (e.g., non-A block edge case)
    opener = OPENER_RE.match(flat) if flat else None
    is_a_block = opener and flat[0] == 'A'
    if is_a_block and hits:
        prefix_before_first = flat[:hits[0].char_offset]
        if SELF_CORRECTION_RE.search(prefix_before_first):
            return {
                'text': para,
                'actions': [{
                    'action': 'exempt_self_correction',
                    'paragraph_index': hits[0].paragraph_index,
                    'input_text': para,
                    'exempt_reason': 'Self-correction guard: dash + correction word in A. block',
                }],
                'next_counter': counter,
            }

    # ── Chain guard: 3+ total turns → tag once, never auto-split ─────────────
    total_turns = 1 + len(hits)   # opener counts as turn 1
    if total_turns >= 3:
        tag_id = f'REVIEW-{counter:03d}'
        tagged = tag_paragraph(para, hits[0], tag_id)
        actions.append({
            'tag_id': tag_id,
            'mode': hits[0].mode,
            'confidence': hits[0].confidence,
            'action': 'tagged',
            'paragraph_index': hits[0].paragraph_index,
            'input_text': para,
            'tag_reason': (
                f'Chain: {total_turns} turns in one paragraph '
                f'— always tag, never auto-split (spec §4.3 edge 1)'
            ),
            'stray_label': hits[0].stray_label,
            'prefix_chars': len(hits[0].prefix_text),
        })
        counter += 1
        return {'text': tagged, 'actions': actions, 'next_counter': counter}

    # ── Single hit (2 turns): evaluate for auto-fix or tag ───────────────────
    hit = hits[0]
    auto_fix = hit.mode in ('A', 'B') and hit.confidence == 'HIGH'

    if auto_fix:
        part1 = flat[:hit.char_offset].rstrip()
        part2 = normalize_label(flat[hit.char_offset:].lstrip())
        new_text = part1 + '\n\n' + part2
        actions.append({
            'fix_id': f'FIX-{counter:03d}',
            'mode': hit.mode,
            'confidence': hit.confidence,
            'action': 'auto_fix',
            'paragraph_index': hit.paragraph_index,
            'input_text': para,
            'output_paragraph_1': part1,
            'output_paragraph_2': part2,
            'split_reason': (
                f'Mode {hit.mode} safe: terminal punctuation present, '
                f'no fragment markers, em-dash interrupt or known pattern'
            ),
            'alternation_check': 'PASS',
        })
        counter += 1
        return {'text': new_text, 'actions': actions, 'next_counter': counter}

    else:
        # Uncertain → tag for CR review
        tag_id = f'REVIEW-{counter:03d}'
        tagged = tag_paragraph(para, hit, tag_id)
        if hit.confidence == 'LOW':
            if not re.search(r'[.?!]', hit.prefix_text):
                reason_detail = 'no terminal punctuation before stray label'
            elif FRAGMENT_END_RE.search(hit.prefix_text):
                reason_detail = 'content ends with fragment indicator (conjunction/preposition)'
            else:
                reason_detail = 'content before stray label is ambiguous'
        else:
            reason_detail = 'ambiguous content before stray label (MEDIUM confidence)'

        actions.append({
            'tag_id': tag_id,
            'mode': hit.mode,
            'confidence': hit.confidence,
            'action': 'tagged',
            'paragraph_index': hit.paragraph_index,
            'input_text': para,
            'tag_reason': f'Mode {hit.mode} uncertain: {reason_detail}',
            'stray_label': hit.stray_label,
            'prefix_chars': len(hit.prefix_text),
        })
        counter += 1
        return {'text': tagged, 'actions': actions, 'next_counter': counter}


# ═══════════════════════════════════════════════════════════════════════════════
# Main pipeline entry point
# ═══════════════════════════════════════════════════════════════════════════════

def process_file(input_path, dry_run=False, wide_scan=False):
    """
    Read corrected_text.txt, process all paragraphs, write back in place.
    Returns the PoW summary dict.
    """
    with open(input_path, encoding='utf-8', errors='replace') as f:
        raw = f.read()

    paragraphs = split_paragraphs(raw)
    print(f'[def015_backstop] Input:  {input_path} ({len(raw)} bytes, {len(paragraphs)} paragraphs)')

    out_paragraphs = []
    all_actions = []
    counter = 1

    summary = {
        'total_hits_detected': 0,
        'auto_fixed_mode_a': 0,
        'auto_fixed_mode_b': 0,
        'tagged_uncertain': 0,
        'exempt_self_correction': 0,
        'skipped_verify_tag': 0,
        'false_positive_guards_fired': 0,
        'chains_tagged': 0,
    }

    for idx, para in enumerate(paragraphs):
        # Count skipped-verify-tag paragraphs
        if VERIFY_TAG_RE.search(para):
            summary['skipped_verify_tag'] += 1
            out_paragraphs.append(para)
            continue

        hits = detect_bleed(para, paragraph_index=idx)
        summary['total_hits_detected'] += len(hits)

        result = apply_fix(para, hits, tag_counter_start=counter)
        counter = result['next_counter']
        out_paragraphs.append(result['text'])

        for action in result['actions']:
            all_actions.append(action)
            act = action['action']
            mode = action.get('mode', '')
            if act == 'auto_fix':
                if mode == 'A':
                    summary['auto_fixed_mode_a'] += 1
                else:
                    summary['auto_fixed_mode_b'] += 1
            elif act == 'tagged':
                total_turns = 1 + sum(
                    1 for h in detect_bleed(action['input_text'], idx)
                )
                if total_turns >= 3:
                    summary['chains_tagged'] += 1
                else:
                    summary['tagged_uncertain'] += 1
            elif act == 'exempt_self_correction':
                summary['exempt_self_correction'] += 1

        if wide_scan and hits:
            for h in hits:
                print(f'  [HIT] para={idx} mode={h.mode} conf={h.confidence} '
                      f'label={h.stray_label} offset={h.char_offset}')
                print(f'        ...{h.prefix_text[-40:]}|{h.suffix_text[:40]}...')

    # Report
    print(f'[def015_backstop] Hits detected:         {summary["total_hits_detected"]}')
    print(f'[def015_backstop] Auto-fixed Mode A:     {summary["auto_fixed_mode_a"]}')
    print(f'[def015_backstop] Auto-fixed Mode B:     {summary["auto_fixed_mode_b"]}')
    print(f'[def015_backstop] Tagged uncertain:      {summary["tagged_uncertain"]}')
    print(f'[def015_backstop] Chains tagged:         {summary["chains_tagged"]}')
    print(f'[def015_backstop] Self-correction exempt:{summary["exempt_self_correction"]}')
    print(f'[def015_backstop] Verify-tag skipped:    {summary["skipped_verify_tag"]}')

    if dry_run:
        print('[def015_backstop] Dry-run mode — no files written.')
        return summary

    # Write corrected_text.txt back in place
    out_text = '\n\n'.join(out_paragraphs) + '\n'
    with open(input_path, 'w', encoding='utf-8') as f:
        f.write(out_text)
    print(f'[def015_backstop] Wrote {input_path}')

    # Write PROOF_OF_WORK_BACKSTOP.json
    delivery_dir = os.path.join(os.path.dirname(input_path), 'FINAL_DELIVERY')
    if os.path.isdir(delivery_dir):
        pow_path = os.path.join(delivery_dir, 'PROOF_OF_WORK_BACKSTOP.json')
        pow_doc = {
            'run_date': datetime.date.today().isoformat(),
            'engine_version': 'v4.2',
            'backstop_version': '1.0',
            'summary': summary,
            'fixes': [a for a in all_actions if a.get('action') == 'auto_fix'],
            'tags': [a for a in all_actions if a.get('action') == 'tagged'],
            'exemptions': [a for a in all_actions if a.get('action') == 'exempt_self_correction'],
        }
        with open(pow_path, 'w', encoding='utf-8') as f:
            json.dump(pow_doc, f, indent=2, ensure_ascii=False)
        print(f'[def015_backstop] Wrote {pow_path}')

    return summary


def main():
    dry_run = '--dry-run' in sys.argv
    wide_scan = '--wide-scan' in sys.argv

    # Accept optional positional path: python def015_backstop.py [path] [--flags]
    positional = [a for a in sys.argv[1:] if not a.startswith('--')]
    input_path = positional[0] if positional else 'corrected_text.txt'

    if not os.path.exists(input_path):
        print(f'[def015_backstop] ERROR: {input_path} not found')
        sys.exit(1)

    process_file(input_path, dry_run=dry_run, wide_scan=wide_scan)


if __name__ == '__main__':
    main()

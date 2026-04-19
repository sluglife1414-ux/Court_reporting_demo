#!/usr/bin/env python3
"""
qa_line_splitter.py — DEF-015 post-AI Q/A line splitter

Splits dense inline Q/A blocks (multiple speaker turns collapsed onto one line)
into separate lines. Adds structure only — never modifies content words.

Pipeline position: AFTER ai_engine.py, BEFORE def015_backstop.py
Input/output: corrected_text.txt (in-place by default, with pre-split backup)
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

# Matches a Q/A turn boundary: word-boundary + (Q or A) + dot + whitespace.
# \b prevents matching mid-word tokens like ESQ., Mr., Mrs., Dr., 2.5, etc.
TURN_BOUNDARY_RE = re.compile(r'(\b[QA]\.\s)')

# Valid leading tokens for output lines (warning if not matched)
VALID_LEAD_RE = re.compile(r'^([QA]\.|MR\.|MS\.|MRS\.|DR\.|THE\b|BY\s|\(|\[)')


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def mask_brackets(line: str) -> tuple:
    """
    Replace all [bracket content] with null-byte-keyed placeholders so that
    Q. or A. inside bracket tags are invisible to the boundary splitter.
    Returns (masked_line, placeholder_map).
    """
    placeholders = {}
    idx = [0]

    def _replace(m):
        key = f'\x00B{idx[0]}\x00'
        placeholders[key] = m.group(0)
        idx[0] += 1
        return key

    masked = re.sub(r'\[[^\]]*\]', _replace, line)
    return masked, placeholders


def restore_placeholders(text: str, placeholders: dict) -> str:
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


def count_boundaries(masked: str) -> int:
    return len(TURN_BOUNDARY_RE.findall(masked))


def split_line(line: str) -> list:
    """
    Split a collapsed Q/A line into fragments.
    Returns [line] unchanged when fewer than 2 boundaries found.
    Each fragment preserves its leading Q./A. label and full content.
    """
    stripped = line.rstrip('\n\r')
    masked, placeholders = mask_brackets(stripped)

    if count_boundaries(masked) < 2:
        return [line]

    parts = TURN_BOUNDARY_RE.split(masked)
    # parts layout: [pre_content, delim1, body1, delim2, body2, ...]

    result = []

    # Content before the first Q/A boundary (rare; usually empty)
    if parts[0].strip():
        frag = restore_placeholders(parts[0], placeholders)
        result.append(frag)

    # Pair each delimiter with its following body
    i = 1
    while i < len(parts):
        delim = parts[i]     if i < len(parts)     else ''
        body  = parts[i + 1] if (i + 1) < len(parts) else ''
        frag  = restore_placeholders(delim + body, placeholders)
        if frag.strip():
            result.append(frag)
        i += 2

    return result if result else [line]


def check_leading_token(fragment: str, src_lineno: int, warnings: list):
    stripped = fragment.lstrip()
    if stripped and not VALID_LEAD_RE.match(stripped):
        snippet = stripped[:60]
        warnings.append(
            f'unexpected leading token at line {src_lineno}: {snippet!r}'
        )


def process_lines(lines: list) -> tuple:
    """
    Process all input lines.
    Returns (output_lines, split_count, warnings).
    """
    output   = []
    n_split  = 0
    warnings = []

    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            output.append(line)
            continue

        fragments = split_line(line)

        if len(fragments) > 1:
            n_split += 1
            for frag in fragments:
                check_leading_token(frag, lineno, warnings)
                output.append(frag + '\n')
        else:
            output.append(line if line.endswith('\n') else line + '\n')

    return output, n_split, warnings


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def make_backup(input_path: Path) -> Path:
    today = date.today().strftime('%Y-%m-%d')
    backup_path = input_path.with_suffix(f'.pre_split_{today}')
    backup_path.write_bytes(input_path.read_bytes())
    return backup_path


def run(input_path: Path, output_path: Path, dry_run: bool) -> int:
    if not input_path.exists():
        print(f'[ERROR] Input file not found: {input_path}', file=sys.stderr)
        return 1

    lines = input_path.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
    output_lines, n_split, warnings = process_lines(lines)

    n_in  = len(lines)
    n_out = len(output_lines)

    # Summary
    print(f'Lines input   : {n_in}')
    print(f'Lines output  : {n_out}')
    print(f'Lines split   : {n_split}')
    print(f'Warnings      : {len(warnings)}')
    for w in warnings:
        print(f'  [WARN] {w}')

    if dry_run:
        print('[DRY RUN] No files written.')
        return 0

    backup = make_backup(input_path)
    print(f'Backup written: {backup}')

    output_path.write_text(''.join(output_lines), encoding='utf-8')
    print(f'Output written: {output_path}')
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Split dense inline Q/A blocks into separate lines (DEF-015 fix).'
    )
    parser.add_argument(
        '--input', type=Path,
        default=Path('corrected_text.txt'),
        help='Input file (default: corrected_text.txt in CWD)'
    )
    parser.add_argument(
        '--output', type=Path, default=None,
        help='Output file (default: same as --input, in-place)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Report stats only; write nothing'
    )
    args = parser.parse_args()

    output_path = args.output if args.output else args.input
    sys.exit(run(args.input, output_path, args.dry_run))


if __name__ == '__main__':
    main()

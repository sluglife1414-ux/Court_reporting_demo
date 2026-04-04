"""
build_transcript.py — Produce FINAL_TRANSCRIPT.txt from formatted output.

Reads FINAL_DELIVERY/{CASE_SHORT}_FINAL_FORMATTED.txt (already paginated,
line-numbered, and AI-corrected by format_final.py) and writes it as the
official plain-text transcript.

All case metadata from depo_config.json — no hardcoded values.

Usage:
    python build_transcript.py
"""
import json
import os
import sys

# --- Load case config ---
if not os.path.exists('depo_config.json'):
    print('[ERROR] depo_config.json not found. Run extract_config.py first.')
    sys.exit(1)

with open('depo_config.json', encoding='utf-8') as f:
    cfg = json.load(f)
# CASE_CAPTION.json is authoritative — overrides depo_config.json (matches format_final.py logic)
if os.path.exists('CASE_CAPTION.json'):
    with open('CASE_CAPTION.json', encoding='utf-8') as _cf:
        cfg.update(json.load(_cf))

CASE_SHORT = cfg.get('case_short', 'Unknown_Case')

INPUT_FILE  = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL_FORMATTED.txt'
OUTPUT_FILE = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL_TRANSCRIPT.txt'

# --- Read formatted transcript ---
if not os.path.exists(INPUT_FILE):
    print(f'[ERROR] {INPUT_FILE} not found.')
    print('        Run format_final.py first (or python run_pipeline.py --from format).')
    sys.exit(1)

with open(INPUT_FILE, encoding='utf-8') as f:
    content = f.read()

# --- Write transcript ---
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Transcript written: {OUTPUT_FILE}  ({len(content):,} chars)')

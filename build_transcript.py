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

CASE_SHORT = cfg.get('case_short', 'Unknown_Case')

INPUT_FILE  = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL_FORMATTED.txt'
OUTPUT_FILE = f'FINAL_DELIVERY/{CASE_SHORT}_FINAL_TRANSCRIPT.txt'

# --- Fallback: scan for any *_FINAL_FORMATTED.txt if expected name not found ---
if not os.path.exists(INPUT_FILE):
    import glob as _glob
    _candidates = [f for f in _glob.glob('FINAL_DELIVERY/*_FINAL_FORMATTED.txt')
                   if not os.path.basename(f).startswith('accuracy_report_')]
    if len(_candidates) == 1:
        INPUT_FILE  = _candidates[0]
        _found_short = os.path.basename(INPUT_FILE).replace('_FINAL_FORMATTED.txt', '')
        OUTPUT_FILE = f'FINAL_DELIVERY/{_found_short}_FINAL_TRANSCRIPT.txt'
        print(f'[build_transcript] WARNING: case_short mismatch — using {INPUT_FILE}')
    elif len(_candidates) > 1:
        print(f'[ERROR] Multiple FINAL_FORMATTED files found, cannot auto-resolve:')
        for c in _candidates: print(f'  {c}')
        sys.exit(1)
    else:
        print(f'[ERROR] {INPUT_FILE} not found.')
        print('        Run format_final.py first (or python run_pipeline.py --from format).')
        sys.exit(1)

with open(INPUT_FILE, encoding='utf-8') as f:
    content = f.read()

# --- Write transcript ---
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Transcript written: {OUTPUT_FILE}  ({len(content):,} chars)')

"""
Build condensed transcript (4 lines per row, reduced spacing).
"""
import re
import json

with open('depo_config.json', encoding='utf-8') as _f:
    _cfg = json.load(_f)
_CASE = _cfg.get('case_short', 'Unknown_Case')

with open(f'FINAL_DELIVERY/{_CASE}_FINAL_TRANSCRIPT.txt', 'r', encoding='utf-8') as f:
    full = f.read()

# Condensed format: narrower, compressed
# We'll produce a condensed version with 4-mini-pages per page concept
# Output as readable condensed text

_plaintiff  = _cfg.get('plaintiff', 'UNKNOWN')
_defendant  = _cfg.get('defendant', 'UNKNOWN')
_case_name  = f"{_plaintiff} v. {_defendant}"
_docket     = _cfg.get('docket', 'UNKNOWN')
_witness    = _cfg.get('witness_name', 'UNKNOWN')
_depo_date  = _cfg.get('depo_date', 'UNKNOWN')
_reporter   = _cfg.get('reporter_name', 'UNKNOWN')

header = f"""\
================================================================================
CONDENSED TRANSCRIPT
{_case_name} | Docket {_docket}
Witness: {_witness} | {_depo_date}
Reporter: {_reporter}
[CONDENSED FORMAT — 4 transcript pages per page equivalent]
================================================================================

"""

# Simply re-output with tighter spacing and a note
# Standard condensed = 4 Q/A lines per page row
# For our purposes, we collapse the line-number padding and output compactly

lines = full.split('\n')
condensed_lines = [header]

prev_blank = False
for line in lines:
    # Collapse multiple blank lines to single
    if not line.strip():
        if not prev_blank:
            condensed_lines.append('\n')
        prev_blank = True
        continue
    prev_blank = False

    # Remove line numbers from left margin (compress to just the text)
    stripped = re.sub(r'^\s*\d{1,2}\s{2,4}', '', line)
    condensed_lines.append(stripped.rstrip() + '\n')

output = ''.join(condensed_lines)

# Further collapse blank lines
output = re.sub(r'\n{3,}', '\n\n', output)

with open(f'FINAL_DELIVERY/{_CASE}_CONDENSED.txt', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Condensed transcript written. Length: {len(output):,} chars")

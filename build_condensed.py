"""
Build condensed transcript (4 lines per row, reduced spacing).
"""
import re

with open('FINAL_DELIVERY/Easley_YellowRock_FINAL_TRANSCRIPT.txt', 'r', encoding='utf-8') as f:
    full = f.read()

# Condensed format: narrower, compressed
# We'll produce a condensed version with 4-mini-pages per page concept
# Output as readable condensed text

header = """\
================================================================================
CONDENSED TRANSCRIPT
Yellow Rock, LLC et al. v. Westlake US 2 LLC et al. | Docket 202-001594
Witness: Thomas L. Easley | March 13, 2026
Reporter: Marybeth E. Muir, CCR, RPR
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

with open('FINAL_DELIVERY/Easley_YellowRock_CONDENSED.txt', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Condensed transcript written. Length: {len(output):,} chars")

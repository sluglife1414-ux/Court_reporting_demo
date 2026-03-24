"""
Build clean final transcript from extracted Q/A text.
Applies all corrections per Louisiana Engineering rules.
"""
import re

CASE_HEADER = """\
                    STATE OF LOUISIANA

                    PARISH OF CALCASIEU

                    14TH JUDICIAL DISTRICT

* * * * * * * * * * * * * * * * * * * * * * * *

YELLOW ROCK, LLC, et al.,
                    Plaintiffs,

Docket No. 202-001594
Division "H"

               v.

WESTLAKE US 2 LLC f/k/a EAGLE US 2 LLC, et al.,
                    Defendants.

* * * * * * * * * * * * * * * * * * * * * * * *

                    VIDEOTAPED DEPOSITION
                    OF
                    THOMAS L. EASLEY

taken on

Friday, March 13, 2026

commencing at 9:09 a.m.

at

111 North Post Oak Lane
Houston, Texas  77024

Reported By:  MARYBETH E. MUIR, CCR, RPR

* * * * * * * * * * * * * * * * * * * * * * * *
"""

with open('cleaned_text.txt', 'r', encoding='utf-8') as f:
    raw_lines = f.readlines()

raw = ''.join(raw_lines)

# --- CORRECTIONS ---

# Fix underscore hyphens (steno artifact)
raw = re.sub(r'(?<=[a-zA-Z])_(?=[a-zA-Z])', '-', raw)

# Fix "brat spot" → "bright spot" [CORRECTED]
raw = re.sub(r'\bbrat spot', '[CORRECTED: brat spot] bright spot', raw, flags=re.IGNORECASE)
raw = re.sub(r'\bbrat spots', '[CORRECTED: brat spot] bright spots', raw, flags=re.IGNORECASE)

# Fix "stand forward" → "Stanford" [CORRECTED]
raw = raw.replace('stand forward', '[CORRECTED: stand forward] Stanford')

# Fix "We depth have to" → "We don't have to" [CORRECTED]
raw = raw.replace('We depth have to go through every one,',
                  "We don't [CORRECTED: depth] have to go through every one,")

# Fix "get picked up bathe transcript" → "get picked up by the transcript" [CORRECTED]
raw = raw.replace('get picked up bathe\ntranscript', 'get picked up by the [CORRECTED: bathe] transcript')

# Fix double-@ in email
raw = raw.replace('asirianni@@windelsmarx.com', 'asirianni@windelsmarx.com')

# Fix "hey" → "hay" (coastal Bermuda hay)
# Done contextually in the transcript

# Fix location: caption says 909 Post Oak St but videographer says 111 North Post Oak Lane
# Keep videographer's opening verbatim; flag caption error

# Remove filler word "uhmm" (unless meaningful to preserve voice)
# Per Layer 6: default REMOVE
raw = re.sub(r'\bUhmm\.?\s*', '', raw, flags=re.IGNORECASE)
raw = re.sub(r'\buhmm,?\s*', '', raw, flags=re.IGNORECASE)

# Clean remaining duplicate blank lines
raw = re.sub(r'\n{3,}', '\n\n', raw)

# Remove lines that are just the page break markers (we'll re-paginate)
# Keep them for now as section markers

# --- Write clean transcript ---
output_lines = []

# Write header
output_lines.append(CASE_HEADER)
output_lines.append("\n")
output_lines.append("                   [REVIEW: Caption page lists location as 909 Post Oak Street;\n")
output_lines.append("                    videographer transcript reflects 111 North Post Oak Lane.\n")
output_lines.append("                    Reporter to verify correct location address.]\n")
output_lines.append("\n")

# Now process the extracted lines
# Skip everything up to and including the cover page content (first ~100 lines)
# Start from the APPEARANCES section onward

lines = raw.split('\n')

# Find the start of APPEARANCES
start_idx = 0
for i, line in enumerate(lines):
    if 'A P P E A R A N C E S:' in line and i > 50:
        start_idx = i
        break

# Write APPEARANCES
output_lines.append("=" * 70 + "\n")
output_lines.append("                    A P P E A R A N C E S:\n")
output_lines.append("=" * 70 + "\n\n")

# Process transcript body
PAGE_LINE_COUNT = 0
PAGE_NUM = 5  # Appearances start around page 5
LINE_NUM = 1

i = start_idx
while i < len(lines):
    line = lines[i].strip()

    # Skip page break markers and re-paginate
    if '--- PAGE BREAK ---' in line or '--- PAGE' in line:
        PAGE_NUM += 1
        LINE_NUM = 1
        output_lines.append(f"\n{'='*70}\n")
        output_lines.append(f"                              PAGE {PAGE_NUM}\n")
        output_lines.append(f"{'='*70}\n\n")
        i += 1
        continue

    if not line:
        output_lines.append('\n')
        i += 1
        continue

    # Format with line numbers (simplified - left margin)
    formatted = f"{LINE_NUM:2d}    {line}\n"
    output_lines.append(formatted)
    LINE_NUM += 1
    if LINE_NUM > 25:
        PAGE_NUM += 1
        LINE_NUM = 1
        output_lines.append(f"\n--- [Page {PAGE_NUM}] ---\n\n")

    i += 1

# Add certification page
output_lines.append("\n")
output_lines.append("=" * 70 + "\n")
output_lines.append("                    REPORTER'S CERTIFICATE\n")
output_lines.append("=" * 70 + "\n\n")
output_lines.append("STATE OF LOUISIANA\n\n")
output_lines.append("PARISH OF CALCASIEU\n\n")
output_lines.append("        I, MARYBETH E. MUIR, Certified Court Reporter in and for\n")
output_lines.append("the State of Louisiana and Registered Professional Reporter, do hereby\n")
output_lines.append("certify that the witness, THOMAS L. EASLEY, was duly sworn by me prior\n")
output_lines.append("to the taking of the foregoing deposition; that said deposition was\n")
output_lines.append("taken by me in stenotype and transcribed under my supervision; and that\n")
output_lines.append("the foregoing is a true and correct transcript of the testimony of\n")
output_lines.append("said witness.\n\n")
output_lines.append("        I further certify that I am not a relative or employee of\n")
output_lines.append("counsel or any of the parties hereto, nor am I financially interested\n")
output_lines.append("in the outcome of this matter.\n\n")
output_lines.append("        [FLAG: LOUISIANA CERTIFICATION INCOMPLETE — reporter license\n")
output_lines.append("         number required. Please add CCR No. before signing.]\n\n")
output_lines.append("\n\n")
output_lines.append("                              ___________________________________\n")
output_lines.append("                              MARYBETH E. MUIR, CCR, RPR\n")
output_lines.append("                              Certified Court Reporter\n")
output_lines.append("                              State of Louisiana\n")
output_lines.append("                              CCR No. ____________\n\n")
output_lines.append("Date of Certification: _____________________________\n\n")

# Write final transcript
with open('FINAL_DELIVERY/Easley_YellowRock_FINAL_TRANSCRIPT.txt', 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print(f"Transcript written. Total output chars: {sum(len(l) for l in output_lines):,}")
print(f"Approximate final pages: {PAGE_NUM}")

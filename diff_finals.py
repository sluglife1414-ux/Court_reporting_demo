"""
diff_finals.py — Line-by-line comparison of engine output vs MB final PDF.
Finds the FIRST deviation and shows context.
Usage: python diff_finals.py
"""
import pdfplumber
import re
import sys

ENGINE_TXT = r"FINAL_DELIVERY\Easley_YellowRock_FINAL_FORMATTED.txt"
MB_PDF     = r"C:\Users\scott\Downloads\031326yellowrock-FINAL.pdf"
CONTEXT    = 5  # lines to show before/after deviation

# ── Extract MB PDF lines ──────────────────────────────────────────────────────
def extract_pdf_lines(path):
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                # Strip line numbers (1-2 digits at start)
                m = re.match(r"^\d{1,2}\s+(.*)", line)
                content = m.group(1) if m else line
                content = content.strip()
                if content:
                    lines.append(content)
    return lines

# ── Extract engine output lines ───────────────────────────────────────────────
def extract_engine_lines(path):
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            # Strip line numbers from our format (leading spaces + number + spaces)
            m = re.match(r"^\s*\d+\s+(.*)", line)
            content = m.group(1) if m else line
            content = content.strip()
            if content and "--- PAGE" not in content:
                lines.append(content)
    return lines

# ── Normalize for comparison (ignore minor whitespace/punctuation) ────────────
def norm(s):
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[—–-]+", "--", s)  # normalize dashes
    return s

# ── Main diff ─────────────────────────────────────────────────────────────────
print("Reading MB final PDF...")
mb_lines   = extract_pdf_lines(MB_PDF)
print(f"  {len(mb_lines)} lines extracted")

print("Reading engine output...")
eng_lines  = extract_engine_lines(ENGINE_TXT)
print(f"  {len(eng_lines)} lines extracted")

print()
print("=" * 70)
print("LINE-BY-LINE DIFF — first 20 deviations")
print("=" * 70)

mb_i  = 0
eng_i = 0
deviations = 0
MAX_DEV = 20

while mb_i < len(mb_lines) and eng_i < len(eng_lines) and deviations < MAX_DEV:
    mb_line  = mb_lines[mb_i]
    eng_line = eng_lines[eng_i]

    if norm(mb_line) == norm(eng_line):
        mb_i  += 1
        eng_i += 1
        continue

    # Deviation found
    deviations += 1
    print(f"\n{'─'*70}")
    print(f"DEVIATION #{deviations}  (MB line {mb_i+1}, Engine line {eng_i+1})")
    print(f"  MB  : {mb_line}")
    print(f"  ENG : {eng_line}")

    # Try to resync — look ahead up to 10 lines for a match
    resynced = False
    for lookahead in range(1, 10):
        # Engine is ahead (extra lines in engine)
        if eng_i + lookahead < len(eng_lines) and norm(mb_line) == norm(eng_lines[eng_i + lookahead]):
            print(f"  ↑ ENGINE has {lookahead} EXTRA line(s) before this MB line:")
            for x in range(lookahead):
                print(f"      +ENG[{eng_i+x+1}]: {eng_lines[eng_i+x]}")
            eng_i += lookahead
            resynced = True
            break
        # MB is ahead (extra lines in MB)
        if mb_i + lookahead < len(mb_lines) and norm(eng_line) == norm(mb_lines[mb_i + lookahead]):
            print(f"  ↑ MB has {lookahead} EXTRA line(s) before this engine line:")
            for x in range(lookahead):
                print(f"      +MB[{mb_i+x+1}]: {mb_lines[mb_i+x]}")
            mb_i += lookahead
            resynced = True
            break

    if not resynced:
        print(f"  ↑ Could not resync — content genuinely differs")
        mb_i  += 1
        eng_i += 1

print()
print("=" * 70)
print(f"Total deviations shown: {deviations}")
print(f"MB  remaining lines: {len(mb_lines) - mb_i}")
print(f"ENG remaining lines: {len(eng_lines) - eng_i}")

"""
ai_engine.py — AI correction pass for mb_demo_engine_v4.

Pipeline position: AFTER steno_cleanup.py, BEFORE format_final.py

  extract_rtf.py  →  extracted_text.txt
  steno_cleanup.py → cleaned_text.txt
  ai_engine.py    → corrected_text.txt + correction_log.json   ← THIS SCRIPT
  format_final.py → FINAL_DELIVERY/...

Uses Claude Code CLI (no API key required — uses your existing Claude Code auth).

Cost:   Covered by your Claude Code subscription. No separate billing.
Model:  claude-sonnet-4-6 (via Claude Code)
"""

import os
import sys
import json
import time
import re
import subprocess

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

INPUT_FILE    = 'cleaned_text.txt'
OUTPUT_TEXT   = 'corrected_text.txt'
OUTPUT_LOG    = 'correction_log.json'
CHUNK_TARGET  = 3000    # soft char limit per chunk; always breaks at paragraph boundary
MAX_RETRIES   = 2
INTER_CHUNK_DELAY = 0.3

# ─────────────────────────────────────────────────────────────────────────────
# CORRECTION PROMPT
# ─────────────────────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """You are a professional court reporter assistant correcting steno CAT rough draft artifacts in a legal deposition transcript. Apply Margie Wakeman Wells punctuation standards.

STENO ERROR PATTERNS TO CORRECT:

1. PHONETIC SUBSTITUTIONS — wrong word that sounds like what was said:
   "bathe transcript" → "by the transcript"
   "depth have to" → "don't have to"
   "ankle of the drill" → "angle of the drill"
   "wheels" → "wells" (oil and gas context)
   "writes offering" → "rights offering"
   "brat spot" → "bright spot" (seismic term)
   "hey" → "hay" (farming context)
   "ghee sciences" → "geoscience"
   "stand forward" → "Stanford"
   "vibrate ores" → "vibrators"
   "try angels" → "triangles"
   "signature named" → "significant named"
   "done" → "gone" (context: "they would have gone to")
   "Become in the day" → "Back in the day"
   "Collect check" → "Correct"
   "accept this slide to" → "sent this slide to"
   "odd" → "on" ("based odd this" → "based on this")
   "check silver mines" → "Sulphur Mines"

2. HOMOPHONES:
   "there" → "their" (possessive)
   "whole" → "hole" (drilling: "straight-hole")
   "mine" → "mind" ("in my mind")
   "very" → "V" (when referring to a letter)
   "hey" → "hay" (farming)
   "weep" → "we" ("weep want" → "we want")
   "write_up" → "right up" ("drilling right up to the salt")
   "why are" → "YR" (Bates prefix)

3. DROPPED LETTERS/SYLLABLES:
   "acquisition an development" → "acquisition and development"
   "don't know how far way" → "don't know how far away"
   "personal" → "personally"
   "expand had" → "expanded"

4. SPLIT WORD ERRORS:
   "a dressed" → "addressed"
   "cavern s" → "caverns"
   "ie it announces" → "it announces"
   "T he settlement" → "the settlement"
   "Board ofDescribe the ores meeting" → "Board of Directors meeting"
   "blacktop" → "White Top" (company name)

5. MERGED WORDS:
   "ofYellow Rock" → "of Yellow Rock"
   "IM D" → "IMD"

6. NUMERAL AND PUNCTUATION ARTIFACTS:
   "I mean0 Commissioner" → "I mean, Commissioner" (0 = comma)
   "12 '06 p.m." → "12:06 p.m."
   "'9:58 a.m." → "9:58 a.m." (leading apostrophe)
   "that right? . Okay." → "that right? Okay." (rogue period)
   "You asked me that. ." → "You asked me that." (double period)
   "SBA,," → "SBA," (double comma)
   "Okay U?" → "Okay."
   "28 today period" → "28-day period"
   "_ _" → "—" (em dash)

7. MULTI-WORD GARBLES:
   "tap California manager" → "typical manager"
   "geneos" → "gone"
   "toss that particular" → "to that particular"
   "Oliver resin mar sol" → "Alvarez and Marsal"
   "lawyer a" → "Laura" (Hurricane Laura)
   "REV rent signal energy" → "Revenant Signal Energy"
   "vis_ _vis" → "vis-à-vis"
   "say eye we" → "—I would say we"

8. NAME/PROPER NOUN GARBLES — use context or spelling to confirm. Log all.

9. Q./A. RUN-TOGETHER — if Q and A are merged, tag: [REVIEW: Q./A. FORMAT — needs separation]

VERBATIM RULES — NEVER CHANGE THESE:
- Witness colloquial speech ("gonna", "kinda", idioms)
- Witness self-corrections ("The—the thing I mean is...")
- Hesitation words (uh, um)
- Quoted language from documents
Log these as: confidence = "N/A", reason = "Verbatim — [explain]"

CONFIDENCE:
HIGH   — certain from context, pattern, or factual confirmation
MEDIUM — likely but ambiguous; insert [REVIEW: note] in corrected text
LOW    — possible; insert [REVIEW: note] in corrected text; do not apply silently
N/A    — verbatim, no change

MARGIE WAKEMAN WELLS:
- Commas around direct address: "I know, sir, that..."
- Comma before AND after state name when sentence continues:
  CORRECT: "in Houston, Texas, to visit" (not "Houston, Texas to visit")
- Em dash (—) for interruptions, no spaces around it

OUTPUT: Return ONLY valid JSON, no preamble, no explanation:

{{
  "corrected_text": "full corrected chunk preserving all paragraph breaks exactly",
  "corrections": [
    {{
      "line_approx": 44,
      "original": "exact text from input",
      "corrected": "corrected text",
      "confidence": "HIGH",
      "reason": "error type and why this correction is right"
    }}
  ]
}}

If no corrections found: return "corrections": []

---

Correct this deposition transcript chunk.
Starting line in full document (approximate): {line_start}
Chunk {chunk_num} of {total_chunks}

--- BEGIN CHUNK ---
{chunk_text}
--- END CHUNK ---

Return only valid JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# CHUNKING
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(text, target_size=CHUNK_TARGET):
    """Split text into chunks at paragraph boundaries."""
    paragraphs = re.split(r'\n\n+', text)
    chunks = []
    current = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para) + 2
        if current_size + para_size > target_size and current:
            chunks.append('\n\n'.join(current))
            current = [para]
            current_size = para_size
        else:
            current.append(para)
            current_size += para_size

    if current:
        chunks.append('\n\n'.join(current))

    return chunks


def line_start_for_chunk(text, chunk_index, chunks):
    preceding = '\n\n'.join(chunks[:chunk_index])
    return preceding.count('\n') + 1


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE CODE CLI CALL
# ─────────────────────────────────────────────────────────────────────────────

def correct_chunk(chunk_content, line_start, chunk_num, total_chunks):
    """Call Claude Code CLI to correct one chunk. Returns (corrected_text, corrections)."""
    prompt = PROMPT_TEMPLATE.format(
        line_start=line_start,
        chunk_num=chunk_num + 1,
        total_chunks=total_chunks,
        chunk_text=chunk_content
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                ['claude', '--print'],
                input=prompt,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=120
            )

            if result.returncode != 0:
                raise RuntimeError(f"claude CLI exit code {result.returncode}: {result.stderr[:200]}")

            raw = result.stdout.strip()

            # Strip markdown code fences if present
            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```\s*$', '', raw)

            parsed = json.loads(raw)
            corrected = parsed.get('corrected_text', chunk_content)
            corrections = parsed.get('corrections', [])
            return corrected, corrections

        except json.JSONDecodeError:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] JSON parse error, retry {attempt + 1}...', flush=True)
                time.sleep(2)
            else:
                print(f'  [ERROR] JSON parse failed — chunk kept as-is')
                return chunk_content, []

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] {e}, retry {attempt + 1}...', flush=True)
                time.sleep(3)
            else:
                print(f'  [ERROR] CLI call failed — chunk kept as-is')
                return chunk_content, []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(INPUT_FILE):
        print(f'ERROR: Input file not found: {INPUT_FILE}')
        sys.exit(1)

    # Verify claude CLI is available
    try:
        subprocess.run(['claude', '--version'], capture_output=True, timeout=10)
    except FileNotFoundError:
        print('ERROR: claude CLI not found. Is Claude Code installed?')
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text(text)

    print('=' * 60)
    print('AI CORRECTION ENGINE')
    print('Auth:   Claude Code (no API key needed)')
    print(f'Input:  {INPUT_FILE}  ({len(text):,} chars)')
    print(f'Chunks: {len(chunks)}  (~{CHUNK_TARGET} chars each)')
    print('=' * 60)

    all_corrections = []
    corrected_chunks = []

    for i, chunk in enumerate(chunks):
        line_start = line_start_for_chunk(text, i, chunks)
        pct = (i + 1) / len(chunks) * 100
        print(f'  [{i+1:3d}/{len(chunks)}]  ~line {line_start:<6}  {pct:5.1f}%', end='', flush=True)

        corrected, corrections = correct_chunk(chunk, line_start, i, len(chunks))
        corrected_chunks.append(corrected)
        all_corrections.extend(corrections)

        n = len(corrections)
        print(f'  +{n} correction{"s" if n != 1 else ""}')

        if i < len(chunks) - 1:
            time.sleep(INTER_CHUNK_DELAY)

    corrected_text = '\n\n'.join(corrected_chunks)

    with open(OUTPUT_TEXT, 'w', encoding='utf-8') as f:
        f.write(corrected_text)

    log_data = {
        "engine":            "ai_engine.py",
        "model":             "claude-sonnet-4-6 (via Claude Code CLI)",
        "input_file":        INPUT_FILE,
        "input_chars":       len(text),
        "output_chars":      len(corrected_text),
        "total_corrections": len(all_corrections),
        "corrections":       all_corrections
    }
    with open(OUTPUT_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    conf_counts = {}
    for c in all_corrections:
        conf = c.get('confidence', 'UNKNOWN')
        conf_counts[conf] = conf_counts.get(conf, 0) + 1

    print()
    print('=' * 60)
    print('AI CORRECTION COMPLETE')
    print('=' * 60)
    print(f'Output text:  {OUTPUT_TEXT}  ({len(corrected_text):,} chars)')
    print(f'Output log:   {OUTPUT_LOG}')
    print(f'Corrections:  {len(all_corrections)} total')
    print()
    for conf in ('HIGH', 'MEDIUM', 'LOW', 'N/A', 'UNKNOWN'):
        if conf in conf_counts:
            print(f'  {conf:<8}  {conf_counts[conf]}')
    print('=' * 60)


if __name__ == '__main__':
    main()

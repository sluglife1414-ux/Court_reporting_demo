"""
ai_engine.py — AI correction pass for mb_demo_engine_v4.

Pipeline position: AFTER steno_cleanup.py, BEFORE format_final.py

  extract_rtf.py  →  extracted_text.txt
  steno_cleanup.py → cleaned_text.txt
  ai_engine.py    → corrected_text.txt + correction_log.json   ← THIS SCRIPT
  format_final.py → FINAL_DELIVERY/...

What this does:
  - Reads cleaned_text.txt (post-steno-cleanup)
  - Chunks transcript by paragraph blocks (preserves Q&A integrity)
  - Calls Claude API on each chunk with court reporter correction prompt
  - Corrects: phonetic substitutions, homophones, garbles, split words,
    dropped letters, numeral artifacts, punctuation artifacts
  - Verbatim rule: never "fixes" witness's natural language or colloquial speech
  - Uncertain corrections tagged [REVIEW: ...] for reporter to verify
  - Writes corrected_text.txt and correction_log.json

Target:  ~100+ corrections per full depo (v3 PROOF_OF_WORK as reference baseline)
Model:   claude-sonnet-4-6
Cost:    ~$0.50-$1.50 per full Easley-length run (~12,000 lines)
"""

import os
import sys
import json
import time
import re

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed.")
    print("       Run: pip install anthropic")
    sys.exit(1)

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

INPUT_FILE    = 'cleaned_text.txt'
OUTPUT_TEXT   = 'corrected_text.txt'
OUTPUT_LOG    = 'correction_log.json'
MODEL         = 'claude-sonnet-4-6'
CHUNK_TARGET  = 3000    # soft char limit per chunk; always breaks at paragraph boundary
MAX_RETRIES   = 2
INTER_CHUNK_DELAY = 0.4  # seconds between API calls

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional court reporter assistant specializing in correcting steno CAT (Computer-Aided Transcription) rough draft artifacts in legal deposition transcripts.

Your job is to correct steno errors while preserving the verbatim record. You apply Margie Wakeman Wells grammar and punctuation standards — the industry standard for court reporters.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STENO ERROR PATTERNS — IDENTIFY AND CORRECT ALL OF THESE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. PHONETIC SUBSTITUTIONS — steno theory produced a word that sounds similar:
   "bathe transcript" → "by the transcript"
   "depth have to" → "don't have to"
   "ankle of the drill" → "angle of the drill"
   "wheels" → "wells" (oil and gas context)
   "writes offering" → "rights offering"
   "brat spot" → "bright spot" (seismic term)
   "hey" → "hay" (farming context)
   "ghee sciences" → "geoscience"
   "stand forward" → "Stanford"
   "debris or certification" → "degree or certification"
   "vibrate ores" → "vibrators"
   "try angels" → "triangles"
   "signature named" → "significant named"
   "done" → "gone" (in context "they would have gone to")
   "Become in the day" → "Back in the day"
   "check silver mines" → "Sulphur Mines" (proper noun, phonetic error)
   "Collect check" → "Correct"
   "accept this slide to" → "sent this slide to"
   "odd" → "on" (e.g., "based odd this" → "based on this")

2. HOMOPHONES — steno wrote the wrong same-sounding word:
   "there" → "their" (possessive context)
   "whole" → "hole" (drilling context: "straight-hole")
   "mine" → "mind" ("in my mind")
   "very" → "V" (when referring to a letter of the alphabet)
   "hey" → "hay" (farming/agriculture context)
   "weep" → "we" ("weep want" → "we want")
   "write_up" → "right up" (e.g., "drilling right up to the salt")
   "why are" → "YR" (Bates prefix phonetic)

3. DROPPED LETTERS OR SYLLABLES:
   "acquisition an development" → "acquisition and development"
   "don't know how far way" → "don't know how far away"
   "personal" → "personally"
   "expand had" → "expanded"
   "weep" → "we"

4. SPLIT WORD ERRORS — one word broken into two (or more):
   "a dressed" → "addressed"
   "cavern s" → "caverns"
   "ie it announces" → "it announces" ("ie" is a steno artifact)
   "T he settlement" → "the settlement"
   "Board ofDescribe the ores meeting" → "Board of Directors meeting"
   "blacktop" → "White Top" (company name — "black" is phonetic for "White")

5. MERGED / RUN-ON WORDS — separate words joined without space:
   "ofYellow Rock" → "of Yellow Rock"
   "IM D" → "IMD" (acronym spacing artifact)

6. NUMERAL AND PUNCTUATION ARTIFACTS:
   "I mean0 Commissioner" → "I mean, Commissioner" (numeral 0 = comma)
   "12 '06 p.m." → "12:06 p.m." (apostrophe artifact → colon in times)
   "'9:58 a.m." → "9:58 a.m." (leading apostrophe before time)
   "that right? . Okay." → "that right? Okay." (rogue period after punctuation)
   "You asked me that. ." → "You asked me that." (double period)
   "disaster relief and SBA,," → "disaster relief and SBA," (double comma)
   "Okay U?" → "Okay." ("U?" is a steno artifact)
   "28 today period" → "28-day period" ("today" garble of "day")
   "3230 on three" → "323003" (steno split of Bates number)
   "_ _" (two underscores with space) → "—" (em dash)

7. MULTI-WORD GARBLES — steno theory completely broke down for a phrase:
   "tap California manager" → "typical manager"
   "geneos" → "gone"
   "toss that particular" → "to that particular"
   "Oliver resin mar sol" → "Alvarez and Marsal" (firm name)
   "B bone" → "Burt Bowen" (if confirmed by context)
   "lawyer a" → "Laura" (e.g., Hurricane Laura)
   "REV rent signal energy" → "Revenant Signal Energy" (company name)
   "vis_ _vis" → "vis-à-vis"
   "financed if you can" → "and if you can" ("financed" is an intruding artifact)
   "say eye we" → "—I would say we" (self-correction garble)
   "First Getty M.D. approval" → "First get IMD approval"

8. NAME / PROPER NOUN GARBLES — verify by context or explicit spelling in transcript:
   Always log these; use MEDIUM if confirmed only by context, HIGH if spelled out.

9. Q./A. ATTRIBUTION ISSUES:
   If a question and answer appear merged without proper separation, tag:
   [REVIEW: Q./A. FORMAT — question and answer run together; needs separation]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERBATIM SPEECH RULES — DO NOT CORRECT THESE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEVER change:
- Witness's colloquial or grammatically imperfect but intentional speech
- Self-corrections (witness says "The—the thing I mean is...") — keep as-is
- Hesitation words (uh, um) — preserve unless reporter prefers to remove
- Idioms and informal phrasing ("I handed off the ball", "nothing burger")
- Quoted language the witness is reading from a document
- Any speech that sounds natural even if grammatically imperfect

When you identify something as verbatim (no correction needed):
- Keep the text unchanged
- Log: confidence = "N/A", reason = "Verbatim — [brief explanation]"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MARGIE WAKEMAN WELLS PUNCTUATION STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Apply when correcting punctuation artifacts:
- Direct address always gets commas: "I know, sir, that..." / "Your Honor, I ask..."
- Comma BEFORE AND AFTER state name when sentence continues:
  CORRECT:   "in Houston, Texas, to visit"
  INCORRECT: "in Houston, Texas to visit"
- Em dash (—) for interruptions and self-corrections; no surrounding spaces
- Ellipsis (...) for trailing off
- Period after Q. and A. labels is part of the label format — do not remove

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFIDENCE LEVELS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HIGH   — Certain from context, established pattern, factual confirmation,
         or spelling confirmed elsewhere in the transcript.
MEDIUM — Likely correct but context is ambiguous. INSERT [REVIEW: note]
         in the corrected_text at that location. Reporter must verify audio.
LOW    — Possible correction. Flagged for reporter. Do not apply silently.
         INSERT [REVIEW: note] in the corrected_text.
N/A    — Verbatim rule applies. No change made.

For MEDIUM and LOW: always insert [REVIEW: your brief note] inline in the
corrected_text so the reporter can find it in a single pass.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — RETURN ONLY VALID JSON, NO PREAMBLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "corrected_text": "the full corrected chunk text, preserving all paragraph breaks exactly",
  "corrections": [
    {
      "line_approx": 44,
      "original": "exact text as it appears in the input chunk",
      "corrected": "corrected text",
      "confidence": "HIGH",
      "reason": "brief explanation: error type and why this correction is correct"
    }
  ]
}

Rules:
- corrected_text must preserve all blank lines between paragraphs as in input
- If no corrections found in this chunk, return "corrections": []
- line_approx is the absolute line number in the full document (you are told the start line)
- Log each error instance as a separate corrections entry
- For MEDIUM/LOW items, the [REVIEW: ...] tag appears in corrected_text AND in the log entry
"""


# ─────────────────────────────────────────────────────────────────────────────
# CHUNKING
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(text, target_size=CHUNK_TARGET):
    """Split text into chunks at paragraph (blank-line) boundaries."""
    paragraphs = re.split(r'\n\n+', text)
    chunks = []
    current = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para) + 2  # +2 for separator
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
    """Approximate absolute starting line number for chunk at chunk_index."""
    preceding = '\n\n'.join(chunks[:chunk_index])
    return preceding.count('\n') + 1


# ─────────────────────────────────────────────────────────────────────────────
# API CALL
# ─────────────────────────────────────────────────────────────────────────────

def correct_chunk(client, chunk_content, line_start, chunk_num, total_chunks):
    """Send one chunk to Claude. Returns (corrected_text_str, corrections_list)."""
    user_msg = (
        f"Correct the following deposition transcript chunk.\n"
        f"Starting line (approximate in full document): {line_start}\n"
        f"Chunk {chunk_num + 1} of {total_chunks}\n\n"
        f"--- BEGIN CHUNK ---\n{chunk_content}\n--- END CHUNK ---\n\n"
        f"Return only valid JSON as specified."
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}]
            )
            raw = response.content[0].text.strip()

            # Strip markdown code fences if Claude wraps the JSON
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
                time.sleep(1)
            else:
                print(f'  [ERROR] JSON parse failed after retries — chunk kept as-is')
                return chunk_content, []

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] API error: {e}, retry {attempt + 1}...', flush=True)
                time.sleep(3)
            else:
                print(f'  [ERROR] API call failed — chunk kept as-is')
                return chunk_content, []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(INPUT_FILE):
        print(f'ERROR: Input file not found: {INPUT_FILE}')
        sys.exit(1)

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('ERROR: ANTHROPIC_API_KEY environment variable not set.')
        print('       Windows: set ANTHROPIC_API_KEY=sk-ant-...')
        sys.exit(1)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text(text)

    print('=' * 60)
    print('AI CORRECTION ENGINE')
    print(f'Model:  {MODEL}')
    print(f'Input:  {INPUT_FILE}  ({len(text):,} chars)')
    print(f'Chunks: {len(chunks)}  (~{CHUNK_TARGET} chars target each)')
    print('=' * 60)

    client = anthropic.Anthropic(api_key=api_key)
    all_corrections = []
    corrected_chunks = []

    for i, chunk in enumerate(chunks):
        line_start = line_start_for_chunk(text, i, chunks)
        pct = (i + 1) / len(chunks) * 100
        print(f'  [{i+1:3d}/{len(chunks)}]  ~line {line_start:<6}  {pct:5.1f}%', end='', flush=True)

        corrected, corrections = correct_chunk(client, chunk, line_start, i, len(chunks))
        corrected_chunks.append(corrected)
        all_corrections.extend(corrections)

        n = len(corrections)
        print(f'  +{n} correction{"s" if n != 1 else ""}')

        if i < len(chunks) - 1:
            time.sleep(INTER_CHUNK_DELAY)

    corrected_text = '\n\n'.join(corrected_chunks)

    # Write corrected text
    with open(OUTPUT_TEXT, 'w', encoding='utf-8') as f:
        f.write(corrected_text)

    # Write correction log
    log_data = {
        "engine":            "ai_engine.py",
        "model":             MODEL,
        "input_file":        INPUT_FILE,
        "input_chars":       len(text),
        "output_chars":      len(corrected_text),
        "total_corrections": len(all_corrections),
        "corrections":       all_corrections
    }
    with open(OUTPUT_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    # Summary
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

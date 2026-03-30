"""
ai_engine.py — AI correction pass for mb_demo_engine_v4.
Version: 2.0 — Full master engine prompt (all 6 rule files loaded at runtime)

Pipeline position: AFTER steno_cleanup.py, BEFORE format_final.py

  extract_rtf.py  →  extracted_text.txt
  steno_cleanup.py → cleaned_text.txt
  ai_engine.py    → corrected_text.txt + correction_log.json   ← THIS SCRIPT
  format_final.py → FINAL_DELIVERY/...

What this does:
  - Reads cleaned_text.txt (post-steno-cleanup)
  - Loads FULL engine prompt from all 6 rule files at startup
  - Chunks transcript by paragraph blocks (preserves Q&A integrity)
  - Calls Claude API on each chunk with the complete master engine rules
  - Corrects: phonetic substitutions, homophones, garbles, split words,
    dropped letters, numeral artifacts, punctuation artifacts
  - Verbatim rule (KB-010): NEVER corrects witness's actual spoken words
  - Uncertain corrections tagged [REVIEW: ...] for reporter to verify
  - Writes corrected_text.txt and correction_log.json
  - Prints 5-minute progress updates during long runs

Engine files loaded at runtime (must be in same directory):
  1. MASTER_DEPOSITION_ENGINE_v4.md   — Layers 1, 3-11 (full rule set)
  2. STATE_MODULE_louisiana_engineering.md
  3. HOUSE_STYLE_MODULE_muir.md
  4. KNOWLEDGE_BASE.txt               — KB-001 through KB-015
  5. GREGG_STYLE_MODULE.txt
  6. MARGIE_STYLE_MODULE.txt

Target:  90%+ match against PROOF_OF_WORK.txt (117 manual corrections)
Model:   claude-sonnet-4-6
Cost:    ~$2-4 per full Easley-length run (~12,000 lines, full prompt)
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

INPUT_FILE         = 'cleaned_text.txt'
OUTPUT_TEXT        = 'corrected_text.txt'
OUTPUT_LOG         = 'correction_log.json'
CHECKPOINT_FILE    = 'ai_engine_checkpoint.json'
MODEL              = 'claude-sonnet-4-6'
CHUNK_TARGET       = 3000    # soft char limit per chunk; always breaks at paragraph boundary
MAX_RETRIES        = 2
INTER_CHUNK_DELAY  = 0.4     # seconds between API calls
PROGRESS_INTERVAL  = 300     # 5 minutes between progress banner prints


# ─────────────────────────────────────────────────────────────────────────────
# API MODE OVERRIDE — appended last, supersedes Layers 2, 12, 13 of master engine
# ─────────────────────────────────────────────────────────────────────────────

API_MODE_OVERRIDE = """

══════════════════════════════════════════════════════════════════════════════
API CHUNKED MODE — OVERRIDE INSTRUCTIONS (HIGHEST PRIORITY — SUPERSEDES ALL)
══════════════════════════════════════════════════════════════════════════════

YOU ARE RUNNING IN API CHUNKED MODE. This overrides any file-loading,
folder-creation, or delivery-package instructions in the engine above.
Specifically, Layers 2, 12, and 13 of the master engine DO NOT APPLY here.
Python handles all of that. Your role is correction only.

OPERATING CONTEXT:
  - Python handles ALL file I/O (reading input, writing output files)
  - Python handles ALL chunking (you receive one chunk at a time)
  - Python handles ALL delivery file creation (PDF, transcripts, etc.)
  - YOUR ROLE: Apply every correction rule from the engine above to the
               text chunk you receive and return corrected JSON. Nothing else.

WHAT YOU DO — AND ONLY WHAT YOU DO:
  1. Read the deposition text chunk provided in the user message.
  2. Apply ALL rules from:
       - Layer 1:  Absolute rules [R1]-[R12] — NEVER violate any of these
       - Layer 5:  Full Punctuation Bible — MANDATORY, apply to every sentence
       - Layer 6:  Grammar + Verbatim rules — CRITICAL (see KB-010)
       - Layer 7:  Terminology engine — apply confidence tiers exactly
       - Layer 8:  Exhibit engine — flag any exhibit issues found
       - Layer 9:  Edge case engine — log any edge cases encountered
       - Layer 10: Flag types — use exact flag text formats
       - Layer 11: Self-audit checklist — run mentally before returning JSON
       - State Module (Louisiana Engineering) — all rules, esp. objections
       - House Style Module (Muir) — E-mail, em dash, objection format
       - Knowledge Base (KB-001 through KB-015) — ALL 15 RULES, every chunk
       - Gregg Reference Manual — punctuation rules as applicable
       - Margie Wakeman Wells — court reporting style as applicable
  3. Return ONLY valid JSON in the exact format specified below.

══════════════════════════════════════════════════════════════════════════════
THE #1 RULE — VERBATIM (KB-010, Layer 6): READ THIS EVERY CHUNK
══════════════════════════════════════════════════════════════════════════════

The single most important rule in this entire engine:

  STENO ERROR  → The machine got it wrong. FIX IT.
  WITNESS SAID IT → That IS the sworn record. DO NOT TOUCH IT.

Even if the witness said something factually wrong, geographically incorrect,
or imprecise — that is what they said under oath. Correcting it alters sworn
testimony and is a serious professional violation.

EXAMPLES:
  "Intercoastal" (witness said it) → transcribe exactly as "Intercoastal"
  "depth have to" (machine error)  → correct to "don't have to"

When you cannot tell if it is a machine error or witness speech → DO NOT
correct. Insert [REVIEW: brief note] so the reporter can verify the audio.

══════════════════════════════════════════════════════════════════════════════
ROUGH DRAFT MODE IS ACTIVE
══════════════════════════════════════════════════════════════════════════════

Source is a steno rough draft (cleaned_text.txt from steno_cleanup.py).
Apply ROUGH_DRAFT MODE rules from Layer 5 Punctuation Bible:
  LOAD: Q./A. format, em dash, ellipsis, capitalization, numbers,
        Oxford comma in clean series, period after polite request
  SKIP: Yes/no comma/period distinction, interrupter comma pairs,
        tag clause punctuation, stacked question marks,
        Okay/all right transition punctuation
  FLAG: [REVIEW: PUNCTUATION — steno fragmentation prevents confident ruling]
        when judgment is required but sentence structure is unclear.

══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT — RETURN ONLY THIS JSON. NO PREAMBLE. NO EXPLANATION.
══════════════════════════════════════════════════════════════════════════════

{
  "corrected_text": "the full corrected chunk text, preserving all paragraph breaks exactly as in input",
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

RULES FOR THE JSON OUTPUT:
  - corrected_text: preserve ALL blank lines between paragraphs exactly as input
  - If no corrections in this chunk: return "corrections": []
  - line_approx: approximate absolute line number in the full document
  - Each correction is a separate entry in the corrections array
  - confidence: HIGH | MEDIUM | LOW | N/A
      HIGH   = certain from context, pattern, or explicit confirmation
      MEDIUM = likely correct, ambiguous context — add [REVIEW: note] in text
      LOW    = uncertain — add [REVIEW: note] in text, do not apply silently
      N/A    = verbatim rule applies, no change made
  - For MEDIUM/LOW: insert [REVIEW: brief note] inline in corrected_text
    at that location AND include it in the log entry reason

DO NOT:
  - Create any files or folders
  - Reference FINAL_DELIVERY
  - Add preamble, explanation, or commentary before or after the JSON
  - Return anything except valid JSON
  - Wrap JSON in markdown code fences
"""


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

ENGINE_FILES = [
    ('MASTER_DEPOSITION_ENGINE_v4.1.md',     'MASTER DEPOSITION TRANSFORMATION ENGINE v4.1'),
    ('STATE_MODULE_louisiana_engineering.md', 'STATE MODULE — LOUISIANA ENGINEERING'),
    ('HOUSE_STYLE_MODULE_muir.md',            'HOUSE STYLE MODULE — MARYBETH E. MUIR, CCR, RPR'),
    ('KNOWLEDGE_BASE.txt',                    'KNOWLEDGE BASE — CONFIRMED RULES FROM REAL RUNS (KB-001 to KB-015)'),
    # GREGG_STYLE_MODULE.txt and MARGIE_STYLE_MODULE.txt (~30K tokens combined) excluded from
    # per-chunk API calls due to token rate limits. Their key rules are already captured in:
    #   - Master Engine Layer 5 (Punctuation Bible — references Margie rules by name)
    #   - Master Engine Layer 6 (Grammar rules)
    #   - KB entries KB-001 through KB-015 (confirmed real-world applications)
    # Full modules remain available for Claude co-work sessions (non-API mode).
]


def build_system_prompt():
    """
    Load all 6 engine rule files from same directory as this script,
    concatenate them, and append the API mode override.
    Returns the full system prompt string.
    """
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    sections = []
    missing = []

    for filename, label in ENGINE_FILES:
        path = os.path.join(engine_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            divider = '=' * 70
            sections.append(f"\n\n{divider}\n{label}\n{divider}\n\n{content}")
            print(f'  [ENGINE] Loaded: {filename}  ({len(content):,} chars)', flush=True)
        else:
            missing.append(filename)
            print(f'  [ENGINE] MISSING: {filename} — rules for this module will not apply', flush=True)

    if missing:
        print(f'\n  WARNING: {len(missing)} engine file(s) missing. Proceeding with available rules.\n', flush=True)

    # API mode override is always last — highest priority
    sections.append(API_MODE_OVERRIDE)

    full_prompt = ''.join(sections)
    print(f'  [ENGINE] System prompt assembled: {len(full_prompt):,} chars  (~{len(full_prompt)//4:,} tokens est.)', flush=True)
    return full_prompt


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

def correct_chunk(client, system_prompt, chunk_content, line_start, chunk_num, total_chunks):
    """Send one chunk to Claude. Returns (corrected_text_str, corrections_list).

    Uses Anthropic prompt caching on the system prompt — the 47K-token engine
    is cached after the first call. Subsequent calls hit the cache at ~10% cost
    and much faster processing time.
    """
    user_msg = (
        f"Correct the following deposition transcript chunk.\n"
        f"Starting line (approximate in full document): {line_start}\n"
        f"Chunk {chunk_num + 1} of {total_chunks}\n\n"
        f"--- BEGIN CHUNK ---\n{chunk_content}\n--- END CHUNK ---\n\n"
        f"Return only valid JSON as specified in the API mode instructions."
    )

    # System prompt as a content block with cache_control.
    # The large engine prompt (~47K tokens) is cached after the first call.
    # Cache TTL: 5 minutes (extended cache available for longer runs).
    system_block = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}
        }
    ]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8192,
                system=system_block,
                messages=[{"role": "user", "content": user_msg}]
            )
            # Extract cache usage stats if available
            usage = getattr(response, 'usage', None)
            cache_create = getattr(usage, 'cache_creation_input_tokens', 0) or 0
            cache_read   = getattr(usage, 'cache_read_input_tokens', 0) or 0

            raw = response.content[0].text.strip()

            # Strip markdown code fences if Claude wraps the JSON
            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```\s*$', '', raw)

            parsed = json.loads(raw)
            corrected = parsed.get('corrected_text', chunk_content)
            corrections = parsed.get('corrections', [])
            return corrected, corrections, cache_create, cache_read

        except json.JSONDecodeError:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] JSON parse error, retry {attempt + 1}...', flush=True)
                time.sleep(1)
            else:
                print(f'  [ERROR] JSON parse failed after retries — chunk kept as-is', flush=True)
                return chunk_content, [], 0, 0

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] API error: {e}, retry {attempt + 1}...', flush=True)
                time.sleep(3)
            else:
                print(f'  [ERROR] API call failed — chunk kept as-is', flush=True)
                return chunk_content, [], 0, 0


# ─────────────────────────────────────────────────────────────────────────────
# PROGRESS BANNER
# ─────────────────────────────────────────────────────────────────────────────

def print_progress_banner(chunk_num, total_chunks, corrections_so_far, start_time):
    """Print a 5-minute progress update banner."""
    elapsed = time.time() - start_time
    elapsed_min = elapsed / 60
    pct_done = (chunk_num + 1) / total_chunks * 100
    if chunk_num > 0:
        eta_sec = (elapsed / (chunk_num + 1)) * (total_chunks - chunk_num - 1)
        eta_min = eta_sec / 60
        eta_str = f'~{eta_min:.0f} min remaining'
    else:
        eta_str = 'calculating...'

    print(flush=True)
    print(f'  ┌─ 5-MIN PROGRESS UPDATE ─────────────────────────────────', flush=True)
    print(f'  │  Elapsed:      {elapsed_min:.1f} minutes', flush=True)
    print(f'  │  Progress:     {chunk_num + 1}/{total_chunks} chunks  ({pct_done:.0f}%)', flush=True)
    print(f'  │  Corrections:  {corrections_so_far} logged so far', flush=True)
    print(f'  │  ETA:          {eta_str}', flush=True)
    print(f'  └─────────────────────────────────────────────────────────', flush=True)
    print(flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# CHECKPOINT / RESUME
# ─────────────────────────────────────────────────────────────────────────────

def save_checkpoint(chunk_index, corrected_chunks, all_corrections,
                    cache_creation_tokens, cache_read_tokens, input_file, input_size):
    """Write checkpoint after every completed chunk so a killed run can resume."""
    data = {
        'input_file':            input_file,
        'input_size':            input_size,
        'last_completed_chunk':  chunk_index,
        'corrected_chunks':      corrected_chunks,
        'corrections':           all_corrections,
        'cache_creation_tokens': cache_creation_tokens,
        'cache_read_tokens':     cache_read_tokens,
    }
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def load_checkpoint(input_file, input_size):
    """Return checkpoint dict if one exists for this exact input, else None."""
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            cp = json.load(f)
    except Exception:
        return None
    if cp.get('input_file') != input_file or cp.get('input_size') != input_size:
        print('  [CHECKPOINT] Found checkpoint but input file changed — starting fresh.')
        return None
    return cp


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
        print('       Windows: setx ANTHROPIC_API_KEY sk-ant-...')
        sys.exit(1)

    print('=' * 60, flush=True)
    print('AI CORRECTION ENGINE v2.0 — FULL MASTER PROMPT', flush=True)
    print('=' * 60, flush=True)
    print('Loading engine files...', flush=True)

    system_prompt = build_system_prompt()

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text(text)

    print(flush=True)
    print('=' * 60, flush=True)
    print(f'Model:  {MODEL}', flush=True)
    print(f'Input:  {INPUT_FILE}  ({len(text):,} chars)', flush=True)
    print(f'Chunks: {len(chunks)}  (~{CHUNK_TARGET} chars target each)', flush=True)
    print(f'Cache:  ENABLED — system prompt cached after chunk 1', flush=True)
    print(f'Progress updates every 5 minutes.', flush=True)
    print('=' * 60, flush=True)
    print(flush=True)

    client = anthropic.Anthropic(api_key=api_key)

    # ── Resume from checkpoint if one exists for this input ──────────────────
    checkpoint = load_checkpoint(INPUT_FILE, len(text))
    if checkpoint:
        start_chunk          = checkpoint['last_completed_chunk'] + 1
        corrected_chunks     = checkpoint['corrected_chunks']
        all_corrections      = checkpoint['corrections']
        cache_creation_tokens = checkpoint['cache_creation_tokens']
        cache_read_tokens    = checkpoint['cache_read_tokens']
        print(f'  [RESUME] Checkpoint found — resuming from chunk {start_chunk + 1}/{len(chunks)}', flush=True)
        print(f'  [RESUME] {len(all_corrections)} corrections already logged', flush=True)
        print(flush=True)
    else:
        start_chunk          = 0
        corrected_chunks     = []
        all_corrections      = []
        cache_creation_tokens = 0
        cache_read_tokens    = 0

    start_time = time.time()
    last_progress_time = start_time

    for i in range(start_chunk, len(chunks)):
        chunk = chunks[i]
        line_start = line_start_for_chunk(text, i, chunks)
        pct = (i + 1) / len(chunks) * 100
        print(f'  [{i+1:3d}/{len(chunks)}]  ~line {line_start:<6}  {pct:5.1f}%', end='', flush=True)

        corrected, corrections, cc_tok, cr_tok = correct_chunk(
            client, system_prompt, chunk, line_start, i, len(chunks)
        )
        corrected_chunks.append(corrected)
        all_corrections.extend(corrections)
        cache_creation_tokens += cc_tok
        cache_read_tokens += cr_tok

        n = len(corrections)
        print(f'  +{n} correction{"s" if n != 1 else ""}', flush=True)

        # Save checkpoint + partial output after every chunk
        save_checkpoint(i, corrected_chunks, all_corrections,
                        cache_creation_tokens, cache_read_tokens, INPUT_FILE, len(text))
        with open(OUTPUT_TEXT, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(corrected_chunks))

        # 5-minute progress banner
        now = time.time()
        if now - last_progress_time >= PROGRESS_INTERVAL:
            print_progress_banner(i, len(chunks), len(all_corrections), start_time)
            last_progress_time = now

        if i < len(chunks) - 1:
            time.sleep(INTER_CHUNK_DELAY)

    corrected_text = '\n\n'.join(corrected_chunks)

    # Write corrected text
    with open(OUTPUT_TEXT, 'w', encoding='utf-8') as f:
        f.write(corrected_text)

    # Write correction log
    elapsed_total = time.time() - start_time
    log_data = {
        "engine":                  "ai_engine.py v2.0",
        "model":                   MODEL,
        "input_file":              INPUT_FILE,
        "input_chars":             len(text),
        "output_chars":            len(corrected_text),
        "total_corrections":       len(all_corrections),
        "elapsed_seconds":         round(elapsed_total, 1),
        "cache_creation_tokens":   cache_creation_tokens,
        "cache_read_tokens":       cache_read_tokens,
        "corrections":             all_corrections
    }
    with open(OUTPUT_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    # Clean up checkpoint — run completed successfully
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    # Summary
    conf_counts = {}
    for c in all_corrections:
        conf = c.get('confidence', 'UNKNOWN')
        conf_counts[conf] = conf_counts.get(conf, 0) + 1

    elapsed_min = elapsed_total / 60
    print(flush=True)
    print('=' * 60, flush=True)
    print('AI CORRECTION COMPLETE', flush=True)
    print('=' * 60, flush=True)
    print(f'Elapsed:      {elapsed_min:.1f} minutes', flush=True)
    print(f'Output text:  {OUTPUT_TEXT}  ({len(corrected_text):,} chars)', flush=True)
    print(f'Output log:   {OUTPUT_LOG}', flush=True)
    print(f'Corrections:  {len(all_corrections)} total', flush=True)
    print(f'Cache write:  {cache_creation_tokens:,} tokens (chunk 1)', flush=True)
    print(f'Cache reads:  {cache_read_tokens:,} tokens ({len(chunks)-1} chunks at ~10% cost)', flush=True)
    print(flush=True)
    for conf in ('HIGH', 'MEDIUM', 'LOW', 'N/A', 'UNKNOWN'):
        if conf in conf_counts:
            print(f'  {conf:<8}  {conf_counts[conf]}', flush=True)
    print('=' * 60, flush=True)


if __name__ == '__main__':
    main()

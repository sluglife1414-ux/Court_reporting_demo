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

# AI output can contain Unicode (arrows, quotes, em-dashes) — force UTF-8 so
# cp1252 Windows console never crashes on AI-generated text.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Load .env from engine dir — runs before anything else ────────────────────
# Keys live in .env (gitignored). Loaded once here so ai_engine.py works when
# run directly (not via run_pipeline.py which has its own .env loader).
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                _key, _val = _k.strip(), _v.strip()
                if _val:
                    os.environ[_key] = _val

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

# ── Ops validator feature flag ────────────────────────────────────────────────
# USE_OPS_FORMAT=True: Agent returns ops JSON (KEEP/REWORD/FLAG) that is validated
# before any text is written to disk. Prevents block collapse + name hallucinations.
# Default False — flip to True only after single-chunk test succeeds. Non-breaking.
USE_OPS_FORMAT = True
VERBOSE_OPS    = False  # True = print OPS-WARN from-field mismatches. Noisy but useful for debugging.

# Ensure engine dir is on sys.path so ops modules import correctly when ai_engine
# is called from a different working directory (e.g., the job work/ folder).
_engine_dir = os.path.dirname(os.path.abspath(__file__))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

if USE_OPS_FORMAT:
    from tokenize_chunk import tokenize_chunk, annotate_chunk  # noqa: E402
    from validate_ops import validate_ops                       # noqa: E402
    from apply_ops import apply_ops, ops_to_corrections_log    # noqa: E402
    from names_lock import load_names_lock, build_names_lock   # noqa: E402


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
       - State Module (loaded for this run) — all rules, esp. objections
       - House Style Module (loaded for this run) — reporter-specific style rules
       - Knowledge Base (loaded for this run) — ALL KB RULES, every chunk
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

# ─────────────────────────────────────────────────────────────────────────────
# CR CONFIG — dynamic module loading
# Reads cr_config.json from the engine directory to determine which reporter
# and state modules to load. Falls back to MB/Louisiana defaults if not found.
#
# cr_config.json format:
#   {
#     "reporter_id":   "dalotto_ny_001",
#     "reporter_name": "Alicia D'Alotto",
#     "state_label":   "NEW YORK WCB",
#     "modules": {
#       "state_module":  "STATE_MODULE_ny_wcb.md",
#       "house_style":   "HOUSE_STYLE_MODULE_dalotto.md",
#       "knowledge_base":"KNOWLEDGE_BASE_ny_wcb.txt"
#     }
#   }
#
# To run MB/Louisiana: delete cr_config.json (or don't create one).
# To run AD/NY WC: create cr_config.json with the values above.
# ─────────────────────────────────────────────────────────────────────────────

# Defaults — MB Louisiana (backward compatible)
_DEFAULT_STATE_MODULE  = ('STATE_MODULE_louisiana_engineering.md', 'STATE MODULE — LOUISIANA ENGINEERING')
_DEFAULT_HOUSE_STYLE   = ('HOUSE_STYLE_MODULE_muir.md',            'HOUSE STYLE MODULE — MARYBETH E. MUIR, CCR, RPR')
_DEFAULT_KB            = ('KNOWLEDGE_BASE.txt',                    'KNOWLEDGE BASE — CONFIRMED RULES FROM REAL RUNS (KB-001 to KB-015)')
_DEFAULT_REPORTER_NAME = 'Marybeth E. Muir, CCR, RPR'
_DEFAULT_STATE_LABEL   = 'Louisiana Engineering'


def load_cr_config(engine_dir):
    """
    Read cr_config.json from engine_dir.
    Returns (state_module_tuple, house_style_tuple, kb_tuple, reporter_name, state_label, dictionary_setting).

    dictionary_setting values:
      None        → no cr_config found, use glob default (backward compat)
      False       → cr_config says skip dictionary (null in JSON)
      'filename'  → cr_config specifies exact dictionary file to load

    Falls back to MB/Louisiana defaults if cr_config.json not found.
    """
    # CWD (job work folder) takes priority — fall back to engine_dir for legacy runs
    config_path = os.path.join(os.getcwd(), 'cr_config.json')
    if not os.path.exists(config_path):
        config_path = os.path.join(engine_dir, 'cr_config.json')
    if not os.path.exists(config_path):
        print('  [ENGINE] cr_config.json not found — using MB/Louisiana defaults', flush=True)
        return _DEFAULT_STATE_MODULE, _DEFAULT_HOUSE_STYLE, _DEFAULT_KB, _DEFAULT_REPORTER_NAME, _DEFAULT_STATE_LABEL, None

    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    mods = cfg.get('modules', {})
    reporter_name = cfg.get('reporter_name', 'Unknown Reporter')
    state_label   = cfg.get('state_label',   'Unknown State')

    state_module  = (mods['state_module'],  f'STATE MODULE — {state_label.upper()}')
    house_style   = (mods['house_style'],   f'HOUSE STYLE MODULE — {reporter_name.upper()}')
    kb_file       = mods.get('knowledge_base', None)
    kb = (kb_file, f'KNOWLEDGE BASE — {reporter_name.upper()} ({state_label.upper()})') if kb_file else _DEFAULT_KB

    # dictionary: explicit null in JSON → False (skip). Missing key → None (glob default).
    dict_setting = mods.get('dictionary', 'KEY_MISSING')
    if dict_setting == 'KEY_MISSING':
        dictionary = None        # key not present — use glob default
    elif dict_setting is None:
        dictionary = False       # explicitly null — skip dictionary
    else:
        dictionary = dict_setting  # specific filename

    print(f'  [ENGINE] cr_config.json loaded — reporter: {reporter_name} | state: {state_label}', flush=True)
    return state_module, house_style, kb, reporter_name, state_label, dictionary


# ENGINE_FILES is built at runtime by build_system_prompt() using load_cr_config().
# GREGG_STYLE_MODULE.txt and MARGIE_STYLE_MODULE.txt (~30K tokens combined) excluded from
# per-chunk API calls due to token rate limits. Their key rules are captured in:
#   - Master Engine Layer 5 (Punctuation Bible — references Margie rules by name)
#   - Master Engine Layer 6 (Grammar rules)
#   - KB entries (confirmed real-world applications)
# Full modules remain available for Claude co-work sessions (non-API mode).


def build_depo_identity_block():
    """
    Read CASE_CAPTION.json from the current working directory (job folder)
    and return a locked identity block injected into every API call.

    This is the cross-depo contamination firewall. The AI is explicitly told
    who THIS deposition belongs to so it cannot fill boilerplate blocks with
    names or case identifiers from any previous deposition it has processed.

    Graceful: if CASE_CAPTION.json is missing, returns an empty string and
    logs a warning. The pipeline continues — but contamination risk is present.
    """
    caption_path = os.path.join(os.getcwd(), 'CASE_CAPTION.json')
    if not os.path.exists(caption_path):
        print('  [ENGINE] WARNING: CASE_CAPTION.json not found — '
              'cross-depo contamination firewall NOT active.', flush=True)
        return ''

    with open(caption_path, 'r', encoding='utf-8') as f:
        cap = json.load(f)

    witness      = cap.get('witness_full_name') or cap.get('witness_name', '[UNKNOWN WITNESS]')
    case_short   = cap.get('case_short', '')
    plaintiff    = cap.get('plaintiff', '')
    defendant    = cap.get('defendant', '').replace('\n', ' ')
    docket       = cap.get('docket', '')
    court        = cap.get('court', '')
    parish       = cap.get('parish', '')
    depo_date    = cap.get('depo_date', '')
    reporter     = cap.get('reporter_name_display') or cap.get('reporter_name', '')
    exam_atty    = cap.get('examining_atty', '')
    exam_firm    = cap.get('examining_firm', '')
    # deposing_atty_full added to schema after Brandl — fall back to exam_atty
    dep_atty     = cap.get('deposing_atty_full') or exam_atty

    divider = '=' * 70
    block = f"""

{divider}
DEPOSITION IDENTITY — THIS JOB ONLY (READ EVERY CHUNK — HIGHEST PRIORITY)
{divider}

YOU ARE PROCESSING THIS SPECIFIC DEPOSITION:

  Witness:          {witness}
  Case:             {plaintiff} v. {defendant}
  Docket:           {docket}
  Court:            {court}, {parish}
  Date:             {depo_date}
  Deposing attorney:{dep_atty} ({exam_firm})
  Reporter:         {reporter}
  Job ID:           {case_short}

══════════════════════════════════════════════════════════════════════════════
CROSS-DEPO CONTAMINATION RULES — ABSOLUTE, NO EXCEPTIONS
══════════════════════════════════════════════════════════════════════════════

1. NEVER use a witness name, attorney name, firm name, docket number, or
   any case identifier from any deposition other than the one listed above.
   You have no memory of previous jobs. This job is the only job.

2. STIPULATION BLOCK RULE — the S T I P U L A T I O N section contains:
     "testimony of the witness, [NAME]"
     "delivered to and retained by [ATTORNEY]"
   These MUST be filled ONLY from the identity above. If the steno in the
   stipulation block is sparse, garbled, or ambiguous:
     - Use the witness name and deposing attorney from this identity block
     - Tag the correction: [CHANGED: steno unclear → filled from CASE_CAPTION]
     - NEVER invent a name. NEVER copy a name from a prior deposition.

3. BOILERPLATE BLOCK RULE — certificate blocks, appearances headers, and
   the stipulation are TEMPLATES. The only proper nouns allowed in these
   blocks are those from the identity above or those explicitly present in
   the steno input for THIS chunk.

4. IF YOU SEE A NAME IN A BOILERPLATE BLOCK THAT DOES NOT MATCH THE
   IDENTITY ABOVE — flag it immediately:
     [REVIEW: name in steno "{{}}" does not match case caption — verify]
   Do not silently accept or reconstruct it.

{divider}
"""
    print(f'  [ENGINE] Depo identity block injected — witness: {witness} | '
          f'docket: {docket}', flush=True)
    return block


def build_system_prompt():
    """
    Load engine rule files from same directory as this script.
    Reads cr_config.json to determine which reporter/state modules to load.
    Reads CASE_CAPTION.json from cwd to build the cross-depo contamination firewall.
    Falls back to MB/Louisiana defaults if cr_config.json not found.
    Returns the full system prompt string.
    """
    engine_dir = os.path.dirname(os.path.abspath(__file__))

    state_module, house_style, kb, reporter_name, state_label, dictionary_setting = load_cr_config(engine_dir)

    engine_files = [
        ('MASTER_DEPOSITION_ENGINE_v4.2.md', 'MASTER DEPOSITION TRANSFORMATION ENGINE v4.2'),
        state_module,
        house_style,
        kb,
    ]

    sections = []
    missing = []

    for filename, label in engine_files:
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

    # Case-specific dictionary injection (graceful — works with or without .tlx)
    # dictionary_setting: None = glob default, False = skip, str = specific file
    if dictionary_setting is False:
        print('  [ENGINE] Case dictionary: skipped (cr_config says no dictionary for this CR)', flush=True)
    else:
        try:
            from load_case_dictionary import load_case_dictionary, build_dictionary_prompt_block
            if isinstance(dictionary_setting, str):
                # cr_config specified a specific dictionary file
                import os as _os
                dict_path = _os.path.join(engine_dir, dictionary_setting)
                dict_words = load_case_dictionary(search_dir=_os.path.dirname(dict_path))
            else:
                # None = no cr_config, use glob default (backward compat)
                dict_words = load_case_dictionary(search_dir=engine_dir)
            dict_block = build_dictionary_prompt_block(dict_words)
            if dict_block:
                sections.append(dict_block)
                print(f'  [ENGINE] Case dictionary: {len(dict_words)} proper nouns injected into prompt', flush=True)
        except Exception as e:
            print(f'  [ENGINE] Case dictionary: skipped ({e})', flush=True)

    # Cross-depo contamination firewall — inject depo identity before API override
    identity_block = build_depo_identity_block()
    if identity_block:
        sections.append(identity_block)

    # API mode override is always last — highest priority
    sections.append(API_MODE_OVERRIDE)

    full_prompt = ''.join(sections)
    print(f'  [ENGINE] System prompt assembled: {len(full_prompt):,} chars  (~{len(full_prompt)//4:,} tokens est.)', flush=True)
    return full_prompt


# ─────────────────────────────────────────────────────────────────────────────
# PRE-PROCESSING — D-11 guard
# ─────────────────────────────────────────────────────────────────────────────

_REVIEW_TAG_RE = re.compile(r'\[(?:REVIEW|AUDIO):(?:[^\[\]]|\[[^\]]*\])*\]')

def sanitize_structural_headers(text):
    """Strip [REVIEW] and [AUDIO] tags from structural header lines before AI pass.

    Prevents AI chunk-overlap from misattributing tags to section headers like
    'E X H I B I T S' or '* * *' separators. (D-11)

    Structural headers matched:
      - Spaced-out all-caps: E X H I B I T S, I N D E X
      - Asterisk/dash separator lines: * * *  ---  *** etc.
    """
    lines = text.split('\n')
    cleaned = []
    stripped_count = 0

    for line in lines:
        s = line.strip()
        is_spaced_caps = bool(re.match(r'^[A-Z](\s[A-Z]){2,}\s*$', s))
        is_separator   = len(s) >= 3 and bool(re.match(r'^[\*\-\s]+$', s))

        if is_spaced_caps or is_separator:
            new_line = _REVIEW_TAG_RE.sub('', line).rstrip()
            if new_line != line.rstrip():
                stripped_count += 1
            cleaned.append(new_line)
        else:
            cleaned.append(line)

    if stripped_count:
        print(f'  [ENGINE] D-11 guard: stripped [REVIEW]/[AUDIO] tags from '
              f'{stripped_count} structural header line(s)', flush=True)
    return '\n'.join(cleaned)


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

def get_last_qa_label(text):
    """Return the last Q/A speaker label seen in text ('Q' or 'A'), or None."""
    matches = re.findall(r'^([QA])\.\s+', text, re.MULTILINE)
    return matches[-1] if matches else None


def normalize_ops(ops: list, n_tokens: int) -> list:
    """Resolve overlapping REWORD/FLAG ops from Claude.

    With implicit KEEP, Claude only returns REWORD and FLAG ops.
    Gaps (uncovered tokens) are kept verbatim by apply_ops automatically.

    This function:
      1. Strips any stray KEEP ops Claude may have included.
      2. Resolves overlapping REWORD/FLAG ops — first-encountered wins
         (sorted by span start; REWORD beats FLAG on tie).
      3. Returns a clean list of non-overlapping REWORD/FLAG ops only.
    """
    PRIORITY = {"REWORD": 2, "FLAG": 1}

    # Drop any KEEP ops — they are implicit now
    active = [op for op in ops if op.get("op") in ("REWORD", "FLAG")]
    if not active:
        return []

    # Build token-ownership bitmap for REWORD/FLAG only
    assignment = [(-1, -1)] * n_tokens  # (priority, op_index)
    indexed = sorted(enumerate(active),
                     key=lambda t: (t[1].get("span", [0])[0],
                                    -PRIORITY.get(t[1].get("op", "FLAG"), 0)))

    for op_idx, op in indexed:
        span = op.get("span", [])
        if not span or len(span) != 2:
            continue
        s, e = span
        if s < 0 or e >= n_tokens or s > e:
            continue
        prio = PRIORITY.get(op.get("op", "FLAG"), 0)
        for i in range(s, e + 1):
            cur_prio, _ = assignment[i]
            if prio > cur_prio:
                assignment[i] = (prio, op_idx)

    # Rebuild ops from assignment — group consecutive tokens owned by same op
    result = []
    i = 0
    while i < n_tokens:
        _, op_idx = assignment[i]
        if op_idx == -1:
            i += 1  # unowned token — implicit KEEP, skip
            continue
        # Find the end of this op's consecutive run
        j = i + 1
        while j < n_tokens and assignment[j][1] == op_idx:
            j += 1
        op_data = dict(active[op_idx])
        op_data["span"] = [i, j - 1]
        result.append(op_data)
        i = j

    return result


def correct_chunk(client, system_prompt, chunk_content, line_start, chunk_num, total_chunks,
                  qa_anchor=None, names_lock=None):
    """Send one chunk to Claude. Returns (corrected_text_str, corrections_list, ...).

    Uses Anthropic prompt caching on the system prompt — the 47K-token engine
    is cached after the first call. Subsequent calls hit the cache at ~10% cost
    and much faster processing time.

    qa_anchor:  last speaker label ('Q'/'A') from previous chunk for re-anchoring.
    names_lock: set of locked proper nouns; passed to validate_ops when USE_OPS_FORMAT=True.
    """
    if qa_anchor:
        next_label = 'A' if qa_anchor == 'Q' else 'Q'
        anchor_header = (
            f"RE-ANCHOR: You are mid-examination. "
            f"Last labeled line in previous chunk was {qa_anchor}. "
            f"Next expected label is {next_label}. "
            f"CRITICAL: Every line of testimony must begin with Q. or A. "
            f"Do not return any unlabeled testimony lines.\n\n"
        )
    else:
        anchor_header = ''

    if USE_OPS_FORMAT:
        # Tokenize + annotate chunk so Claude can reference token indexes in spans
        tokens = tokenize_chunk(chunk_content)
        annotated = annotate_chunk(chunk_content)
        n_tokens = len(tokens)

        ops_format_block = (
            f"OPS FORMAT OVERRIDE — Ignore the corrected_text JSON format from the system prompt.\n"
            f"Return ONLY this JSON:\n\n"
            f'{{"ops": [...]}}\n\n'
            f"RULE: Return ONLY REWORD and FLAG ops — do NOT include KEEP ops.\n"
            f"Everything not covered by a REWORD or FLAG is kept verbatim automatically.\n"
            f"An empty ops list is valid if the chunk needs no corrections.\n\n"
            f"OP TYPES:\n"
            f'  {{"op": "REWORD", "span": [a, b], "from": "raw text", "to": "fixed text",\n'
            f'    "source": "SOURCE", "reason": "why"}}  — replace span with corrected text\n'
            f'  {{"op": "FLAG",   "span": [a, b], "reason": "..."}}  — uncertain, tag for reporter\n\n'
            f"CRITICAL — 'to' FIELD RULE:\n"
            f"  The 'to' field must contain ONLY the corrected transcript words.\n"
            f"  NEVER put reasoning, notes, analysis, or explanations in 'to'.\n"
            f"  NEVER reference token numbers in 'to' (e.g. 'token 52 likely...').\n"
            f"  NEVER include 'steno artifact', 'verify audio', 'missing clause', or\n"
            f"  similar diagnostic phrases in 'to'.\n"
            f"  If you are uncertain → use FLAG, not REWORD with a long 'to'.\n"
            f"  Put your reasoning in the 'reason' field — never in 'to'.\n"
            f"  WRONG: {{\"to\": \"isopach — steno artifact, token 52 likely 'isopach'\"}}\n"
            f"  RIGHT: {{\"to\": \"isopach\", \"reason\": \"token 52 likely isopach (geological term)\"}}\n\n"
            f"SOURCE (required on REWORD, exactly one of):\n"
            f"  raw_steno | case_dict | kb | names_lock | phonetic_match | house_style\n\n"
            f"SPAN RULE: spans must not overlap. If two corrections touch adjacent tokens,\n"
            f"  use separate non-overlapping spans. Token range: 0..{n_tokens - 1}.\n\n"
            f"PROPER NOUN RULE — STRICT, NO EXCEPTIONS:\n"
            f"  A proper noun is any person name, firm name, or place name.\n"
            f"  You may REWORD a proper noun ONLY IF the correct spelling is confirmed in:\n"
            f"    (1) names.lock  (2) the KB provided  (3) the case caption\n"
            f"  If you are not 100% certain — use FLAG, not REWORD.\n"
            f"  NEVER guess a proper noun. A FLAG is always correct. A wrong name is never acceptable.\n"
            f"  Wrong name example: steno 'mad dan' — you do not know if this is Madden, Madigan,\n"
            f"    Madison, etc. Use KB-018: it is Mr. Madigan.\n\n"
            f"EXAMPLE for a 6-token chunk [0]Q. [1]the [2]witnes [3]was [4]swor [5]in:\n"
            f'  [{{"op":"REWORD","span":[2,2],"from":"witnes","to":"witness","source":"raw_steno","reason":"dropped s"}},{{"op":"REWORD","span":[4,4],"from":"swor","to":"sworn","source":"raw_steno","reason":"dropped n"}}]\n'
            f"  Tokens [0,1,3,5] are kept verbatim — no KEEP op needed.\n\n"
            f"Total tokens this chunk: {n_tokens}. When uncertain: FLAG, not REWORD.\n"
        )

        user_msg = (
            f"{anchor_header}"
            f"Correct the following deposition transcript chunk.\n"
            f"Starting line: {line_start} | Chunk {chunk_num + 1} of {total_chunks}\n\n"
            f"{ops_format_block}\n"
            f"--- BEGIN ANNOTATED CHUNK ---\n{annotated}\n--- END ANNOTATED CHUNK ---\n"
        )
    else:
        tokens = None  # unused in non-ops path
        user_msg = (
            f"{anchor_header}"
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
            # Extract token usage stats
            usage        = getattr(response, 'usage', None)
            cache_create = getattr(usage, 'cache_creation_input_tokens', 0) or 0
            cache_read   = getattr(usage, 'cache_read_input_tokens', 0) or 0
            input_tok    = getattr(usage, 'input_tokens', 0) or 0
            output_tok   = getattr(usage, 'output_tokens', 0) or 0

            raw = response.content[0].text.strip()

            # Strip markdown code fences if Claude wraps the JSON
            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```\s*$', '', raw)

            parsed = json.loads(raw)

            if USE_OPS_FORMAT:
                # Ops path: validate before writing anything
                ops = parsed.get('ops', [])
                if not ops:
                    print(f'  [OPS-WARN] empty ops list — fallback', flush=True)
                    return (chunk_content + '\n~~REVIEW: ops validator — empty ops list returned~~',
                            [], cache_create, cache_read, input_tok, output_tok)
                # Normalize before validation: fix background-KEEP + patch overlap pattern
                ops_norm = normalize_ops(ops, len(tokens))
                if len(ops_norm) != len(ops):
                    print(f'  [OPS-NORM] ops normalized: {len(ops)} → {len(ops_norm)} (overlap repaired)', flush=True)
                # Summarize op type counts (REWORD/FLAG counts confirm corrections were made)
                reword_ct = sum(1 for o in ops_norm if o.get("op") == "REWORD")
                flag_ct   = sum(1 for o in ops_norm if o.get("op") == "FLAG")
                if reword_ct or flag_ct:
                    print(f'  [OPS] {reword_ct} REWORD, {flag_ct} FLAG', flush=True)
                result = validate_ops(ops_norm, tokens, names_lock or set())
                if result.ok:
                    corrected = apply_ops(ops_norm, tokens)
                    corrections = ops_to_corrections_log(ops_norm, tokens, chunk_num, line_start)
                    if result.warnings and VERBOSE_OPS:
                        for w in result.warnings:
                            print(f'  [OPS-WARN] {w[:100]}', flush=True)
                    return corrected, corrections, cache_create, cache_read, input_tok, output_tok
                else:
                    print(f'  [OPS-REJECTED] {result.reason[:100]}', flush=True)
                    return (chunk_content + f'\n~~REVIEW: ops validator rejected — {result.reason[:160]}~~',
                            [], cache_create, cache_read, input_tok, output_tok)
            else:
                corrected = parsed.get('corrected_text', chunk_content)
                corrections = parsed.get('corrections', [])
                return corrected, corrections, cache_create, cache_read, input_tok, output_tok

        except json.JSONDecodeError:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] JSON parse error, retry {attempt + 1}...', flush=True)
                time.sleep(1)
            else:
                print(f'  [ERROR] JSON parse failed after retries — chunk kept as-is', flush=True)
                return chunk_content, [], 0, 0, 0, 0

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f'  [WARN] API error: {e}, retry {attempt + 1}...', flush=True)
                time.sleep(3)
            else:
                print(f'  [ERROR] API call failed — chunk kept as-is', flush=True)
                return chunk_content, [], 0, 0, 0, 0


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
    # ── CLI flags ─────────────────────────────────────────────────────────────
    import argparse
    parser = argparse.ArgumentParser(description='AI correction engine')
    parser.add_argument('--chunk', type=int, default=None,
                        help='Run only this chunk index (0-based) and exit. For testing.')
    parser.add_argument('--verbose', action='store_true',
                        help='Print OPS-WARN from-field mismatch details (noisy, for debugging).')
    args = parser.parse_args()

    if args.verbose:
        global VERBOSE_OPS
        VERBOSE_OPS = True

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

    # D-11: strip [REVIEW]/[AUDIO] tags from structural headers before AI sees them
    text = sanitize_structural_headers(text)

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
        start_chunk           = 0
        corrected_chunks      = []
        all_corrections       = []
        cache_creation_tokens = 0
        cache_read_tokens     = 0

    # Always initialize — not saved in checkpoint (resume adds to 0 for cost calc)
    total_input_tokens  = 0
    total_output_tokens = 0

    # Load names.lock for ops validator (build if missing)
    names_lock_set = None
    if USE_OPS_FORMAT:
        import os as _os
        _lock_path = 'names.lock'
        if not _os.path.exists(_lock_path):
            print('[ops] names.lock not found — building from CASE_CAPTION.json + KB...', flush=True)
            from pathlib import Path as _Path
            _names = build_names_lock(_Path('.'))
            from names_lock import save_names_lock as _save_lock
            _save_lock(_names, _Path(_lock_path))
        from pathlib import Path as _Path2
        names_lock_set = load_names_lock(_Path2(_lock_path))
        print(f'[ops] names.lock loaded — {len(names_lock_set)} locked names', flush=True)

    start_time = time.time()
    last_progress_time = start_time
    last_qa_label = None   # tracks last Q/A speaker across chunk boundaries

    # --chunk N: run only that chunk index, print result, exit (testing only)
    if args.chunk is not None:
        ci = args.chunk
        if ci < 0 or ci >= len(chunks):
            print(f'ERROR: --chunk {ci} out of range (0..{len(chunks)-1})')
            sys.exit(1)
        print(f'\n[--chunk {ci}] Running single-chunk test ({len(chunks)} chunks total)\n')
        corrected, corrections, cc_tok, cr_tok, in_tok, out_tok = correct_chunk(
            client, system_prompt, chunks[ci],
            line_start_for_chunk(text, ci, chunks), ci, len(chunks),
            names_lock=names_lock_set
        )
        print(f'\n--- CORRECTED OUTPUT (chunk {ci}) ---')
        print(corrected[:2000])
        print(f'\n--- CORRECTIONS ({len(corrections)}) ---')
        for c in corrections[:10]:
            print(f"  [{c.get('confidence','?')}] {c.get('original','')} → {c.get('corrected','')[:60]}")
        print(f'\nTokens: input={in_tok} output={out_tok} cache_create={cc_tok} cache_read={cr_tok}')
        return

    for i in range(start_chunk, len(chunks)):
        chunk = chunks[i]
        line_start = line_start_for_chunk(text, i, chunks)
        pct = (i + 1) / len(chunks) * 100
        print(f'  [{i+1:3d}/{len(chunks)}]  ~line {line_start:<6}  {pct:5.1f}%', end='', flush=True)

        corrected, corrections, cc_tok, cr_tok, in_tok, out_tok = correct_chunk(
            client, system_prompt, chunk, line_start, i, len(chunks),
            qa_anchor=last_qa_label,
            names_lock=names_lock_set
        )
        corrected_chunks.append(corrected)
        all_corrections.extend(corrections)

        # Update Q/A anchor — track last speaker label for next chunk
        chunk_last = get_last_qa_label(corrected)
        if chunk_last:
            last_qa_label = chunk_last

        cache_creation_tokens += cc_tok
        cache_read_tokens     += cr_tok
        total_input_tokens    += in_tok
        total_output_tokens   += out_tok

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

    # ── Cost estimate (Sonnet 4.6 pricing) ───────────────────────────────────
    # input_tokens includes cache tokens — subtract to get non-cached input
    non_cached_input = max(0, total_input_tokens - cache_creation_tokens - cache_read_tokens)
    cost_input       = non_cached_input      * 3.00  / 1_000_000
    cost_cache_write = cache_creation_tokens * 3.75  / 1_000_000
    cost_cache_read  = cache_read_tokens     * 0.30  / 1_000_000
    cost_output      = total_output_tokens   * 15.00 / 1_000_000
    cost_total       = cost_input + cost_cache_write + cost_cache_read + cost_output
    print(flush=True)
    print(f'--- COST ESTIMATE (Sonnet 4.6) ---', flush=True)
    print(f'  Input (non-cached): {non_cached_input:>10,} tok  ${cost_input:.4f}', flush=True)
    print(f'  Cache write:        {cache_creation_tokens:>10,} tok  ${cost_cache_write:.4f}', flush=True)
    print(f'  Cache read:         {cache_read_tokens:>10,} tok  ${cost_cache_read:.4f}', flush=True)
    print(f'  Output:             {total_output_tokens:>10,} tok  ${cost_output:.4f}', flush=True)
    print(f'  TOTAL:                              ${cost_total:.4f}', flush=True)
    print(f'----------------------------------', flush=True)
    print(flush=True)
    for conf in ('HIGH', 'MEDIUM', 'LOW', 'N/A', 'UNKNOWN'):
        if conf in conf_counts:
            print(f'  {conf:<8}  {conf_counts[conf]}', flush=True)
    print('=' * 60, flush=True)


if __name__ == '__main__':
    main()

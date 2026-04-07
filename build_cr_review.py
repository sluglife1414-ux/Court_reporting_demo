"""
build_cr_review.py — CR 15-Minute Review Package
======================================================
Generates FINAL_DELIVERY/{case_short}_CR_REVIEW.txt

Design goal:
  CR opens the PDF and this file side by side.
  Every item has a PDF page number she can jump to.
  She should be done in 15 minutes.

What we show the CR:
  0 — Data integrity check  (4 phrases from raw → verified in final)
  A — 5 spot-check pages    (structure confirmation)
  B — Items she can fix RIGHT NOW without audio
       (name spellings, Bates issues, exhibit numbers, missing words)
  C — Filler words           (her preference, one decision applies to all)
  D — Audio-dependent items  (count only — she handles in her normal pass)
  E — Sign-off box

What we DO NOT show:
  - Garbage: engine internal notes that resolve themselves (index page numbers, etc.)
  - Dollar amounts / figures that require audio to fill in
  - Items the engine already corrected with high confidence
  - Any item without a clear actionable question

Author:  Scott + Claude
Version: 5.0  (2026-04-06) — real page numbers, smart Section B filter,
                              integrity check, specific questions for every item
"""

import json
import os
import re
from datetime import date

BASE = os.getcwd()  # job's work folder (set by run_pipeline.py --job-dir)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return default or {}


def truncate_at_word(s, max_len=65):
    """Truncate at word boundary — no mid-word cuts."""
    s = s.strip()
    if len(s) <= max_len:
        return s
    cut = s[:max_len].rsplit(' ', 1)[0]
    return cut + '...'


# ── Load config ───────────────────────────────────────────────────────────────

cfg       = load_json(os.path.join(BASE, 'depo_config.json'))
caption   = load_json(os.path.join(BASE, 'CASE_CAPTION.json'))
cfg.update(caption)
corr_data = load_json(os.path.join(BASE, 'correction_log.json'))
if isinstance(corr_data, list):
    corr_data = {'corrections': corr_data}
corr_list = corr_data.get('corrections', [])

CASE_SHORT = cfg.get('case_short', 'Case')
WITNESS    = caption.get('witness_name',          cfg.get('witness_name', 'WITNESS'))
DEPO_DATE  = caption.get('depo_date',             cfg.get('depo_date_short', ''))
REPORTER   = caption.get('reporter_name_display', 'Marybeth E. Muir')
DOCKET     = caption.get('docket',                cfg.get('docket', ''))
EXAMINING  = caption.get('examining_atty',        cfg.get('examining_atty', ''))


# ── Load FINAL_FORMATTED.txt — page/line reference map ───────────────────────

FORMATTED_PATH = os.path.join(BASE, 'FINAL_DELIVERY', f'{CASE_SHORT}_FINAL_FORMATTED.txt')
_flines = []
if os.path.exists(FORMATTED_PATH):
    with open(FORMATTED_PATH, encoding='utf-8') as f:
        _flines = f.read().split('\n')

# Build page map: formatted_line_index → page number
# Rule: page marker lines are BARE digits with NO leading whitespace ("2", "3").
# Content blank lines like " 4  " strip to "4" — they must NOT be treated as pages.
_page_at = {}
_cur_pg  = None
for _i, _raw in enumerate(_flines):
    _s = _raw.strip()
    if (_s.isdigit() and 1 <= int(_s) <= 9999
            and _raw.lstrip() == _raw):   # no leading whitespace = real page marker
        _cur_pg = int(_s)
    _page_at[_i] = _cur_pg
total_pages = max((v for v in _page_at.values() if v), default=0)


def find_page_for_text(snippet):
    """Search FINAL_FORMATTED for snippet. Return (page, line) or (None, None).

    - Strips [WORD] reconstruction markers from BOTH the snippet and each
      formatted line before comparing, so [see] in one matches see in the other.
    - Single-token path handles Bates numbers (YR-364101-354102, no spaces).
    - Multi-word path tries 3-5 word chunks at offsets 0-3 for line-wrap splits.
    - Line-number regex uses \\s+ (not \\s{1,3}) to handle 4-space indents.
    """
    clean = re.sub(r'\[([^\]]+)\]', r'\1', snippet)
    words = clean.lower().strip().split()
    if not words:
        return None, None

    # Single-token: Bates numbers, hyphenated refs, individual words in PASS* check
    if len(words) == 1 and len(words[0]) >= 5:
        target      = words[0]
        target_norm = re.sub(r"[-']", '', target)   # "write-off"→"writeoff", "wasn't"→"wasnt"
        for i, raw in enumerate(_flines):
            raw_norm  = re.sub(r'\[([^\]]+)\]', r'\1', raw.lower())
            raw_alpha = re.sub(r"[-']", '', raw_norm)  # strip hyphens/apostrophes for fuzzy match
            if target in raw_norm or target_norm in raw_alpha:
                pg = _page_at.get(i)
                m  = re.match(r'^\s{0,2}(\d{1,2})\s+', raw)
                return pg, (int(m.group(1)) if m else None)
        return None, None

    # Multi-word: try 3-5 word chunks at offsets 0-3
    for start in range(min(4, len(words))):
        for chunk_size in (5, 4, 3):
            chunk_words = words[start:start + chunk_size]
            if len(chunk_words) < 3:
                continue
            candidate = ' '.join(chunk_words)
            if len(candidate) < 6:
                continue
            for i, raw in enumerate(_flines):
                # Strip [WORD] markers from formatted line before comparing
                raw_norm = re.sub(r'\s+', ' ',
                                  re.sub(r'\[([^\]]+)\]', r'\1', raw.lower()))
                if candidate in raw_norm:
                    pg = _page_at.get(i)
                    m  = re.match(r'^\s{0,2}(\d{1,2})\s+', raw)
                    return pg, (int(m.group(1)) if m else None)
    return None, None


# ── SECTION 0 — DATA INTEGRITY CHECK ─────────────────────────────────────────

def run_integrity_check():
    """
    Pull one unique phrase at 25%, 50%, 75%, 100% of corrected_text.
    Verify each phrase appears in FINAL_FORMATTED.
    Returns list of 4 result dicts.
    """
    corr_path = os.path.join(BASE, 'corrected_text.txt')
    if not os.path.exists(corr_path) or not _flines:
        return []
    with open(corr_path, encoding='utf-8') as f:
        raw = f.read()
    # Strip all engine tags so we're searching clean testimony text
    clean = re.sub(r'\[REVIEW[^\]]*\]', '', raw)
    clean = re.sub(r'\[CORRECTED:[^\]]*\]', '', clean)
    clean = re.sub(r'\[([^\]]+)\]', r'\1', clean)
    # Collect content lines: skip headers, blanks, short lines, engine markers
    lines = []
    for ln in clean.split('\n'):
        ln = ln.strip()
        if len(ln) < 30:
            continue
        if ln.isupper():
            continue
        if ln.startswith('FLAG:') or ln.startswith('[FLAG'):
            continue
        if len(ln.split()) >= 6:
            lines.append(ln)
    if not lines:
        return []
    results = []
    for pct in [25, 50, 75, 100]:
        idx = max(0, min(int(len(lines) * pct / 100) - 1, len(lines) - 1))
        phrase = None
        # Scan back from checkpoint for a phrase with 6+ words and one long word
        for j in range(idx, max(0, idx - 20), -1):
            w = lines[j].split()
            if len(w) < 6:
                continue
            if not any(len(word.rstrip('.,;:')) > 5 for word in w):
                continue
            phrase = ' '.join(w[:8])
            break
        if phrase:
            pg, ln_num = find_page_for_text(phrase)
            results.append({
                'pct':    pct,
                'phrase': phrase,
                'found':  pg is not None,
                'page':   pg,
                'line':   ln_num,
            })
        else:
            results.append({
                'pct': pct, 'phrase': '(no phrase found)',
                'found': False, 'page': None, 'line': None,
            })
    return results

def _strip_rtf_codes(rtf_content):
    """Strip RTF control codes and return plain text. Reuses extract_rtf.py logic."""
    c = rtf_content
    c = re.sub(r'\{\\\*\\cx[^}]{0,200}\}', '', c)
    c = re.sub(r'\\cxsgdelsteno[01]', '', c)
    c = re.sub(r'\\cxfl\s*', '', c)
    c = re.sub(r'\\cxsingle\s*', '', c)
    c = re.sub(r'\\cxdouble\s*', '', c)
    c = re.sub(r'\\cxsgnocap\s*', '', c)
    c = re.sub(r'\\cxsgindex[0-9]+\s*', '', c)
    c = re.sub(r'\\cxsgmargin[0-9]+\s*', '', c)
    c = re.sub(r'\\cxsg[a-z]+[0-9]*\s*', '', c)
    c = re.sub(r'\\cx[a-z]+[0-9]*\s*', '', c)
    c = c.replace('\\line ', '\n').replace('\\line\n', '\n').replace('\\line', '\n')
    c = re.sub(r'\\pard[^\\{}\n]*', '\n', c)
    c = re.sub(r'\\par[\s\\]', '\n', c)
    c = c.replace('\\par', '\n').replace('\\tab', ' ')
    c = re.sub(r'\\[a-zA-Z]+-?[0-9]*\*?\s?', '', c)
    c = re.sub(r'\{[^{}]*\}', '', c)
    c = re.sub(r'[{}\\]', '', c)
    c = re.sub(r'[ \t]+', ' ', c)
    return c.strip()


_STOPWORDS = {
    'that', 'this', 'with', 'from', 'they', 'have', 'will', 'been', 'were',
    'your', 'what', 'when', 'then', 'also', 'said', 'just', 'into', 'than',
    'their', 'there', 'about', 'which', 'would', 'could', 'should', 'after',
    'before', 'those', 'these', 'some', 'more', 'very', 'well', 'right',
}


def run_10slice_check():
    """
    Pipeline acceptance test: divide the raw RTF into 10 equal slices,
    pull TWO independent phrases per slice (A from second half, B from first
    half), verify each appears in FINAL_FORMATTED.

    Independence rule: no word >= 5 chars may appear in more than one probe
    across all 20 probes. This is enforced by a global used_words set.

    Scoring (by slice, not probe):
      Slice PASS  — either probe found exactly
      Slice PASS* — no exact match, but distinctive words confirmed present
      Slice FAIL  — BOTH probes fail completely

      10/10  → DELIVER
       9/10  → DELIVER
       8/10  → HOLD — review failed slices before delivering
      <=7/10 → DO NOT DELIVER — pipeline failure

    Returns list of 10 result dicts, each with:
      slice   — slice number 1-10
      pct     — approximate position in depo (10, 20, ... 100)
      status  — combined 'PASS', 'PASS*', or 'FAIL'
      probes  — list of 2 dicts: label, phrase, status, page, line
    """
    import glob as _glob
    rtf_files = _glob.glob(os.path.join(BASE, '*.rtf'))
    if not rtf_files or not _flines:
        return []

    with open(rtf_files[0], encoding='utf-8', errors='replace') as f:
        raw_rtf = f.read()

    plain = _strip_rtf_codes(raw_rtf)

    # Build token list: alpha-only words, 3+ chars.
    # Strip apostrophes — contractions like "don't" → "dont" (4 chars)
    # won't qualify as distinctive, preventing false FAIL.
    tokens = []
    for w in plain.split():
        t = re.sub(r"[^a-zA-Z]", '', w).lower()
        if len(t) >= 3:
            tokens.append(t)

    if len(tokens) < 100:
        return []

    n_slices   = 10
    slice_size = len(tokens) // n_slices
    used_words = set()   # global: no distinctive word re-used across any probe

    def _pick_phrase(start_idx, stop_idx):
        """Scan backward from start_idx to stop_idx for a usable phrase.
        Skips any phrase whose distinctive words overlap with used_words.
        Updates used_words on success. Returns phrase string or None."""
        lo = max(stop_idx, 0)
        for j in range(start_idx, lo - 1, -1):
            chunk = tokens[j:j + 5]
            if len(chunk) < 5:
                continue
            distinctive = [w for w in chunk if len(w) >= 5 and w not in _STOPWORDS]
            if len(distinctive) < 2:
                continue
            if len(set(distinctive)) < len(distinctive):
                continue   # word repeats within this phrase
            if any(w in used_words for w in distinctive):
                continue   # word already used in another probe
            used_words.update(distinctive)
            return ' '.join(chunk)
        return None

    def _probe_result(label, phrase):
        """Check one phrase against FINAL_FORMATTED. Returns probe dict."""
        if not phrase:
            return {'label': label, 'phrase': '(no phrase)',
                    'status': 'FAIL', 'page': None, 'line': None}
        pg, ln = find_page_for_text(phrase)
        if pg is not None:
            return {'label': label, 'phrase': phrase,
                    'status': 'PASS', 'page': pg, 'line': ln}
        distinctive = [w for w in phrase.split() if len(w) >= 5 and w not in _STOPWORDS]
        all_found   = distinctive and all(
            find_page_for_text(dw)[0] is not None for dw in distinctive
        )
        status = 'PASS*' if all_found else 'FAIL'
        return {'label': label, 'phrase': phrase,
                'status': status, 'page': None, 'line': None}

    results = []
    for s in range(1, n_slices + 1):
        pct      = s * 10
        s_end    = min(s * slice_size - 1, len(tokens) - 6)
        s_start  = (s - 1) * slice_size
        midpoint = s_start + slice_size // 2

        # Probe A — second half of slice (end → midpoint)
        probe_a = _probe_result('A', _pick_phrase(s_end, midpoint))

        # Probe B — first half of slice (midpoint-1 → start), fully independent
        probe_b = _probe_result('B', _pick_phrase(midpoint - 1, s_start))

        # Combined slice status: best result of the two probes
        statuses = {probe_a['status'], probe_b['status']}
        if 'PASS' in statuses:
            combined = 'PASS'
        elif 'PASS*' in statuses:
            combined = 'PASS*'
        else:
            combined = 'FAIL'

        results.append({
            'slice':  s,
            'pct':    pct,
            'status': combined,
            'probes': [probe_a, probe_b],
        })

    return results


# Acceptance thresholds
_DELIVER_THRESHOLD = 9   # 9 or 10 out of 10 = deliver
_HOLD_THRESHOLD    = 8   # 8 out of 10 = hold for review


def slice_verdict(results):
    """Return (score, verdict_string) for the 10-slice check."""
    if not results:
        return 0, 'UNKNOWN'
    passed = sum(1 for r in results if r['status'] in ('PASS', 'PASS*'))
    total  = len(results)
    if passed >= _DELIVER_THRESHOLD:
        verdict = 'DELIVER'
    elif passed >= _HOLD_THRESHOLD:
        verdict = 'HOLD — review failed slices before delivering'
    else:
        verdict = 'DO NOT DELIVER — pipeline failure, investigate immediately'
    return passed, verdict


integrity_results  = run_integrity_check()   # kept for internal pipeline stats
slice_results      = run_10slice_check()


# ── Parse corrected_text.txt — find [REVIEW] items ───────────────────────────

CORRECTED_PATH = os.path.join(BASE, 'corrected_text.txt')
_clines = []
if os.path.exists(CORRECTED_PATH):
    with open(CORRECTED_PATH, encoding='utf-8') as f:
        _clines = f.read().split('\n')

# ── Categorization rules ──────────────────────────────────────────────────────

# GARBAGE — engine internal notes that should never reach MB
_GARBAGE = [
    'page number missing from index',   # formatter fills these automatically
    'year range broken across lines',   # internal formatting note
    'tense inconsistency',              # instruction was "transcribe verbatim" — nothing to ask
    'vestedinvested',                   # obvious steno duplication, already fixed
    'corrected to "debt" throughout',   # obvious steno artifact, engine already fixed
    'see above',                        # internal cross-reference, not actionable
    'see below — exhibit number',       # cross-ref to adjacent self-correction item
]

# AUDIO ONLY — needs the recording, never shows in Section B
_AUDIO_ONLY = [
    'audio', 'reconstruction', 'beyond steno', 'fragmented', 'reporter confirm',
    'steno gap', 'fragmentation', 'attributed', 'speaker attribution',
    'requires audio', 'verify audio', 'listen',
    'dollar amount', 'unit unclear', 'amount unclear', 'figure unclear',
    'figure missing', 'amount missing', 'number missing',
    'answer absent',           # missing testimony — needs audio to restore
    'speaker unclear',         # Q/A attribution — audio only
    'question fragmented',     # incomplete question — audio only
    'absent or truncated',     # answer cut off — audio only
    'response not captured',   # answer not in steno — audio only
    'structure unclear',       # sentence fragmentation — audio only
    'continues below',         # answer runs on — needs full audio context
    'answer continues',        # same
    'cannot resolve',          # engine explicitly cannot determine — audio required
]

# ACTIONABLE — MB can answer by reading the PDF
_ACTIONABLE = [
    'bates', 'exhibit', 'name', 'spelling',
    'date', 'address', 'zip', 'phone', 'email', 'title', 'firm', 'attorney',
    'missing word', 'word missing', 'word appears missing',
    'gap', 'jump', 'sequence',
    'alternate spelling', 'canonical spelling', 'steno artifact', 'verify spelling',
    'verify', 'confirm', 'self-correct', 'self correct',
]


def categorize_review(note):
    n = note.lower()
    if any(k in n for k in _GARBAGE):
        return 'garbage'
    if any(k in n for k in _AUDIO_ONLY):
        return 'audio'
    if any(k in n for k in _ACTIONABLE):
        return 'actionable'
    return 'audio'   # default: audio pass


def extract_key_term(note):
    """Pull the most useful searchable term from the review note.
    Looks for quoted names, exhibit numbers, Bates strings."""
    # Quoted terms: 'Bertelot', 'Brandl', etc.
    quoted = re.findall(r"'([^']{2,30})'", note)
    if quoted:
        return quoted[0]
    # Exhibit: "Exhibit No. 244"
    m = re.search(r'Exhibit No\.?\s*(\d+)', note, re.I)
    if m:
        return f'Exhibit No. {m.group(1)}'
    # Bates string in note: "Bates 285451" or "Bates YR-364101"
    # Skip the word "range" — match only tokens containing digits
    m = re.search(r'Bates\s+(?:range\s+)?([\w-]*\d[\w-]*)', note, re.I)
    if m:
        return m.group(1)
    return None


def plain_english_label(note):
    """Convert the engine note into a specific, plain-English question for MB."""
    n = note.lower()
    # Extract quoted terms — try single quotes first, fall back to double quotes
    quoted = re.findall(r"'([^']{2,30})'", note)
    if not quoted:
        quoted = re.findall(r'"([^"]{2,30})"', note)

    # Name spelling — two versions exist
    if 'alternate spelling' in n or 'canonical spelling' in n:
        term = quoted[0] if quoted else 'this name'
        # Find alternate form (may not be quoted)
        alt_m = re.search(
            r"spelling of (\w+)|appears as '([^']+)'|also spelled '([^']+)'",
            note, re.I)
        if alt_m:
            alt = alt_m.group(1) or alt_m.group(2) or alt_m.group(3)
            return (f"Name appears two ways: '{term}' here and '{alt}' elsewhere. "
                    f"Which spelling is correct?")
        return f"Name '{term}' — verify spelling is correct"

    # Year reference that looks like a steno artifact
    if 'year' in n and ('steno artifact' in n or 'steno artifacts' in n):
        return 'Year reference may be a steno artifact — verify the year is written correctly.'

    # Engine noted a likely correction (even without "steno artifact" label)
    # e.g. "apparent duplication; likely 'Caverns 6 and 7'"
    if quoted:
        likely_early = re.search(r"likely\s+['\"]([^'\"]{2,50})['\"]", note, re.I)
        if likely_early:
            orig = quoted[0]
            corr = likely_early.group(1)
            if orig.lower().strip() != corr.lower().strip():
                return f"Engine thinks '{orig}' should read '{corr}' — please confirm."

    # Steno artifact — name reconstructed from garbled steno
    if 'steno artifact' in n and quoted:
        term = quoted[0]
        trans_m = re.search(r"transcribed as '([^']+)'", note, re.I)
        if trans_m:
            return (f"Steno wrote '{term}' — transcribed as '{trans_m.group(1)}'. "
                    f"Verify spelling is correct.")
        # Steno may have captured a partial word or unit — no canonical form available
        # Accept both single and double quotes around the suggested form
        likely_m = re.search(
            r"possibly ['\"]([^'\"]+)['\"]|likely ['\"]([^'\"]+)['\"]|similar ['\"]([^'\"]+)['\"]",
            note, re.I)
        if likely_m:
            likely = likely_m.group(1) or likely_m.group(2) or likely_m.group(3)
            if likely.strip().lower() != term.strip().lower():
                return f"Steno wrote '{term}' here — possibly '{likely}'. What should it say?"
        return f"Steno wrote '{term}' here — verify this is the correct word or name."

    # Inverted Bates range
    if 'inverted' in n or ('lower than' in n and 'bates' in n):
        return ('Bates range end number is lower than the start number. '
                'Verify the correct range.')

    # Bates number incomplete or uncertain
    if 'bates' in n and ('dropped' in n or 'leading' in n or 'incomplete' in n):
        return 'Bates number may be missing digits — provide the complete number.'

    if 'bates' in n and ('confirm' in n or 'verify' in n):
        return 'Bates number — verify this is the correct reference.'

    # Exhibit number garbled
    if 'exhibit' in n and ('unclear' in n or 'garbled' in n or 'bates string' in n):
        return 'Exhibit number was garbled in the steno. What is the correct exhibit number?'

    # Attorney self-corrected exhibit on the record
    if 'exhibit' in n and ('self-correct' in n or 'initially referenced' in n
                            or 'operative' in n or 'struck' in n):
        return ('Attorney corrected the exhibit number on the record. '
                'Confirm the operative exhibit number is correct.')

    # Exhibit number sequence gap
    if 'exhibit' in n and ('gap' in n or 'sequence' in n or 'jump' in n):
        return 'Exhibit numbers skip — were all these exhibits marked in this depo?'

    # Missing word
    if 'missing word' in n or 'word missing' in n or 'word appears missing' in n:
        sug_m = re.search(
            r"possibly '([^']+)'|likely '([^']+)'|probably '([^']+)'",
            note, re.I)
        if sug_m:
            word = sug_m.group(1) or sug_m.group(2) or sug_m.group(3)
            return f"A word appears missing here — possibly '{word}'. What should it say?"
        return 'A word appears to be missing here. What should it say?'

    # Correction already applied — confirm
    if 'corrected to' in n:
        term = quoted[0] if quoted else ''
        return (f"Engine corrected this to '{term}'. Confirm this is right."
                if term else 'Engine made a correction here — confirm it is right.')

    # Year / date unclear
    if ('year' in n or 'date' in n) and ('unclear' in n or 'verify' in n or 'confirm' in n):
        return 'Year or date is unclear — verify against the original recording or exhibits.'

    # Speaker unclear
    if 'speaker' in n and ('unclear' in n or 'unknown' in n or 'attribution' in n):
        return 'Could not identify the speaker on this line. Is this a Q or an A?'

    # Witness self-corrected
    if 'self-correct' in n or 'self correct' in n:
        return 'Witness self-corrected here. Which word or name is the correct final answer?'

    # Exhibit index / description running together
    if 'exhibit' in n and 'appears to be' in n:
        if quoted:
            desc = quoted[-1]  # last quoted term is usually the description
            return (f"Exhibit number and description may be running together. "
                    f"Confirm this reads correctly.")
        return "Exhibit number and description may be running together — please verify."

    # Name verification — surname fragment or full name needed
    if 'full name' in n or 'surname fragment' in n:
        if quoted:
            return f"Name '{quoted[0]}' may be incomplete — provide the full name."
        return "Name appears incomplete or uncertain — provide the full name."

    # Name or term — direct address vs. reference to person
    if 'direct address' in n or ('name' in n and 'third party' in n):
        if quoted:
            return (f"'{quoted[0]}' appears here — is this addressing the witness directly "
                    f"or referring to a third party? Verify.")
        return "Possible direct address to witness or third party — verify which."

    # Name or term — verify spelling
    if 'verify' in n and 'spelling' in n:
        if quoted:
            return f"'{quoted[0]}' — verify spelling against exhibits or witness list."
        return "Verify spelling against exhibits or witness list."

    # Generic verify
    if 'verify' in n or 'confirm' in n:
        return 'Please verify this is correct.'

    return 'Engine flagged this line — please review and correct if needed.'


def is_usable_snippet(s):
    """True if s is long enough and meaningful to use as a search phrase."""
    s = s.strip()
    return (len(s) >= 15
            and not s.startswith('[REVIEW')
            and s not in ('Q.', 'A.', 'Q', 'A')
            and not re.match(r'^[QA]\.\s{0,2}$', s))


def extract_review_notes(line):
    """Extract all [REVIEW: ...] note texts from a line.

    Uses a depth counter instead of a regex so nested brackets like
    [REVIEW: "Bracketing '[REVIEW]' is fine"] don't truncate the note early.
    """
    notes = []
    i = 0
    while i < len(line):
        idx = line.find('[REVIEW:', i)
        if idx == -1:
            break
        j = idx + 8           # skip past '[REVIEW:'
        depth = 1             # we are inside one '[...'
        while j < len(line) and depth > 0:
            if line[j] == '[':
                depth += 1
            elif line[j] == ']':
                depth -= 1
            if depth > 0:
                j += 1
        notes.append(line[idx + 8:j].strip())
        i = j + 1
    return notes


# ── Main parse loop ───────────────────────────────────────────────────────────

review_actionable  = []
review_audio_count = 0

for i, raw_line in enumerate(_clines):
    if '[REVIEW' not in raw_line:
        continue
    tags = extract_review_notes(raw_line)
    for tag_note in tags:
        tag_note = tag_note.strip()
        cat = categorize_review(tag_note)

        if cat == 'garbage':
            continue   # silently discard — not MB's problem

        if cat == 'audio':
            review_audio_count += 1
            continue

        # ── ACTIONABLE ──────────────────────────────────────────────────────

        # Full line with ALL tags stripped — what MB will see as context
        full_line_clean = re.sub(r'\[REVIEW[^\]]*\]', '', raw_line)
        full_line_clean = re.sub(r'\[CORRECTED:[^\]]*\]', '', full_line_clean)
        full_line_clean = re.sub(r'\[AUDIO:[^\]]*\]', '', full_line_clean)
        full_line_clean = re.sub(r'\[([^\]]+)\]', r'\1', full_line_clean).strip()

        # If the flagged line is very short (e.g. just "A."), scan backward
        # for the preceding line to give MB context for what to look at.
        if len(full_line_clean) <= 5:
            for back_i in range(i - 1, max(0, i - 5), -1):
                prev_clean = re.sub(r'\[REVIEW[^\]]*\]', '', _clines[back_i])
                prev_clean = re.sub(r'\[CORRECTED:[^\]]*\]', '', prev_clean)
                prev_clean = re.sub(r'\[([^\]]+)\]', r'\1', prev_clean).strip()
                if len(prev_clean) >= 15:
                    full_line_clean = prev_clean
                    break

        # Determine best search snippet — priority order:
        #   1. Text before the [REVIEW] tag (actual transcript text, most reliable)
        #   2. Text after all REVIEW tags stripped (line body)
        #   3. Surrounding lines: prefer the line BEFORE (the Q that preceded the A)
        #   4. Key term extracted from the note (last resort — may not be in PDF)
        key_term = extract_key_term(tag_note)
        before   = raw_line.split('[REVIEW')[0].strip()
        before   = re.sub(r'\[([^\]]+)\]', r'\1', before).strip()

        if is_usable_snippet(before):
            snippet = before[-68:]
            # Don't start mid-word
            if len(snippet) < len(before) and snippet and not snippet[0].isspace():
                first_space = snippet.find(' ')
                if 0 < first_space < 20:
                    snippet = snippet[first_space + 1:].strip()
        else:
            # Before-tag text too short — try text after the [REVIEW] tag
            after_tag = re.sub(r'\[REVIEW[^\]]*\]', '', raw_line, count=1)
            after_tag = re.sub(r'\[([^\]]+)\]', r'\1', after_tag).strip()
            # Remove any remaining [REVIEW] tags (line may have multiple)
            after_tag = re.sub(r'\[REVIEW[^\]]*\]', '', after_tag).strip()

            if is_usable_snippet(after_tag):
                snippet = after_tag[:68]
            else:
                # Scan surrounding lines — prefer BEFORE (the preceding Q),
                # then after, then fall back to key term
                context_snip = ''
                for offset in [-1, -2, 1, 2]:
                    idx2 = i + offset
                    if 0 <= idx2 < len(_clines):
                        cand = re.sub(r'\[REVIEW[^\]]*\]', '', _clines[idx2])
                        cand = re.sub(r'\[([^\]]+)\]', r'\1', cand).strip()
                        if is_usable_snippet(cand):
                            context_snip = cand
                            break
                if context_snip:
                    snippet = context_snip[:68]
                elif key_term and len(key_term) >= 4:
                    snippet = key_term
                else:
                    snippet = before[:68]

        pg, ln = find_page_for_text(snippet)

        review_actionable.append({
            'note':      tag_note[:200],           # store enough for dedup/debug
            'label':     plain_english_label(tag_note),   # computed on full note
            'snippet':   snippet[:68],
            'context':   truncate_at_word(full_line_clean, 65),
            'page':      pg,
            'line':      ln,
        })


# ── Post-process: filter and deduplicate ──────────────────────────────────────

# Dollar-amount items that slipped through: need audio, not PDF
_AUDIO_AMOUNTS = [
    'dollar amount unclear', 'amount unclear', 'figure unclear',
    'unit unclear', 'figure missing', 'amount missing', 'number missing',
]
review_needs_audio = [it for it in review_actionable
                      if any(k in it['note'].lower() for k in _AUDIO_AMOUNTS)]
review_can_answer  = [it for it in review_actionable
                      if it not in review_needs_audio]
audio_total        = review_audio_count + len(review_needs_audio)

# Deduplicate by snippet
_seen = set()
_deduped = []
for _it in review_can_answer:
    _key = _it['snippet'].strip()[:50]
    if _key not in _seen:
        _seen.add(_key)
        _deduped.append(_it)
review_can_answer = _deduped


# ── Load QA_FLAGS — filler word count ────────────────────────────────────────

QA_PATH = os.path.join(BASE, 'FINAL_DELIVERY', 'QA_FLAGS.txt')
filler_count = 0
if os.path.exists(QA_PATH):
    with open(QA_PATH, encoding='utf-8') as f:
        qa_text = f.read()
    filler_count = qa_text.count('FILLER WORD')


# ── Spot-check pages ──────────────────────────────────────────────────────────

SPOT_CHECKS = [
    {
        'label': 'COVER PAGE',
        'page':  1,
        'check': (f'Witness: {WITNESS}. Date: {DEPO_DATE}. '
                  f'Location. Your name as reporter.'),
    },
    {
        'label': 'STIPULATION',
        'page':  10,
        'check': (f'Witness named as {WITNESS}. '
                  f'Attorney named to retain original.'),
    },
    {
        'label': 'FIRST TESTIMONY PAGE',
        'page':  11,
        'check': (f'Videographer statement correct. Witness intro block. '
                  f'Q. by {EXAMINING}.'),
    },
    {
        'label': "REPORTER'S CERTIFICATE",
        'page':  max(total_pages - 4, 1),
        'check': 'Your name, credentials, witness name, page count correct.',
    },
    {
        'label': 'WITNESS CERT + ERRATA',
        'page':  max(total_pages - 2, 1),
        'check': f'Witness name {WITNESS} and testimony date correct.',
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# BUILD THE DOCUMENT
# ═════════════════════════════════════════════════════════════════════════════

W   = 68
SEP = '-' * W
DBL = '=' * W
L   = []

def add(*lines):
    for line in lines:
        L.append(line)

def section(title):
    add('', DBL, title, DBL, '')


# ── HEADER ────────────────────────────────────────────────────────────────────

add(
    DBL,
    f'  TRANSCRIPT REVIEW  --  {WITNESS}',
    f'  {DEPO_DATE}   |   Docket {DOCKET}',
    f'  Prepared for: {REPORTER}',
    DBL,
    '',
    '  This file tells you exactly what to look at.',
    f'  You do NOT need to read all {total_pages} pages.',
    '  Open the PDF alongside this file and work through each section.',
    '',
    f'  Total transcript pages:  {total_pages}',
    f'  Items needing your eyes: {len(review_can_answer)} (Section B)',
    f'  Audio pass items:        {audio_total} (Section D -- your normal pass)',
    '',
    '  HOW TO USE THIS:',
    '  Step 1 -- Section 0: Confirm 4 data integrity checkpoints passed.',
    '  Step 2 -- Section A: Go to 5 specific pages in the PDF.',
    '            Confirm each one looks right. Note anything wrong.',
    '  Step 3 -- Section B: For each item, go to the page listed.',
    '            Write your answer in the ANSWER line.',
    '  Step 4 -- Section C: One filler-word question. Circle your choice.',
    '  Step 5 -- Section E: Sign off and reply to Scott.',
    '',
    '  Questions? Call or text Scott.',
    '',
)

# ── FORMAT QUESTION ───────────────────────────────────────────────────────────

add(
    SEP,
    '  QUICK FORMAT QUESTION (circle one):',
    '',
    '  Attorneys who appeared remotely are listed as:',
    '',
    '      THOMAS J. MADIGAN, ESQ.  (Via Zoom)',
    '',
    '  Should this be:',
    '      (A)  (Via Zoom)   <- current',
    '      (B)  (Zoom)       <- alternate',
    '',
    '  Your choice: _______',
    '  (Whichever you pick, we apply it to every depo going forward.)',
    SEP,
    '',
)

# ── SECTION 0 — DATA INTEGRITY ────────────────────────────────────────────────

section('SECTION 0 -- PIPELINE ACCEPTANCE TEST')

score, verdict = slice_verdict(slice_results)
n_total        = len(slice_results) if slice_results else 10

add(
    f'  Depo divided into {n_total} equal slices.',
    f'  Two independent phrases sampled per slice (A = second half, B = first half).',
    f'  No word shared between any two probes across all 20 samples.',
    f'  Slice PASSES if either probe is found. Slice FAILS only if both fail.',
    '',
    f'  SCORE:    {score}/{n_total}',
    f'  VERDICT:  {verdict}',
    '',
)

if not slice_results:
    add('  (Check could not run -- no .rtf file found in job folder.)', '')
else:
    add(f'  {"SL":<4}  {"POS":>4}  {"STATUS":<7}  {"PHRASE":<42}  LOCATION')
    add(f'  {"-"*4}  {"-"*4}  {"-"*7}  {"-"*42}  {"-"*14}')
    for r in slice_results:
        for p in r['probes']:
            sl_label = f'{r["slice"]}{p["label"]}'
            if p['status'] == 'PASS' and p.get('page'):
                loc = (f'p.{p["page"]} l.{p["line"]}' if p.get('line')
                       else f'p.{p["page"]}')
            elif p['status'] == 'PASS*':
                loc = 'steno correction'
            else:
                loc = 'NOT FOUND'
            phrase_disp = f'"{truncate_at_word(p["phrase"], 38)}"'
            add(f'  {sl_label:<4}  {r["pct"]:>3}%  {p["status"]:<7}  {phrase_disp:<42}  {loc}')
    add('')
    if score < n_total:
        failed = [r for r in slice_results if r['status'] == 'FAIL']
        add(f'  PASS*  = phrase words confirmed present; AI corrected the phrasing.')
        add(f'  FAIL   = BOTH probes for this slice not found in final output.')
        if failed:
            add('', '  Failed slices:', '')
            for r in failed:
                for p in r['probes']:
                    add(f'    Slice {r["slice"]}{p["label"]} (~{r["pct"]}% through depo):',
                        f'    RTF had: "{p["phrase"]}"',
                        f'    Not found in FINAL_FORMATTED.',
                        '')
    add('')

# ── SECTION A — SPOT CHECK ────────────────────────────────────────────────────

section('SECTION A -- 5 PAGES TO CHECK  (about 5 minutes)')
add(
    '  Open the PDF. Jump to each page number listed.',
    '  Read that page. If something looks wrong, write it in NOTES.',
    '  If it looks right, leave NOTES blank and move on.',
    '',
)

for sc in SPOT_CHECKS:
    add(
        f'  +-- GO TO PAGE {sc["page"]}  --  {sc["label"]}',
        f'  |',
        f'  |  What to check:  {sc["check"]}',
        f'  |',
        f'  |  NOTES: _________________________________________________',
        f'  +',
        '',
    )

# ── SECTION B — ITEMS NEEDING HER ANSWER ─────────────────────────────────────

section(f'SECTION B -- {len(review_can_answer)} ITEMS THAT NEED YOUR ANSWER  (about 10 minutes)')

if not review_can_answer:
    add('  Nothing flagged. Engine was confident throughout.', '')
else:
    add(
        '  For each item:',
        '    1. Go to the page number listed. Find the line number.',
        '    2. Read that line in the PDF.',
        '    3. Write your answer in the ANSWER line.',
        '       Write OK if it looks correct.',
        '       Write the correction if something is wrong.',
        '',
        '  (Items that require audio are in Section D.)',
        '',
    )
    for n, item in enumerate(review_can_answer, 1):
        # Page reference line
        if item['page'] and item['line']:
            pg_ref = f'Go to PDF page {item["page"]}, line {item["line"]}'
        elif item['page']:
            pg_ref = f'Go to PDF page {item["page"]}'
        else:
            # Fallback: show clean search phrase (never show mid-word garbage)
            search_phrase = item['snippet'].strip()
            pg_ref = f'Search PDF for: "{truncate_at_word(search_phrase, 50)}"'

        label = item['label']

        add(
            f'  -- ITEM B-{n:02d} ' + '-' * (W - 12),
            f'  {pg_ref}',
            f'',
            f'  What the transcript says:',
            f'    {item["context"]}',
            f'',
            f'  What to check:',
            f'    {label}',
            f'',
            f'  ANSWER: ________________________________________________',
            '',
        )

# ── SECTION C — FILLER WORDS ──────────────────────────────────────────────────

section('SECTION C -- FILLER WORDS  (one question)')
add(
    f'  The engine found {filler_count} places where the witness said "uhmm" or',
    f'  similar filler sounds.',
    '',
    '  A filler word is a sound made while thinking -- not actual testimony.',
    '  Examples:  "Uhmm, I believe so."  /  "Well, uh, I think..."',
    '',
    '  NOTE: "Uh-huh" (yes) and "Huh-uh" (no) are always kept.',
    '  Those are real answers. Only true fillers are in scope here.',
    '',
    '  What would you like us to do with filler words?  (circle one)',
    '',
    '    ( ) Remove all filler words     -- cleaner, most common choice',
    '    ( ) Keep all filler words        -- verbatim record',
    '    ( ) Remove "uhmm" only           -- keep other fillers',
    '    ( ) I will mark them myself      -- send me the full list',
    '',
    '  Your choice applies to this depo and all future depos.',
    '',
)

# ── SECTION D — AUDIO PASS ────────────────────────────────────────────────────

AUDIO_LOG_PATH = os.path.join(BASE, 'audio_apply_log.json')
audio_auto    = []
audio_suggest = []

if os.path.exists(AUDIO_LOG_PATH):
    with open(AUDIO_LOG_PATH, encoding='utf-8') as _af:
        _log = json.load(_af)
    audio_auto    = _log.get('applied', [])
    audio_suggest = _log.get('surfaced', [])

d_total = len(audio_auto) + len(audio_suggest)
section(f'SECTION D -- AUDIO VERIFICATION AGENT  ({d_total} items)')
add(
    '  Your audio verification agent listened to the full recording.',
    '  This section has two parts.',
    '',
)

# Part D1: changes we made
add(
    f'  +---------------------------------------------------------------------+',
    f'  |  PART 1 OF 2 -- WE MADE A CHANGE  ({len(audio_auto)} items)                |',
    f'  |                                                                     |',
    f'  |  The agent was confident enough to clean up these lines.            |',
    f'  |  The transcript reads clean -- no [REVIEW] tag remaining.           |',
    f'  |                                                                     |',
    f'  |  YOUR JOB:  Go to each page. Read the line. Listen if needed.      |',
    f'  |             Write OK -- or write the correction.                    |',
    f'  +---------------------------------------------------------------------+',
    '',
)

for n, item in enumerate(audio_auto, 1):
    after_clean = re.sub(r'\[REVIEW[^\]]*\]', '', item.get('after', '')).strip()
    whisper     = item.get('whisper_text', '').strip()
    pg, ln      = find_page_for_text(after_clean)
    if pg and ln:
        pg_ref = f'Go to PDF page {pg}, line {ln}'
    elif pg:
        pg_ref = f'Go to PDF page {pg}'
    else:
        pg_ref = f'Search PDF for: "{truncate_at_word(after_clean, 40)}"'
    add(
        f'  -- CONFIRM D1-{n:02d} ' + '-' * (W - 16),
        f'  {pg_ref}',
        f'',
        f'  Line now reads:',
        f'    {truncate_at_word(after_clean, 70)}',
        f'',
        (f'  Agent heard:  "{truncate_at_word(whisper, 60)}"' if whisper else ''),
        f'',
        f'  CONFIRM: ___  (write OK -- or your correction)',
        f'',
    )

# Part D2: suggestions
add(
    f'  +---------------------------------------------------------------------+',
    f'  |  PART 2 OF 2 -- YOUR CALL  ({len(audio_suggest)} items)                        |',
    f'  |                                                                     |',
    f'  |  The agent heard something but was not certain enough to change     |',
    f'  |  the line. It left a note in the transcript for you.                |',
    f'  |                                                                     |',
    f'  |  YOUR JOB:  Go to each page. Listen to the recording.              |',
    f'  |             Write exactly what was said.                            |',
    f'  +---------------------------------------------------------------------+',
    '',
)

for n, item in enumerate(audio_suggest, 1):
    before_clean = re.sub(r'\[REVIEW[^\]]*\]', '', item.get('before', '')).strip()
    whisper      = item.get('whisper_text', '').strip()
    pg, ln       = find_page_for_text(before_clean)
    if pg and ln:
        pg_ref = f'Go to PDF page {pg}, line {ln}'
    elif pg:
        pg_ref = f'Go to PDF page {pg}'
    else:
        pg_ref = f'Search PDF for: "{truncate_at_word(before_clean, 40)}"'
    add(
        f'  -- YOUR CALL D2-{n:02d} ' + '-' * (W - 18),
        f'  {pg_ref}',
        f'',
        f'  What the transcript says (with gap):',
        f'    {truncate_at_word(before_clean, 70)}',
        f'',
        (f'  Agent heard:  "{truncate_at_word(whisper, 60)}"'
         if whisper else '  Agent heard:  (no clear match in recording)'),
        f'',
        f'  YOUR ANSWER: ' + '_' * 46,
        f'',
    )

# ── SECTION E — SIGN-OFF ──────────────────────────────────────────────────────

section('SECTION E -- SIGN-OFF')
add(
    '  When you are done, fill in below and reply to Scott.',
    '',
    f'  Reviewed by:  {REPORTER}',
    f'  Date:         _________________________________',
    '',
    '  How does the transcript look overall?  (circle one)',
    '',
    '    ( ) GOOD -- deliver with my corrections noted above',
    '',
    '    ( ) NEEDS WORK -- call me before delivering',
    '',
    '  Anything else I should know:',
    '  __________________________________________________________________',
    '  __________________________________________________________________',
    '',
    DBL,
    f'  {CASE_SHORT}  |  {date.today().strftime("%B %d, %Y")}',
    f'  This document is a reporter review aid. Not a legal document.',
    DBL,
)


# ── Write output ──────────────────────────────────────────────────────────────

out_path = os.path.join(BASE, 'FINAL_DELIVERY', f'{CASE_SHORT}_CR_REVIEW.txt')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))

print(f'Written: {out_path}')
print(f'  Total pages:           {total_pages}')
print(f'  Integrity checkpoints: {len(integrity_results)} '
      f'({sum(1 for r in integrity_results if r["found"])} passed)')
print(f'  Section B items:       {len(review_can_answer)}')
print(f'  Audio-deferred:        {audio_total}')
print(f'  Filler words:          {filler_count}')
print(f'  Total lines in doc:    {len(L)}')

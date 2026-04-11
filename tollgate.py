"""
tollgate.py — Phase transition quality gates for mb_demo_engine_v4.

Called by run_pipeline.py after each step completes. Prints PASS/WARN/FAIL
inline as the pipeline runs. Hard FAILs stop the pipeline immediately.

Status levels:
  pass  — all hard checks passed, no warnings
  warn  — all hard checks passed, one or more soft warnings
  fail  — one or more hard checks failed — caller must stop pipeline

Usage (internal — called by run_pipeline.py):
    from tollgate import run_tollgate
    status = run_tollgate('extract')   # after extract step
    # returns 'pass', 'warn', or 'fail'
"""
import os
import re
import json
import glob as _glob

PASS = 'pass'
WARN = 'warn'
FAIL = 'fail'


# ── Result collector ──────────────────────────────────────────────────────────

class _Results:
    def __init__(self):
        self._items = []

    def ok(self, code, msg):
        self._items.append((PASS, code, msg))

    def warn(self, code, msg):
        self._items.append((WARN, code, msg))

    def fail(self, code, msg):
        self._items.append((FAIL, code, msg))

    def overall(self):
        if any(s == FAIL for s, _, _ in self._items):
            return FAIL
        if any(s == WARN for s, _, _ in self._items):
            return WARN
        return PASS

    def print_all(self, phase_label):
        print(f"[TOLLGATE] {phase_label}")
        for status, code, msg in self._items:
            tag = {'pass': 'PASS', 'warn': 'WARN', 'fail': 'FAIL'}[status]
            print(f"  [{tag}] {code:<8} {msg}")
        overall = self.overall()
        n_warn = sum(1 for s, _, _ in self._items if s == WARN)
        n_fail = sum(1 for s, _, _ in self._items if s == FAIL)
        if overall == FAIL:
            print(f"[TOLLGATE] FAIL — {n_fail} hard failure(s) above")
        elif overall == WARN:
            print(f"[TOLLGATE] PASS ({n_warn} warning(s))")
        else:
            print(f"[TOLLGATE] PASS")
        print()
        return overall


# ── Context helpers ───────────────────────────────────────────────────────────

def _caption():
    if os.path.exists('CASE_CAPTION.json'):
        with open('CASE_CAPTION.json', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _cr_config():
    if os.path.exists('cr_config.json'):
        with open('cr_config.json', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _read(path):
    """Read file text. Returns empty string if missing."""
    if not os.path.exists(path):
        return ''
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def _word_count(text):
    return len(text.split())


def _size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


# ── Phase 1: extracted_text.txt ───────────────────────────────────────────────

def _check_phase1():
    r = _Results()
    cap = _caption()
    text = _read('extracted_text.txt')
    sz = _size('extracted_text.txt')

    # T1-1 file size
    if sz >= 10_000:
        r.ok('T1-1', f'File exists, {sz:,} bytes')
    elif sz > 0:
        r.fail('T1-1', f'File only {sz:,} bytes — extractor may have failed')
    else:
        r.fail('T1-1', 'extracted_text.txt missing or empty')

    if not text:
        return r

    lines = text.splitlines()

    # T1-2 line count
    if len(lines) >= 100:
        r.ok('T1-2', f'Line count: {len(lines):,}')
    else:
        r.warn('T1-2', f'Only {len(lines)} lines — may be wrong file or partial extract')

    # T1-3 page numbers present
    page_lines = [l.strip() for l in lines if re.match(r'^\d{1,4}$', l.strip())]
    if len(page_lines) >= 3:
        r.ok('T1-3', f'Page numbers found: {len(page_lines)}')
    else:
        r.warn('T1-3', f'Only {len(page_lines)} bare-integer page lines — steno format may not be recognized')

    # T1-4 witness name present (hard stop — wrong depo)
    witness_last = cap.get('witness_last', '')
    if witness_last and witness_last.lower() in text.lower():
        r.ok('T1-4', f'Witness "{witness_last}" found in extracted text')
    elif witness_last:
        r.fail('T1-4', f'Witness "{witness_last}" not found — may be wrong depo loaded')
    else:
        r.warn('T1-4', 'No witness_last in CASE_CAPTION.json — skipping name check')

    # T1-5 no raw RTF codes
    if re.search(r'\\rtf1|\\pard\b|\\f\d+\b', text):
        r.fail('T1-5', 'Raw RTF codes found in extracted text — extractor failed mid-file')
    else:
        r.ok('T1-5', 'No raw RTF codes')

    # T1-6 exhibit index (warn only — some depos have none)
    if 'E X H I B I T S' in text or 'EXHIBITS' in text or 'Exhibit No.' in text:
        r.ok('T1-6', 'Exhibit index found')
    else:
        r.warn('T1-6', 'No exhibit index found — verify if this depo has no exhibits')

    return r


# ── Phase 2: cleaned_text.txt ─────────────────────────────────────────────────

def _check_phase2():
    r = _Results()
    cap = _caption()
    cr = _cr_config()

    text = _read('cleaned_text.txt')
    sz = _size('cleaned_text.txt')
    extracted_text = _read('extracted_text.txt')

    # T2-1 file size
    if sz >= 8_000:
        r.ok('T2-1', f'File exists, {sz:,} bytes')
    elif sz > 0:
        r.fail('T2-1', f'File only {sz:,} bytes — cleanup may have crashed')
    else:
        r.fail('T2-1', 'cleaned_text.txt missing or empty')

    if not text:
        return r

    # T2-2 word count vs extracted
    if extracted_text:
        wc_clean = _word_count(text)
        wc_raw = _word_count(extracted_text)
        pct = wc_clean / wc_raw if wc_raw > 0 else 0
        if pct >= 0.85:
            r.ok('T2-2', f'Word count: {wc_clean:,} ({pct:.0%} of extracted)')
        elif pct >= 0.75:
            r.warn('T2-2', f'Word count dropped to {pct:.0%} of extracted — cleanup may have removed real content')
        else:
            r.fail('T2-2', f'Word count only {pct:.0%} of extracted ({wc_clean:,} vs {wc_raw:,}) — cleanup ate content')
    else:
        r.warn('T2-2', 'extracted_text.txt not found — skipping word count comparison')

    # T2-3 no raw steno strokes surviving
    steno_lines = [l for l in text.splitlines() if re.search(r'\b-[A-Z]{3,}\b', l)]
    if not steno_lines:
        r.ok('T2-3', 'No raw steno strokes found')
    else:
        r.warn('T2-3', f'{len(steno_lines)} line(s) with possible steno strokes — e.g.: "{steno_lines[0][:60]}"')

    # T2-4 Q/A labels present (hard stop — AI pass will misread structure)
    qa_lines = [l for l in text.splitlines() if re.match(r'^[QA]\.\s+', l)]
    if len(qa_lines) >= 10:
        r.ok('T2-4', f'Q/A labels found: {len(qa_lines)} labeled lines')
    elif len(qa_lines) > 0:
        r.warn('T2-4', f'Only {len(qa_lines)} Q/A labeled lines — verify depo has examination')
    else:
        r.fail('T2-4', 'No Q/A labels found — cleanup may have stripped them or depo has no examination')

    # T2-5 witness name survived cleanup
    witness_last = cap.get('witness_last', '')
    if witness_last and witness_last.lower() in text.lower():
        r.ok('T2-5', f'Witness "{witness_last}" still present after cleanup')
    elif witness_last:
        r.fail('T2-5', f'Witness "{witness_last}" missing after cleanup — over-cleanup wiped proper noun')

    # T2-6 exhibit index survived
    if 'Exhibit No.' in extracted_text and 'Exhibit No.' not in text:
        r.warn('T2-6', 'Exhibit index was in extracted_text but missing from cleaned_text')
    elif 'Exhibit No.' in text:
        r.ok('T2-6', 'Exhibit index present in cleaned text')

    # T2-7 page numbers survived
    page_lines = [l.strip() for l in text.splitlines() if re.match(r'^\d{1,4}$', l.strip())]
    if len(page_lines) >= 3:
        r.ok('T2-7', f'Page numbers survived cleanup: {len(page_lines)} found')
    else:
        r.warn('T2-7', f'Only {len(page_lines)} page numbers — format pipeline may miscount pages')

    # T2-8 dictionary configured
    dict_file = cr.get('modules', {}).get('dictionary')
    if dict_file:
        r.ok('T2-8', f'Dictionary configured: {dict_file}')
    else:
        r.warn('T2-8', 'No dictionary in cr_config.json — proper noun hints will be limited')

    return r


# ── Phase 3: corrected_text.txt + correction_log.json ────────────────────────

def _check_phase3():
    r = _Results()
    cap = _caption()

    text = _read('corrected_text.txt')
    cleaned = _read('cleaned_text.txt')
    sz = _size('corrected_text.txt')
    cleaned_sz = _size('cleaned_text.txt')

    # T3-1 size vs cleaned (hard stop — truncated run)
    if cleaned_sz > 0:
        pct = sz / cleaned_sz
        if pct >= 0.90:
            r.ok('T3-1', f'File size: {sz:,} bytes ({pct:.0%} of cleaned)')
        else:
            r.fail('T3-1', f'Only {pct:.0%} of cleaned size ({sz:,} vs {cleaned_sz:,}) — may be a truncated run')
    elif sz >= 10_000:
        r.ok('T3-1', f'File exists, {sz:,} bytes')
    else:
        r.fail('T3-1', f'corrected_text.txt missing or too small ({sz:,} bytes)')

    if not text:
        return r

    # T3-2 no checkpoint file (checkpoint deleted on clean completion)
    if os.path.exists('.ai_checkpoint.json'):
        r.fail('T3-2', 'Checkpoint file still exists — AI run may not have completed. Resume or delete checkpoint and re-run.')
    else:
        r.ok('T3-2', 'No checkpoint file — AI run completed normally')

    lines = text.splitlines()

    # T3-3 unlabeled testimony check (warn — fuzzy detection)
    in_exam = False
    unlabeled = []
    skip_pat = re.compile(
        r'^([QA]\.|MR\.|MS\.|THE |BY |EXAMINATION|STIPULATION|'
        r'A P P E A R|E X H I B|S T I P|I,\s|Certified|Reported|'
        r'Video|FOR THE|ALSO|Also|\*|\d{1,4}$|\s*$)',
        re.IGNORECASE
    )
    for line in lines:
        stripped = line.strip()
        if re.match(r'^EXAMINATION\s*$', stripped):
            in_exam = True
        if in_exam and len(stripped) > 20 and not skip_pat.match(stripped):
            unlabeled.append(stripped)
    if not unlabeled:
        r.ok('T3-3', 'No apparent unlabeled testimony lines')
    elif len(unlabeled) <= 3:
        r.warn('T3-3', f'{len(unlabeled)} possible unlabeled line(s) — verify: "{unlabeled[0][:60]}"')
    else:
        r.warn('T3-3', f'{len(unlabeled)} possible unlabeled testimony lines — first: "{unlabeled[0][:60]}"')

    # T3-4 structural headers clean
    structural = ['E X H I B I T S', 'A P P E A R A N C E S', 'S T I P U L A T I O N']
    header_issues = []
    for header in structural:
        for line in lines:
            if header in line and ('[REVIEW' in line or '[AUDIO' in line):
                header_issues.append(header)
    if not header_issues:
        r.ok('T3-4', 'Structural headers have no REVIEW/AUDIO tags')
    else:
        r.warn('T3-4', f'Structural header(s) incorrectly tagged: {header_issues}')

    # T3-5 trailing space before punctuation
    bad_punct = [l for l in lines if re.search(r'\s[?!,;]', l)]
    if not bad_punct:
        r.ok('T3-5', 'No trailing-space punctuation found')
    else:
        r.warn('T3-5', f'{len(bad_punct)} line(s) with space before punctuation — e.g.: "{bad_punct[0].strip()[:60]}"')

    # T3-6 AUDIO tags well-formed (hard stop — breaks CAT RTF builder)
    audio_opens = len(re.findall(r'\[AUDIO:', text))
    audio_closed = len(re.findall(r'\[AUDIO:[^\]]*\]', text))
    if audio_opens == 0:
        r.ok('T3-6', 'No AUDIO tags')
    elif audio_opens == audio_closed:
        r.ok('T3-6', f'{audio_opens} AUDIO tag(s) — all well-formed')
    else:
        r.fail('T3-6', f'{audio_opens} AUDIO open(s) but only {audio_closed} closed — malformed tag(s)')

    # T3-7 REVIEW tags well-formed (hard stop)
    review_opens = len(re.findall(r'\[REVIEW:', text))
    review_closed = len(re.findall(r'\[REVIEW:[^\]]*\]', text))
    if review_opens == 0:
        r.ok('T3-7', 'No REVIEW tags')
    elif review_opens == review_closed:
        r.ok('T3-7', f'{review_opens} REVIEW tag(s) — all well-formed')
    else:
        r.fail('T3-7', f'{review_opens} REVIEW open(s) but only {review_closed} closed — malformed tag(s)')

    # T3-8 word count vs cleaned
    if cleaned:
        wc_corr = _word_count(text)
        wc_clean = _word_count(cleaned)
        pct = wc_corr / wc_clean if wc_clean > 0 else 0
        if pct >= 0.92:
            r.ok('T3-8', f'Word count: {wc_corr:,} ({pct:.0%} of cleaned)')
        else:
            r.warn('T3-8', f'Word count {pct:.0%} of cleaned — AI may have dropped content')

    # T3-9 witness name present
    witness_last = cap.get('witness_last', '')
    if witness_last and witness_last.lower() in text.lower():
        r.ok('T3-9', f'Witness "{witness_last}" present in corrected text')
    elif witness_last:
        r.warn('T3-9', f'Witness "{witness_last}" not found — AI may have altered the name')

    # T3-10 cost check
    if os.path.exists('correction_log.json'):
        try:
            with open('correction_log.json', encoding='utf-8') as f:
                log = json.load(f)
            cost = log.get('total_cost', log.get('cost'))
            if cost is not None:
                if float(cost) <= 6.0:
                    r.ok('T3-10', f'AI pass cost: ${float(cost):.4f}')
                else:
                    r.warn('T3-10', f'AI pass cost ${float(cost):.4f} exceeds $6.00 budget — review chunk count')
            else:
                r.warn('T3-10', 'correction_log.json has no cost field')
        except Exception:
            r.warn('T3-10', 'correction_log.json could not be parsed — skipping cost check')
    else:
        r.warn('T3-10', 'correction_log.json not found — skipping cost check')

    return r


# ── Phase 4: verify_agent + apply_verify → corrected_text.txt updated ────────

def _check_phase4():
    r = _Results()

    text = _read('corrected_text.txt')
    sz_after = _size('corrected_text.txt')

    # T4-1 verify_log.json exists
    vlog_sz = _size('verify_log.json')
    if vlog_sz >= 100:
        r.ok('T4-1', f'verify_log.json exists, {vlog_sz:,} bytes')
    elif vlog_sz > 0:
        r.warn('T4-1', f'verify_log.json only {vlog_sz} bytes — Haiku pass may have produced no results')
    else:
        r.warn('T4-1', 'verify_log.json not found — verify pass may have been skipped')

    # T4-2 / T4-3 DISAGREE rate
    if os.path.exists('verify_log.json'):
        try:
            with open('verify_log.json', encoding='utf-8') as f:
                vlog = json.load(f)
            decisions = []
            if isinstance(vlog, list):
                decisions = [e.get('decision', '') for e in vlog if isinstance(e, dict)]
            elif isinstance(vlog, dict):
                entries = vlog.get('entries', vlog.get('reviews', vlog.get('corrections', [])))
                decisions = [e.get('decision', '') for e in entries if isinstance(e, dict)]

            n_agree    = sum(1 for d in decisions if 'AGREE' in str(d).upper() and 'DIS' not in str(d).upper())
            n_disagree = sum(1 for d in decisions if 'DISAGREE' in str(d).upper())
            total = n_agree + n_disagree

            if total == 0:
                r.warn('T4-2', 'No AGREE/DISAGREE decisions in verify_log — Haiku may not have run')
            else:
                pct = n_disagree / total
                r.ok('T4-2', f'Verify coverage: {total} decisions logged')
                if 0.01 <= pct <= 0.30:
                    r.ok('T4-3', f'DISAGREE rate: {pct:.0%} ({n_disagree}/{total}) — normal range')
                elif pct == 0:
                    r.warn('T4-3', f'DISAGREE rate: 0% — Haiku agreed with everything (confirm it ran)')
                else:
                    r.warn('T4-3', f'DISAGREE rate: {pct:.0%} ({n_disagree}/{total}) — high, Phase 3 may have overcorrected')
        except Exception as e:
            r.warn('T4-2', f'Could not parse verify_log.json: {e}')

    # T4-4 corrected_text.txt not shrunk (hard stop)
    if sz_after >= 10_000:
        r.ok('T4-4', f'corrected_text.txt still {sz_after:,} bytes after apply_verify')
    else:
        r.fail('T4-4', f'corrected_text.txt only {sz_after:,} bytes — apply_verify may have truncated it')

    if not text:
        return r

    # T4-5 no unclosed REVIEW tags (hard stop)
    opens  = len(re.findall(r'\[REVIEW:', text))
    closed = len(re.findall(r'\[REVIEW:[^\]]*\]', text))
    if opens == 0:
        r.ok('T4-5', 'No REVIEW tags')
    elif opens == closed:
        r.ok('T4-5', f'{opens} REVIEW tag(s) — all well-formed')
    else:
        r.fail('T4-5', f'{opens} REVIEW open(s), only {closed} closed — apply_verify wrote malformed tag')

    # T4-6 no duplicate REVIEW tags on same line
    dup_lines = [l for l in text.splitlines() if l.count('[REVIEW:') > 1]
    if not dup_lines:
        r.ok('T4-6', 'No duplicate REVIEW tags on any line')
    else:
        r.warn('T4-6', f'{len(dup_lines)} line(s) with duplicate REVIEW tags')

    return r


# ── Phase 5: specialist_verify_log.json ──────────────────────────────────────

def _check_phase5():
    r = _Results()

    text = _read('corrected_text.txt')
    sz = _size('specialist_verify_log.json')

    # T5-1 file exists (warn only — specialist is advisory)
    if sz >= 500:
        r.ok('T5-1', f'specialist_verify_log.json exists, {sz:,} bytes')
    elif sz > 0:
        r.warn('T5-1', f'specialist_verify_log.json only {sz} bytes — agents may have returned nothing')
    else:
        r.warn('T5-1', 'specialist_verify_log.json not found — specialist pass may have been skipped')

    if not os.path.exists('specialist_verify_log.json'):
        return r

    try:
        with open('specialist_verify_log.json', encoding='utf-8') as f:
            slog = json.load(f)

        # T5-2 section count (hard stop if < 3)
        if isinstance(slog, dict):
            n_sections = len(slog)
            if n_sections >= 5:
                r.ok('T5-2', f'{n_sections} agent sections present in log')
            elif n_sections >= 3:
                r.warn('T5-2', f'Only {n_sections} agent sections — some specialists may have crashed')
            else:
                r.fail('T5-2', f'Only {n_sections} agent sections — most specialists appear to have failed')

            # T5-3 empty section check
            empty = [k for k, v in slog.items() if isinstance(v, list) and len(v) == 0]
            if not empty:
                r.ok('T5-3', 'All agent sections have content')
            else:
                r.warn('T5-3', f'Empty sections (no findings): {empty}')
        else:
            r.warn('T5-2', 'specialist_verify_log.json is not a dict — unexpected format')

    except Exception as e:
        r.warn('T5-1', f'Could not parse specialist_verify_log.json: {e}')
        return r

    # T5-4 no unclosed tags in corrected_text.txt (hard stop)
    if text:
        opens_r  = len(re.findall(r'\[REVIEW:', text))
        closed_r = len(re.findall(r'\[REVIEW:[^\]]*\]', text))
        opens_a  = len(re.findall(r'\[AUDIO:', text))
        closed_a = len(re.findall(r'\[AUDIO:[^\]]*\]', text))
        if opens_r == closed_r and opens_a == closed_a:
            r.ok('T5-4', 'All REVIEW and AUDIO tags well-formed after specialist pass')
        else:
            r.fail('T5-4', f'Tag mismatch after specialist: REVIEW {opens_r}/{closed_r}, AUDIO {opens_a}/{closed_a}')

    return r


# ── Phase 6: depo_config.json ─────────────────────────────────────────────────

def _check_phase6():
    r = _Results()
    cap = _caption()
    text = _read('corrected_text.txt')

    # T6-1 valid JSON (hard stop)
    if not os.path.exists('depo_config.json'):
        r.fail('T6-1', 'depo_config.json not found — extract_config.py may have failed')
        return r
    try:
        with open('depo_config.json', encoding='utf-8') as f:
            cfg = json.load(f)
        r.ok('T6-1', 'depo_config.json is valid JSON')
    except Exception as e:
        r.fail('T6-1', f'depo_config.json parse error: {e}')
        return r

    # T6-2 no UNKNOWN in critical fields (hard stop)
    critical = ['witness_name', 'examining_atty', 'page_count', 'exhibit_count']
    unknowns = [k for k in critical if str(cfg.get(k, '')).upper() in ('UNKNOWN', '', 'NONE', 'NULL')]
    if not unknowns:
        r.ok('T6-2', 'All critical fields populated')
    else:
        r.fail('T6-2', f'Critical field(s) are UNKNOWN/empty: {unknowns}')

    # T6-3 witness name vs CASE_CAPTION (hard stop — wrong name on every page)
    cap_witness = cap.get('witness_full_name') or cap.get('witness_name', '')
    cfg_witness = cfg.get('witness_name', '')
    if cap_witness and cfg_witness:
        if cap_witness.lower() in cfg_witness.lower() or cfg_witness.lower() in cap_witness.lower():
            r.ok('T6-3', f'Witness name consistent: "{cfg_witness}"')
        else:
            r.fail('T6-3', f'Witness name mismatch — caption: "{cap_witness}", config: "{cfg_witness}"')
    else:
        r.warn('T6-3', 'Cannot compare witness names — one or both fields empty')

    # T6-4 exhibit count plausible
    try:
        ec = int(cfg.get('exhibit_count', 0))
        if 1 <= ec <= 99:
            r.ok('T6-4', f'Exhibit count: {ec}')
        elif ec == 0:
            r.warn('T6-4', 'Exhibit count is 0 — verify depo has no exhibits')
        else:
            r.warn('T6-4', f'Exhibit count {ec} is unusually high — verify index not double-counted')
    except (TypeError, ValueError):
        r.warn('T6-4', f'Exhibit count "{cfg.get("exhibit_count")}" is not a number')

    # T6-5 page count vs text
    if text:
        page_nums = [int(l.strip()) for l in text.splitlines() if re.match(r'^\d{1,4}$', l.strip())]
        if page_nums:
            max_page = max(page_nums)
            try:
                pc = int(cfg.get('page_count', 0))
                if abs(pc - max_page) <= 2:
                    r.ok('T6-5', f'Page count: {pc} (last page in text: {max_page})')
                else:
                    r.warn('T6-5', f'Page count {pc} vs last page number {max_page} — off by {abs(pc - max_page)}')
            except (TypeError, ValueError):
                r.warn('T6-5', f'Page count "{cfg.get("page_count")}" is not a number')

    # T6-6 attorney names clean (hard stop — steno artifact on every Q line)
    atty = str(cfg.get('examining_atty', ''))
    if atty and re.search(r'-[A-Z]{2,}', atty):
        r.fail('T6-6', f'examining_atty has steno artifact: "{atty}"')
    elif atty:
        r.ok('T6-6', f'examining_atty looks clean: "{atty}"')
    else:
        r.warn('T6-6', 'examining_atty is empty')

    # T6-7 reporter name
    cap_reporter = cap.get('reporter_name_display') or cap.get('reporter_name', '')
    cfg_reporter = str(cfg.get('reporter_name', ''))

    def _name_core(n):
        return re.sub(r'\b(CCR|RPR|CRR|RMR|CSR)\b', '', n, flags=re.I).strip().lower()

    if cap_reporter and cfg_reporter:
        if _name_core(cap_reporter) in _name_core(cfg_reporter) or _name_core(cfg_reporter) in _name_core(cap_reporter):
            r.ok('T6-7', f'Reporter name consistent: "{cfg_reporter}"')
        else:
            r.warn('T6-7', f'Reporter name mismatch — caption: "{cap_reporter}", config: "{cfg_reporter}"')
    else:
        r.warn('T6-7', 'Cannot compare reporter names — one or both empty')

    # T6-8 docket consistency
    cap_docket = cap.get('docket', '')
    cfg_docket = str(cfg.get('docket', ''))
    if cap_docket and cfg_docket and cap_docket != cfg_docket:
        r.warn('T6-8', f'Docket mismatch — caption: "{cap_docket}", config: "{cfg_docket}"')
    else:
        r.ok('T6-8', 'Docket/division consistent')

    return r


# ── Phase 7: FINAL_FORMATTED.txt ─────────────────────────────────────────────

def _check_phase7():
    r = _Results()
    cap = _caption()

    candidates = (_glob.glob('FINAL_DELIVERY/*_FINAL_FORMATTED.txt') +
                  _glob.glob('FINAL_DELIVERY/*_FORMATTED.txt'))
    if not candidates:
        r.fail('T7-1', 'No FINAL_FORMATTED.txt found in FINAL_DELIVERY/')
        return r

    fmt_path = candidates[0]
    sz = os.path.getsize(fmt_path)
    text = _read(fmt_path)

    # T7-1 file size
    if sz >= 50_000:
        r.ok('T7-1', f'{os.path.basename(fmt_path)}: {sz:,} bytes')
    elif sz >= 10_000:
        r.warn('T7-1', f'Only {sz:,} bytes — may be a short depo or partial format run')
    else:
        r.fail('T7-1', f'Only {sz:,} bytes — formatter likely crashed early')

    if not text:
        return r

    lines = text.splitlines()

    # T7-2 EXAMINATION appears exactly once (hard stop — D-19)
    exam_count = sum(1 for l in lines if re.match(r'^\s*EXAMINATION\s*$', l))
    if exam_count == 1:
        r.ok('T7-2', 'EXAMINATION header appears exactly once')
    elif exam_count == 0:
        r.warn('T7-2', 'EXAMINATION header not found in formatted output')
    else:
        r.fail('T7-2', f'EXAMINATION header appears {exam_count} times — D-19 double-header regression')

    # T7-3 line-numbered lines present
    numbered = [l for l in lines if re.match(r'^\s{0,3}\d{1,2}\s+\S', l)]
    if len(numbered) >= 25:
        r.ok('T7-3', f'Line-numbered lines: {len(numbered)}')
    else:
        r.warn('T7-3', f'Only {len(numbered)} numbered lines — line numbering may be broken')

    # T7-4 no REVIEW/AUDIO tags in final output (hard stop — delivery failure)
    if '[REVIEW:' in text or '[AUDIO:' in text:
        r.fail('T7-4', 'REVIEW or AUDIO tags found in FINAL_FORMATTED.txt — must not appear in final output')
    else:
        r.ok('T7-4', 'No REVIEW/AUDIO tags in formatted output')

    # T7-5 exhibit count vs depo_config
    if os.path.exists('depo_config.json'):
        try:
            with open('depo_config.json', encoding='utf-8') as f:
                cfg = json.load(f)
            expected = int(cfg.get('exhibit_count', 0))
            found = len(re.findall(r'Exhibit No\.', text))
            if expected > 0 and abs(found - expected) <= 1:
                r.ok('T7-5', f'Exhibit entries: {found} (expected {expected})')
            elif expected > 0:
                r.warn('T7-5', f'Exhibit count mismatch: found {found}, expected {expected}')
        except Exception:
            r.warn('T7-5', 'Could not check exhibit count — depo_config.json parse error')

    # T7-6 cert page present (hard stop)
    has_cert = 'CCR' in text or 'RPR' in text or 'Certified Court Reporter' in text
    if has_cert:
        r.ok('T7-6', 'Cert page indicators found')
    else:
        r.fail('T7-6', 'No cert page indicators (CCR/RPR/Certified Court Reporter) — cert page missing')

    # T7-7 reporter name on cert
    cap_reporter = cap.get('reporter_name_display') or cap.get('reporter_name', '')
    if cap_reporter:
        parts = cap_reporter.split()
        reporter_last = parts[-1].rstrip(',.') if parts else ''
        if reporter_last and reporter_last.lower() in text.lower():
            r.ok('T7-7', f'Reporter "{reporter_last}" found in formatted output')
        elif reporter_last:
            r.warn('T7-7', f'Reporter "{reporter_last}" not found — cert page may have wrong name')

    # T7-9 colloquy not labeled as Q/A
    colloquy_as_qa = [l for l in lines if re.match(r'^[QA]\.\s+(MR\.|MS\.)', l)]
    if not colloquy_as_qa:
        r.ok('T7-9', 'No colloquy lines incorrectly labeled as Q/A')
    else:
        r.warn('T7-9', f'{len(colloquy_as_qa)} colloquy line(s) labeled as Q/A')

    # T7-10 Bates numbers use hyphen not underscore
    if re.search(r'\b[A-Z]{2,}_\d{5,}\b', text):
        r.warn('T7-10', 'Possible underscore Bates number in formatted output — should be hyphen (D-10)')
    else:
        r.ok('T7-10', 'No underscore Bates patterns found')

    return r


# ── Phase 8: FINAL_DELIVERY/ complete ────────────────────────────────────────

def _check_phase8():
    r = _Results()
    cap = _caption()

    delivery = 'FINAL_DELIVERY'

    expected_patterns = [
        ('*_FINAL_FORMATTED.txt', 'Formatted transcript'),
        ('*_FINAL.pdf',           'PDF'),
        ('*_FINAL_TRANSCRIPT.txt','Plain transcript'),
        ('*_CONDENSED.txt',       'Condensed'),
        ('*_CR_REVIEW.txt',       'CR Review package'),
    ]

    # T8-1 / T8-2: all expected files present and non-trivial
    all_present = True
    for pattern, label in expected_patterns:
        matches = _glob.glob(os.path.join(delivery, pattern))
        if not matches:
            r.fail('T8-1', f'Missing: {label} ({pattern})')
            all_present = False
        else:
            fsize = os.path.getsize(matches[0])
            fname = os.path.basename(matches[0])
            if fsize >= 1_000:
                r.ok('T8-2', f'{fname}: {fsize:,} bytes')
            else:
                r.fail('T8-2', f'{fname}: only {fsize} bytes — build script may have crashed after creating file')

    # T8-4 PDF opens without error
    pdf_files = _glob.glob(os.path.join(delivery, '*.pdf'))
    if pdf_files:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_files[0]) as pdf:
                n_pages = len(pdf.pages)
                page1_text = pdf.pages[0].extract_text() or ''
            if page1_text:
                r.ok('T8-4', f'PDF opens cleanly: {n_pages} pages, page 1 has text')
            else:
                r.warn('T8-4', f'PDF opens but page 1 has no extractable text')

            # T8-3 PDF page count vs formatted
            fmt_files = _glob.glob(os.path.join(delivery, '*_FINAL_FORMATTED.txt'))
            if fmt_files:
                fmt_text = _read(fmt_files[0])
                fmt_pages = len([l for l in fmt_text.splitlines()
                                 if re.match(r'^\s*\d{1,4}\s*$', l)])
                if abs(n_pages - fmt_pages) <= 2:
                    r.ok('T8-3', f'PDF pages ({n_pages}) matches formatted page count ({fmt_pages})')
                else:
                    r.warn('T8-3', f'PDF pages ({n_pages}) vs formatted pages ({fmt_pages}) — off by {abs(n_pages - fmt_pages)}')
        except ImportError:
            r.warn('T8-4', 'pdfplumber not installed — skipping PDF content check')
        except Exception as e:
            r.fail('T8-4', f'PDF failed to open: {e}')

    # T8-5 / T8-6: CR_REVIEW has REVIEW and AUDIO sections
    cr_review_files = _glob.glob(os.path.join(delivery, '*_CR_REVIEW.txt'))
    corrected = _read('corrected_text.txt')
    if cr_review_files and corrected:
        cr_text = _read(cr_review_files[0])
        has_review_src = '[REVIEW:' in corrected
        has_audio_src  = '[AUDIO:'  in corrected

        if has_review_src:
            if 'REVIEW' in cr_text:
                r.ok('T8-5', 'CR_REVIEW contains REVIEW items')
            else:
                r.warn('T8-5', 'Source has [REVIEW] tags but CR_REVIEW has no REVIEW section')
        else:
            r.ok('T8-5', 'No REVIEW tags in source — CR_REVIEW section not expected')

        if has_audio_src:
            if 'AUDIO' in cr_text:
                r.ok('T8-6', 'CR_REVIEW contains AUDIO items')
            else:
                r.warn('T8-6', 'Source has [AUDIO] tags but CR_REVIEW has no AUDIO section')
        else:
            r.ok('T8-6', 'No AUDIO tags in source — CR_REVIEW section not expected')

    # T8-7 no tags in plain transcript (hard stop)
    transcript_files = _glob.glob(os.path.join(delivery, '*_FINAL_TRANSCRIPT.txt'))
    if transcript_files:
        trans_text = _read(transcript_files[0])
        if '[REVIEW:' in trans_text or '[AUDIO:' in trans_text:
            r.fail('T8-7', 'REVIEW or AUDIO tags in FINAL_TRANSCRIPT.txt — must not appear in plain text delivery')
        else:
            r.ok('T8-7', 'No REVIEW/AUDIO tags in plain transcript')

    # T8-8 exhibit list count
    if os.path.exists('depo_config.json') and all_present:
        try:
            with open('depo_config.json', encoding='utf-8') as f:
                cfg = json.load(f)
            expected = int(cfg.get('exhibit_count', 0))
            # Check deliverables exhibit list if present
            exhibit_files = _glob.glob(os.path.join(delivery, '*EXHIBIT*'))
            if exhibit_files and expected > 0:
                ex_text = _read(exhibit_files[0])
                found = len(re.findall(r'Exhibit No\.', ex_text))
                if abs(found - expected) <= 1:
                    r.ok('T8-8', f'Exhibit list: {found} entries (expected {expected})')
                else:
                    r.warn('T8-8', f'Exhibit list count mismatch: found {found}, expected {expected}')
        except Exception:
            pass

    # T-FINAL no [FLAG:] tech debt markers in any delivery file
    flag_hits = []
    for fname in _glob.glob(os.path.join(delivery, '*')):
        if os.path.isfile(fname):
            content = _read(fname)
            if '[FLAG:' in content:
                flag_hits.append(os.path.basename(fname))
    if not flag_hits:
        r.ok('T-FINAL', 'No [FLAG:] tech debt markers in any delivery file')
    else:
        r.fail('T-FINAL', f'[FLAG:] markers found in: {flag_hits} — remove before delivery')

    return r


# ── Dispatch table ────────────────────────────────────────────────────────────

_PHASE_MAP = {
    'extract':      (_check_phase1, 'Phase 1 — extracted_text.txt'),
    'steno':        (_check_phase2, 'Phase 2 — cleaned_text.txt'),
    'ai':           (_check_phase3, 'Phase 3 — corrected_text.txt'),
    'verify':       (None,          None),   # checked as part of phase 4 (after apply_verify)
    'apply_verify': (_check_phase4, 'Phase 4 — verify + apply_verify'),
    'specialist':   (_check_phase5, 'Phase 5 — specialist_verify_log.json'),
    'config':       (_check_phase6, 'Phase 6 — depo_config.json'),
    'format':       (_check_phase7, 'Phase 7 — FINAL_FORMATTED.txt'),
    'cr_review':    (_check_phase8, 'Phase 8 — FINAL_DELIVERY/'),
}


def run_tollgate(step_key):
    """
    Run the tollgate for the given pipeline step key.

    Prints PASS/WARN/FAIL for each check, then overall result.
    Returns 'pass', 'warn', or 'fail'.

    Called by run_pipeline.py after each step completes successfully.
    Caller is responsible for stopping the pipeline on 'fail'.
    """
    if step_key not in _PHASE_MAP:
        return PASS  # no tollgate defined for this step — pass through

    fn, label = _PHASE_MAP[step_key]
    if fn is None:
        return PASS  # step is checked as part of a combined gate

    results = fn()
    return results.print_all(label)

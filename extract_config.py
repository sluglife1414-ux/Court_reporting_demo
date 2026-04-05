"""
extract_config.py — Auto-extract depo_config.json from corrected_text.txt or cleaned_text.txt.

Reads the transcript and pulls all case metadata automatically.
No MB involvement needed. No form to fill out.

Writes: depo_config.json (read by format_final.py and all pipeline scripts)

Usage:
    python extract_config.py              # auto-detects best input file
    python extract_config.py --review     # prints extracted values, asks to confirm
    python extract_config.py --force      # writes without confirmation
"""

import re
import json
import os
import sys
import argparse
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

# Input priority: corrected > cleaned > extracted
for candidate in ['corrected_text.txt', 'cleaned_text.txt', 'extracted_text.txt']:
    if os.path.exists(candidate):
        INPUT_FILE = candidate
        break

OUTPUT_FILE = 'depo_config.json'
REPORTER_NAME = "UNKNOWN — reporter_name required"   # never default to a real person's name

DAY_NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']


def load_state_label():
    """
    Read cr_config.json from CWD (job's work folder) to determine the state.
    Returns lowercase state_label string, e.g. 'new york wcb' or 'louisiana civil'.
    Falls back to '' if not found — caller treats as unknown state.
    """
    if os.path.exists('cr_config.json'):
        with open('cr_config.json', encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg.get('state_label', '').lower()
    return ''


def is_louisiana(state_label):
    return 'louisiana' in state_label


def is_ny_wcb(state_label):
    return 'new york' in state_label or 'ny' in state_label


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTORS — each returns a value or None
# ─────────────────────────────────────────────────────────────────────────────

def extract_witness_name(lines):
    """
    Find witness name. Tries multiple patterns:
    1. Stipulation: 'testimony of the witness, NAME, is hereby'
    2. Sworn-in standalone line: all-caps name on own line near 'duly sworn'
    3. Caption: line after 'OF' following 'DEPOSITION'
    """
    # Pattern 1: stipulation sentence
    for line in lines:
        m = re.search(r'testimony of the witness,\s+([A-Z][A-Z\s\.]+),\s+is hereby', line)
        if m:
            return m.group(1).strip()

    # Pattern 2: all-caps name on its own line, within 10 lines of 'duly sworn'
    for i, line in enumerate(lines):
        if 'duly sworn' in line.lower():
            for j in range(max(0, i-10), i+1):
                s = lines[j].strip()
                if re.match(r'^[A-Z][A-Z\s\.]{5,}$', s) and ',' not in s:
                    return s
                # "THOMAS L. EASLEY," — name with trailing comma
                m = re.match(r'^([A-Z][A-Z\s\.]{5,}),$', s)
                if m:
                    return m.group(1).strip()

    # Pattern 3: caption — line after "OF" following "DEPOSITION"
    for i, line in enumerate(lines):
        if line.strip() == 'OF' and i > 0 and 'DEPOSITION' in lines[i-1]:
            if i + 1 < len(lines) and lines[i+1].strip():
                return lines[i+1].strip()
    return None


def extract_examining_atty(lines):
    """First 'BY MR./MS. NAME:' line."""
    for line in lines:
        m = re.match(r'^BY ((?:MR\.|MS\.|MRS\.)\s+\w+):', line.strip())
        if m:
            return m.group(1).strip()
    return None


def extract_depo_date_time(lines):
    """
    Pull from videographer opening:
    'Today's date is March 13th, 2026, and the video time is 9:07 a.m.'
    Cross-check with caption 'commencing at X'
    """
    date_str = None
    time_str = None

    for line in lines:
        # Videographer date
        m = re.search(r"Today'?s date is ([A-Z][a-z]+ \d+(?:st|nd|rd|th)?,? \d{4})", line)
        if m and not date_str:
            raw = m.group(1)
            # Remove ordinal suffix: 13th -> 13
            raw = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', raw)
            try:
                dt = datetime.strptime(raw.strip(), "%B %d, %Y")
                day_name = DAY_NAMES[dt.weekday()]
                date_str = dt.strftime(f"{day_name}, %B %-d, %Y") if sys.platform != 'win32' \
                           else f"{day_name}, {dt.strftime('%B')} {dt.day}, {dt.year}"
            except ValueError:
                date_str = raw.strip()

        # Video time from videographer
        m = re.search(r'video time is (\d+:\d+ [ap]\.m\.)', line)
        if m and not time_str:
            time_str = m.group(1)

    # Fallback: 'commencing at X' from caption
    if not time_str:
        for line in lines:
            m = re.search(r'commencing at (\d+:\d+ [ap]\.m\.)', line)
            if m:
                time_str = m.group(1)
                break

    return date_str, time_str


def extract_location(lines):
    """
    Pull from videographer: 'deposition is being held at ADDRESS'
    """
    for line in lines:
        m = re.search(r'being held at (.+?),\s+in the matter', line)
        if m:
            addr = m.group(1).strip()
            # Try to split into street / city-state
            # Common pattern: "111 North Post Oak Lane, Houston, Texas 77024"
            parts = [p.strip() for p in addr.split(',')]
            if len(parts) >= 3:
                loc1 = parts[0]
                loc2 = ', '.join(parts[1:])
                return loc1, loc2
            elif len(parts) == 2:
                return parts[0], parts[1]
            else:
                return addr, ''
    # Fallback: caption lines after "at"
    for i, line in enumerate(lines):
        if line.strip() == 'at' and i + 2 < len(lines):
            return lines[i+1].strip(), lines[i+2].strip()
    return None, None


def extract_caption(lines):
    """Extract parish, court, plaintiff, defendant, docket, division."""
    parish = court = plaintiff = defendant = docket = division = None
    plaintiff_role = "Plaintiffs,"
    defendant_role = "Defendants."

    for line in lines:
        s = line.strip()
        if re.match(r'^PARISH OF ', s) and not parish:
            parish = s
        if re.match(r'^\d+TH JUDICIAL DISTRICT', s) and not court:
            court = s
        m = re.search(r'Docket No\.?\s*([\d\-]+)', s)
        if m and not docket:
            docket = m.group(1).strip()
        m = re.search(r'Division\s+"?([A-Z])"?', s)
        if m and not division:
            division = m.group(1).strip()

    # Plaintiff and defendant: look only in caption (first 60 lines)
    # Caption structure: PLAINTIFF ... v. ... DEFENDANT ... Docket
    caption = lines[:60]
    v_line = None
    for i, line in enumerate(caption):
        if line.strip() in ('v.', 'vs.', 'VS.', 'V.'):
            v_line = i
            break

    if v_line is not None:
        # Plaintiff = all party name lines before v., stopping at skip words
        skip = ('JUDICIAL', 'PARISH', 'LOUISIANA', 'STATE OF',
                'Docket', 'Division', 'Plaintiffs', 'I N ')
        plt_parts = []
        for j in range(v_line - 1, -1, -1):
            s = caption[j].strip()
            if not s or '*' in s:
                if plt_parts:
                    break
                continue
            if any(sk in s for sk in skip):
                continue
            plt_parts.insert(0, s)
        if plt_parts:
            plaintiff = ' '.join(plt_parts)

        # Defendant = first non-empty line after v.
        # Stop at: Defendant(s)., *, Docket, Division, empty after content
        def_parts = []
        for j in range(v_line + 1, min(v_line + 15, len(caption))):
            s = caption[j].strip()
            if not s:
                continue
            if re.match(r'^Defendants?\.?$', s):
                break
            if '*' in s or 'Docket' in s or 'Division' in s:
                break
            def_parts.append(s)
        if def_parts:
            defendant = ' '.join(def_parts)

    return parish, court, plaintiff, plaintiff_role, defendant, defendant_role, docket, division


def extract_state(court, parish):
    """Infer state code from court/parish fields.

    Routing:
      NY Workers' Comp (WCB)   → 'NY'       (AD's measured WC format)
      NY civil/supreme/county  → 'NY_CIVIL' (22 NYCRR § 108.3 format)
      Louisiana (any parish)   → 'LA'
      NJ / CA / other          → None (manual override required in depo_config.json)
    """
    court_upper = (court or '').upper()

    # NY Workers' Compensation Board
    if 'WORKERS' in court_upper and 'COMPENSATION' in court_upper:
        return 'NY'

    # NY civil courts (Supreme Court, County Court, Civil Court, etc.)
    NY_CIVIL_MARKERS = ('SUPREME COURT', 'COUNTY COURT', 'CIVIL COURT',
                        'DISTRICT COURT', 'FAMILY COURT', 'SURROGATE')
    if any(m in court_upper for m in NY_CIVIL_MARKERS):
        return 'NY_CIVIL'

    # Louisiana — any parish reference indicates LA
    if parish:
        return 'LA'

    return None


def extract_case_short(witness_name, defendant):
    """Build a safe filename-friendly case identifier."""
    if not witness_name:
        return "Unknown_Case"
    last = witness_name.split()[-1].capitalize()
    if defendant:
        # Pull first meaningful word from defendant name
        words = [w for w in defendant.split()
                 if w not in ('LLC','INC','CORP','ET','AL','F/K/A','US','2','THE','OF','AND')]
        def_word = words[0].capitalize() if words else "Case"
    else:
        def_word = "Case"
    return f"{last}_{def_word}"


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_BASE = ['witness_name', 'examining_atty', 'depo_date', 'depo_time']
_REQUIRED_LA   = ['location_1', 'parish', 'court', 'plaintiff', 'defendant', 'docket', 'division']


def get_required_fields(state_label):
    """Return the required field list for this state."""
    if is_louisiana(state_label):
        return _REQUIRED_BASE + _REQUIRED_LA
    return _REQUIRED_BASE   # NY WCB and all other states: base fields only


def validate(config, state_label):
    """Return list of problems. Empty list = all good."""
    problems = []
    for key in get_required_fields(state_label):
        if not config.get(key):
            problems.append(f"MISSING: {key}")
        elif str(config[key]).strip() == '':
            problems.append(f"EMPTY: {key}")
    return problems


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Extract depo config from transcript')
    parser.add_argument('--review', action='store_true',
                        help='Print extracted values and confirm before writing')
    parser.add_argument('--force', action='store_true',
                        help='Write without confirmation')
    args = parser.parse_args()

    # ── Manual lock — if depo_config.json was hand-populated, skip extraction ──
    # NOTE: manual lock is always respected — even --force cannot bypass it.
    # --force only skips the interactive Y/n prompt, not the lock.
    # To re-extract over a manual config, edit _extracted_from away from "manual" first.
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding='utf-8') as _chk:
            _existing = json.load(_chk)
        if _existing.get('_extracted_from', '').startswith('manual'):
            print(f"[CONFIG] Manual config detected — skipping extraction.")
            print(f"         (--force does not override a manual lock.)")
            print(f"         Edit _extracted_from in depo_config.json to re-extract.")
            return

    # ── Determine state from cr_config.json in CWD (job's work folder) ──────────
    state_label = load_state_label()
    if state_label:
        print(f"[extract_config] State: {state_label}  (from cr_config.json)")
    else:
        print(f"[extract_config] State: unknown — cr_config.json not found in CWD, showing all fields")

    print(f"Reading: {INPUT_FILE}")
    with open(INPUT_FILE, encoding='utf-8') as f:
        text = f.read()
    lines = text.split('\n')

    print("Extracting case metadata...")

    witness      = extract_witness_name(lines)
    examining    = extract_examining_atty(lines)
    date_str, time_str = extract_depo_date_time(lines)
    state_code   = None

    # Build date_short from date_str
    date_short = None
    if date_str:
        parts = date_str.split(', ', 1)
        date_short = parts[1] if len(parts) == 2 else date_str

    # ── Base config — fields that apply to every state ────────────────────────
    config = {
        "witness_name":     witness     or "UNKNOWN — CHECK RTF",
        "witness_last":     witness.split()[-1] if witness else "UNKNOWN",
        "case_short":       extract_case_short(witness, None),
        "depo_date":        date_str    or "UNKNOWN — CHECK RTF",
        "depo_date_short":  date_short  or "UNKNOWN — CHECK RTF",
        "depo_time":        time_str    or "UNKNOWN — CHECK RTF",
        "examining_atty":   examining   or "UNKNOWN — CHECK RTF",
        "reporter_name":    REPORTER_NAME,
        "cert_year":        date_str.split(', ')[-1][:4] if date_str else "2026",
        "_extracted_from":  INPUT_FILE,
        "_extracted_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # ── Louisiana-only fields — only extracted and shown for LA depos ─────────
    if is_louisiana(state_label) or not state_label:
        loc1, loc2 = extract_location(lines)
        parish, court, plaintiff, plt_role, defendant, def_role, docket, division = \
            extract_caption(lines)
        state_code = extract_state(court, parish)
        config.update({
            "location_1":     loc1       or "UNKNOWN — CHECK RTF",
            "location_2":     loc2       or "",
            "parish":         parish     or "UNKNOWN — CHECK RTF",
            "court":          court      or "UNKNOWN — CHECK RTF",
            "plaintiff":      plaintiff  or "UNKNOWN — CHECK RTF",
            "plaintiff_role": plt_role,
            "defendant":      defendant  or "UNKNOWN — CHECK RTF",
            "defendant_role": def_role,
            "docket":         docket     or "UNKNOWN — CHECK RTF",
            "division":       division   or "UNKNOWN — CHECK RTF",
            "case_short":     extract_case_short(witness, defendant),
        })
    elif is_ny_wcb(state_label):
        state_code = 'NY'

    config["state"] = state_code or "UNKNOWN — CHECK RTF"

    # ── CASE_CAPTION.json overrides — CWD first (job folder), ENGINE_DIR fallback ──
    # CASE_CAPTION.json is authoritative for identity fields — always overrides extraction.
    # Prevents cross-contamination when a previous witness appears in the current depo's text.
    CAPTION_IDENTITY_FIELDS = (
        'witness_name', 'witness_last', 'case_short',
        'examining_atty', 'depo_date', 'depo_date_short', 'depo_time',
    )
    caption_path = 'CASE_CAPTION.json'                                  # CWD = job folder
    if not os.path.exists(caption_path):
        caption_path = os.path.join(ENGINE_DIR, 'CASE_CAPTION.json')   # fallback
    if os.path.exists(caption_path):
        with open(caption_path, encoding='utf-8') as _cf:
            _cap = json.load(_cf)
        _overrides = {}
        for _field in CAPTION_IDENTITY_FIELDS:
            _val = _cap.get(_field, '')
            if _val and not str(_val).startswith('_') and 'TODO' not in str(_val):
                _overrides[_field] = _val
        if 'witness_name' in _overrides and 'witness_last' not in _overrides:
            _overrides['witness_last'] = _overrides['witness_name'].split()[-1]
        if 'case_short' not in _overrides and 'witness_name' in _overrides:
            _last     = _overrides['witness_name'].split()[-1].title()
            _def      = _cap.get('defendant', config.get('defendant', ''))
            _def_short = _def.split()[0].title() if _def else 'Unknown'
            _overrides['case_short'] = f"{_last}_{_def_short}"
        if _overrides:
            config.update(_overrides)
            print(f"[extract_config] CASE_CAPTION.json override: {', '.join(_overrides.keys())}")

    problems = validate(config, state_label)

    print()
    print("=" * 55)
    print("EXTRACTED VALUES")
    print("=" * 55)
    for k, v in config.items():
        if k.startswith('_'):
            continue
        flag = " <-- NEEDS REVIEW" if "UNKNOWN" in str(v) else ""
        print(f"  {k:<20} {v}{flag}")

    if problems:
        print()
        print("VALIDATION PROBLEMS:")
        for p in problems:
            print(f"  *** {p}")
        print()
        print("Edit depo_config.json after writing to fix these.")
    else:
        print()
        print("All required fields extracted successfully.")

    print("=" * 55)

    if not args.force and not args.review:
        # Default: write and report
        pass

    if args.review and not args.force:
        ans = input("\nWrite depo_config.json? [Y/n]: ").strip().lower()
        if ans == 'n':
            print("Aborted — nothing written.")
            return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nWritten: {OUTPUT_FILE}")
    if problems:
        print("ACTION NEEDED: Edit the UNKNOWN fields in depo_config.json before running pipeline.")
    else:
        print("Ready — run the pipeline.")


if __name__ == '__main__':
    main()

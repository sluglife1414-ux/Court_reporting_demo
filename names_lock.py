"""
names_lock.py — Generate names.lock from CASE_CAPTION.json and case dictionary.

Run once per job before the pipeline. Outputs names.lock in the work/ directory.
Any REWORD op in the ops schema that produces a capitalized token not in names.lock
is rejected by validate_ops.py before it reaches the transcript.

Usage:
    python names_lock.py                        # reads CASE_CAPTION.json in cwd
    python names_lock.py path/to/work/          # explicit work dir

Output:
    names.lock — one proper noun per line, lowercase-stripped, sorted
"""

import json
import re
import sys
from pathlib import Path


def extract_names_from_caption(caption: dict) -> set:
    """Pull every proper noun from CASE_CAPTION.json."""
    names = set()

    # Fields that are known to contain proper nouns
    name_fields = [
        "witness_full_name", "witness_name", "witness_last",
        "examining_atty", "deposing_atty_full", "reporter_name", "reporter_name_display",
        "plaintiff", "defendant",
        "venue_name", "case_short",
        "firm_name", "opposing_firm",
    ]

    for field in name_fields:
        val = caption.get(field, "")
        if val:
            for token in _tokenize_name(val):
                names.add(token)

    # Attorney lists (legacy flat list)
    for atty in caption.get("attorneys", []):
        for token in _tokenize_name(atty):
            names.add(token)

    # Zoom attendees (legacy flat list)
    for atty in caption.get("zoom_attorneys", []):
        for token in _tokenize_name(atty):
            names.add(token)

    # Structured appearances block (firms + attorney names)
    for block in caption.get("appearances", []):
        for token in _tokenize_name(block.get("firm", "")):
            names.add(token)
        for token in _tokenize_name(block.get("role", "")):
            names.add(token)
        attorneys = block.get("attorneys", [])
        if isinstance(attorneys, list):
            for atty in attorneys:
                if isinstance(atty, dict):
                    for token in _tokenize_name(atty.get("name", "")):
                        names.add(token)
                else:
                    for token in _tokenize_name(str(atty)):
                        names.add(token)

    # also_present list
    for person in caption.get("also_present", []):
        for token in _tokenize_name(person):
            names.add(token)

    return names


def extract_names_from_kb(kb_text: str) -> set:
    """Extract proper nouns from KNOWLEDGE_BASE.txt (names confirmed in prior depos)."""
    names = set()
    # Look for lines like: NAME: John Smith | John, Smith
    for line in kb_text.splitlines():
        if re.match(r"^\s*(NAME|WITNESS|ATTORNEY|REPORTER)\s*:", line, re.IGNORECASE):
            _, _, rest = line.partition(":")
            for token in _tokenize_name(rest):
                names.add(token)
    return names


def extract_names_from_dictionary(tlx_text: str) -> set:
    """Extract proper nouns from .tlx dictionary (CaseCATalyst custom dict).

    TLX format: steno|translation lines. We only want the translation side,
    and only tokens that are capitalized (proper nouns) and look like real words.
    """
    names = set()
    for line in tlx_text.splitlines():
        if "|" in line:
            _, _, translation = line.partition("|")
            for token in _tokenize_name(translation):
                names.add(token)
    return names


def _tokenize_name(text: str) -> list:
    """Split text, return only capitalized tokens that look like proper nouns.

    Filters out:
    - ALL-CAPS abbreviations (ESQ, CCR, RPR, LLC, etc.)
    - Conjunctions/articles (Of, The, And, etc.)
    - Single letters
    - Numbers
    """
    skip_tokens = {
        "the", "of", "and", "or", "at", "in", "for", "by", "a", "an",
        "esq", "ccr", "rpr", "csr", "llc", "inc", "jr", "sr", "ii", "iii",
        "mr", "ms", "mrs", "dr", "prof",
    }
    tokens = re.findall(r"[A-Za-z'-]+", text)
    result = []
    for tok in tokens:
        stripped = tok.strip("'-")
        if not stripped or len(stripped) < 2:
            continue
        if stripped.lower() in skip_tokens:
            continue
        if stripped.isupper() and len(stripped) <= 4:
            continue  # skip abbreviations
        if stripped[0].isupper():  # only capitalized tokens
            result.append(stripped)
    return result


def build_names_lock(work_dir: Path) -> set:
    """Build the complete names lock set from all available sources."""
    all_names = set()

    # Source 1: CASE_CAPTION.json (most authoritative)
    caption_path = work_dir / "CASE_CAPTION.json"
    if caption_path.exists():
        with open(caption_path, encoding="utf-8") as f:
            caption = json.load(f)
        names = extract_names_from_caption(caption)
        all_names |= names
        print(f"[names_lock] CASE_CAPTION.json: {len(names)} names")
    else:
        # Fall back to depo_config.json
        cfg_path = work_dir / "depo_config.json"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                caption = json.load(f)
            names = extract_names_from_caption(caption)
            all_names |= names
            print(f"[names_lock] depo_config.json fallback: {len(names)} names")

    # Source 2: KNOWLEDGE_BASE.txt (engine-level, not job-level)
    engine_dir = Path(__file__).parent
    kb_path = engine_dir / "KNOWLEDGE_BASE.txt"
    if kb_path.exists():
        with open(kb_path, encoding="utf-8", errors="replace") as f:
            kb_text = f.read()
        names = extract_names_from_kb(kb_text)
        all_names |= names
        print(f"[names_lock] KNOWLEDGE_BASE.txt: {len(names)} names")

    # Source 3: .tlx dictionary files in work dir (case-specific terms)
    for tlx_path in list(work_dir.glob("*.tlx")) + list((work_dir.parent / "intake").glob("*.tlx")):
        try:
            with open(tlx_path, encoding="utf-8", errors="replace") as f:
                tlx_text = f.read()
            names = extract_names_from_dictionary(tlx_text)
            all_names |= names
            print(f"[names_lock] {tlx_path.name}: {len(names)} names")
        except Exception as e:
            print(f"[names_lock] WARNING: could not read {tlx_path.name}: {e}")

    # Always include common depo terms that start with capitals
    always_allow = {
        "Exhibit", "Whereupon", "Identification", "Objection",
        "Videographer", "Reporter", "Counsel", "Court",
        "Zoom",                                   # video attendance qualifier
        "Hotel", "Street", "Suite", "Avenue",     # address components
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday", "January", "February", "March", "April",
        "May", "June", "July", "August", "September", "October",
        "November", "December",
    }
    all_names |= always_allow

    return all_names


def save_names_lock(names: set, out_path: Path):
    """Write names.lock — one name per line, sorted."""
    sorted_names = sorted(names, key=lambda x: x.lower())
    with open(out_path, "w", encoding="utf-8") as f:
        for name in sorted_names:
            f.write(name + "\n")
    print(f"[names_lock] Wrote {len(sorted_names)} names -> {out_path}")


def load_names_lock(lock_path: Path) -> set:
    """Load names.lock into a set. Called by validate_ops.py."""
    if not lock_path.exists():
        return set()
    with open(lock_path, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    work_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    names = build_names_lock(work_dir)
    out_path = work_dir / "names.lock"
    save_names_lock(names, out_path)
    print(f"\nSample names: {sorted(names)[:20]}")

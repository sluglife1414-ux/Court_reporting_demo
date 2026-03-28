"""
build_summary.py — AI-generated lawyer-quality deposition summary.

Reads corrected_text.txt + depo_config.json, calls Claude Haiku,
writes FINAL_DELIVERY/<case>_DEPOSITION_SUMMARY.txt.

USAGE:
  python build_summary.py          # standard run
  python build_summary.py --debug  # print prompt + raw API response

COST: ~$0.06 per depo (Haiku, single pass).
      Passes the 10-cent-per-page design test at any depo size.

DEPENDENCIES:
  - corrected_text.txt    (from ai_engine.py)
  - depo_config.json      (from extract_config.py)
  - ANTHROPIC_API_KEY     (Windows env var)

OUTPUT:
  FINAL_DELIVERY/<case_short>_DEPOSITION_SUMMARY.txt
"""

# ── Standard library ──────────────────────────────────────────────────────────
import os
import sys
import json
import argparse
from datetime import datetime

# ── Third-party ───────────────────────────────────────────────────────────────
try:
    import anthropic
except ImportError:
    print("[ERROR] anthropic package not found. Run: pip install anthropic")
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
MODEL         = "claude-haiku-4-5"
MAX_TOKENS    = 8192          # ~6,000 words — enough for even the longest depo
OUTPUT_DIR    = "FINAL_DELIVERY"
REQUIRED_SIZE = 50_000        # corrected_text.txt sanity check (bytes)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    """Load depo_config.json. Returns dict."""
    path = "depo_config.json"
    if not os.path.exists(path):
        print("[ERROR] depo_config.json not found. Run extract_config.py first.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_transcript():
    """Load corrected_text.txt. Returns full text string."""
    path = "corrected_text.txt"
    if not os.path.exists(path):
        print("[ERROR] corrected_text.txt not found. Run ai_engine.py first.")
        sys.exit(1)
    size = os.path.getsize(path)
    if size < REQUIRED_SIZE:
        print(f"[ERROR] corrected_text.txt looks incomplete ({size:,} bytes < {REQUIRED_SIZE:,}).")
        print("        ai_engine.py may not have finished. Check the file.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_correction_stats():
    """Load basic stats from correction_log.json for the summary footer."""
    path = "correction_log.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    corrections = data.get("corrections", [])
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "N/A": 0}
    for c in corrections:
        conf = c.get("confidence", "")
        if conf in counts:
            counts[conf] += 1
    counts["total"] = len(corrections)
    return counts


def build_prompt(config, transcript):
    """Build the Haiku system + user prompt for the deposition summary."""

    system_prompt = """You are a senior litigation paralegal with 20 years of experience
preparing deposition summaries for trial attorneys. Your summaries are:
- Precise and factual — every claim tied to actual testimony
- Written in plain professional English — no legalese padding
- Organized so a busy attorney can scan in 3 minutes
- Neutral — you report what was said, not whether it was credible

You do not editorialize, speculate, or add information not in the transcript.
When something was unclear or disputed in testimony, say so plainly."""

    user_prompt = f"""Please prepare a complete deposition summary for the following transcript.

CASE INFORMATION:
  Case: {config.get('plaintiff', 'Unknown')} v. {config.get('defendant', 'Unknown')}
  Docket: {config.get('docket', 'Unknown')}
  Court: {config.get('court', 'Unknown')}, {config.get('parish', 'Unknown')}
  Witness: {config.get('witness_name', 'Unknown')}
  Date: {config.get('depo_date', 'Unknown')}
  Examining Attorney: {config.get('examining_atty', 'Unknown')}
  Reporter: {config.get('reporter_name', 'Unknown')}

FULL DEPOSITION TRANSCRIPT:
{transcript}

---

Please provide the summary in the following format:

DEPOSITION SUMMARY
==================
[One paragraph: who is the witness, their role, their relationship to the case,
and the overall scope of examination.]

BACKGROUND & QUALIFICATIONS
[One paragraph on the witness's background, employment history, and relevant
experience as established in testimony.]

KEY TESTIMONY — BY TOPIC
[3-6 paragraphs, one per major topic area covered in the deposition.
Each paragraph should start with a bold topic label, e.g., "Site Conditions:"
Cover the substance of what was established, disputed, or admitted on each topic.]

NOTABLE ADMISSIONS & KEY FACTS
[Bulleted list of the most significant admissions, concessions, or facts
established during examination. These are the lines a trial attorney will
want to find instantly.]

AREAS LEFT UNRESOLVED / FLAGS FOR FOLLOW-UP
[Bulleted list of any testimony that was unclear, contradicted itself,
or raised questions the examining attorney may want to revisit.]"""

    return system_prompt, user_prompt


def output_path(config):
    """Build the output file path from depo_config."""
    case = config.get("case_short", "depo").replace(" ", "_")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, f"{case}_DEPOSITION_SUMMARY.txt")


def build_header(config, stats):
    """Build the plain-text file header block."""
    lines = [
        "=" * 70,
        "DEPOSITION SUMMARY — AI ASSISTED DRAFT",
        "=" * 70,
        f"  Case:     {config.get('plaintiff', '')} v. {config.get('defendant', '')}",
        f"  Docket:   {config.get('docket', '')} — Division {config.get('division', '')}",
        f"  Witness:  {config.get('witness_name', '')}",
        f"  Date:     {config.get('depo_date', '')}",
        f"  Court:    {config.get('court', '')}, {config.get('parish', '')}",
        f"  Reporter: {config.get('reporter_name', '')}",
        "",
        f"  Engine:   MB Demo Engine v4 / {MODEL}",
        f"  Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    if stats:
        lines.append(
            f"  Corrections: {stats.get('total', 0):,} total  "
            f"({stats.get('HIGH', 0)} HIGH / {stats.get('MEDIUM', 0)} MEDIUM / "
            f"{stats.get('LOW', 0)} LOW / {stats.get('N/A', 0)} N/A)"
        )
    lines += [
        "=" * 70,
        "",
        "NOTE: This is an AI-assisted draft. All summaries should be verified",
        "      against the certified transcript before use in any legal proceeding.",
        "",
        "=" * 70,
        "",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build AI deposition summary via Haiku.")
    parser.add_argument("--debug", action="store_true", help="Print prompt + raw API response.")
    args = parser.parse_args()

    # ── Load inputs ───────────────────────────────────────────────────────────
    print("[build_summary] Loading config and transcript...")
    config     = load_config()
    transcript = load_transcript()
    stats      = load_correction_stats()

    chars = len(transcript)
    tokens_est = chars // 4
    print(f"[build_summary] Transcript: {chars:,} chars (~{tokens_est:,} tokens est)")
    print(f"[build_summary] Model: {MODEL}  Max output: {MAX_TOKENS} tokens")

    # ── Build prompt ──────────────────────────────────────────────────────────
    system_prompt, user_prompt = build_prompt(config, transcript)

    if args.debug:
        print("\n--- SYSTEM PROMPT ---")
        print(system_prompt)
        print("\n--- USER PROMPT (first 500 chars) ---")
        print(user_prompt[:500])
        print("...[transcript follows]...")

    # ── Call API ──────────────────────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Fallback: read from Windows registry (set via `setx ANTHROPIC_API_KEY ...`)
        try:
            import winreg
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
            api_key, _ = winreg.QueryValueEx(reg_key, "ANTHROPIC_API_KEY")
        except Exception:
            pass
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not found in environment or Windows registry.")
        print("        Run: setx ANTHROPIC_API_KEY sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("[build_summary] Calling Haiku API...")
    start = datetime.now()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    elapsed = (datetime.now() - start).total_seconds()
    summary_text = response.content[0].text

    # ── Token cost report ─────────────────────────────────────────────────────
    usage = response.usage
    in_tok  = usage.input_tokens
    out_tok = usage.output_tokens
    cost_in  = in_tok  * 0.80  / 1_000_000
    cost_out = out_tok * 4.00  / 1_000_000
    cost_total = cost_in + cost_out

    print(f"[build_summary] Done in {elapsed:.1f}s — "
          f"{in_tok:,} in / {out_tok:,} out — "
          f"cost: ${cost_total:.4f}")

    if args.debug:
        print("\n--- RAW API RESPONSE ---")
        print(summary_text)

    # ── Write output ──────────────────────────────────────────────────────────
    header = build_header(config, stats)
    full_output = header + summary_text + "\n"

    out = output_path(config)
    with open(out, "w", encoding="utf-8") as f:
        f.write(full_output)

    print(f"[build_summary] Written: {out}")
    print(f"[build_summary] Output:  {len(full_output):,} chars")


if __name__ == "__main__":
    main()

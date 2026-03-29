"""
verify_agent.py — Pass 2 verification of HIGH-confidence corrections.

Reads correction_log.json, sends all HIGH-confidence items to Claude in a
single batch API call, and asks: "Do you agree with each correction?"

  AGREE   → stays HIGH
  DISAGREE → drops to MEDIUM (flagged for reporter review)

Output:
  verify_log.json   — full result with agree/disagree + reason per item
  Console summary   — counts, flipped items, cost estimate

Usage:
    python verify_agent.py                          # uses correction_log.json
    python verify_agent.py --log path/to/log.json   # custom log path
"""

import json
import os
import sys
import re
import time
import argparse
import anthropic

# ── Config ───────────────────────────────────────────────────────────────────

MODEL          = 'claude-haiku-4-5-20251001'   # Haiku — cheap for verify pass
MAX_TOKENS     = 4096
LOG_FILE       = 'correction_log.json'
OUTPUT_FILE    = 'verify_log.json'

# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a second-opinion reviewer for court reporter AI corrections.

You will receive a list of HIGH-confidence corrections made to a deposition transcript.
Each correction shows: the original steno text, the corrected text, and the reason given.

Your job: for each item, decide AGREE or DISAGREE.

AGREE if: the correction is clearly correct — the original is a steno artifact, typo,
  or garbled text and the corrected version is the obvious right answer.

DISAGREE if: the correction is uncertain, the original might be intentional, the corrected
  version introduces a guess, or you would want the court reporter to verify it.

Respond ONLY in this exact format — one line per item, no extra text:

ITEM 1: AGREE
ITEM 2: DISAGREE — [one-line reason]
ITEM 3: AGREE
...

Be strict. If you have any doubt, DISAGREE. The goal is to catch overcorrections."""


def build_user_prompt(high_items):
    """Build the batch prompt with all HIGH items numbered."""
    lines = [f"Review these {len(high_items)} HIGH-confidence corrections:\n"]
    for i, item in enumerate(high_items, 1):
        lines.append(f"ITEM {i}:")
        lines.append(f"  Original:  {repr(item['original'])}")
        lines.append(f"  Corrected: {repr(item['corrected'])}")
        lines.append(f"  Reason:    {item.get('reason', 'none given')}")
        lines.append("")
    return "\n".join(lines)


def parse_verify_response(response_text, high_items):
    """Parse Claude's ITEM N: AGREE/DISAGREE response into structured results."""
    results = []
    lines = response_text.strip().split('\n')

    item_map = {}
    for line in lines:
        m = re.match(r'ITEM\s+(\d+):\s+(AGREE|DISAGREE)\s*(?:[-—]\s*(.*))?', line.strip(), re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1   # 0-based
            verdict = m.group(2).upper()
            note = m.group(3).strip() if m.group(3) else ''
            item_map[idx] = (verdict, note)

    for i, item in enumerate(high_items):
        verdict, note = item_map.get(i, ('PARSE_ERROR', 'response line not found'))
        results.append({
            'line_approx':  item['line_approx'],
            'original':     item['original'],
            'corrected':    item['corrected'],
            'reason':       item.get('reason', ''),
            'verdict':      verdict,
            'verify_note':  note,
        })

    return results


def run_verify(log_path):
    """Main verify pass."""
    # Load correction log
    if not os.path.exists(log_path):
        print(f"[ERROR] {log_path} not found.")
        sys.exit(1)

    with open(log_path, encoding='utf-8') as f:
        log = json.load(f)

    corrections = log.get('corrections', [])
    high_items  = [c for c in corrections if c.get('confidence') == 'HIGH']

    print(f"\n{'='*60}")
    print(f"VERIFY AGENT — Pass 2")
    print(f"{'='*60}")
    print(f"Total corrections: {len(corrections)}")
    print(f"HIGH items to verify: {len(high_items)}")

    if not high_items:
        print("[INFO] No HIGH items found. Nothing to verify.")
        return

    # Build and send prompt
    user_prompt = build_user_prompt(high_items)
    print(f"\nSending {len(high_items)} items to {MODEL}...")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('[ERROR] ANTHROPIC_API_KEY not set. Run from CMD where key is set.')
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    t0 = time.time()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_prompt}]
    )

    elapsed = round(time.time() - t0, 1)
    response_text = response.content[0].text

    input_tokens  = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    # Parse results
    results = parse_verify_response(response_text, high_items)

    # Stats
    agreed    = [r for r in results if r['verdict'] == 'AGREE']
    disagreed = [r for r in results if r['verdict'] == 'DISAGREE']
    errors    = [r for r in results if r['verdict'] == 'PARSE_ERROR']

    print(f"\nRESULTS ({elapsed}s):")
    print(f"  AGREE:      {len(agreed):3d}  (stays HIGH)")
    print(f"  DISAGREE:   {len(disagreed):3d}  (drops to MEDIUM — reporter should review)")
    print(f"  Parse error:{len(errors):3d}")
    print(f"  Tokens: {input_tokens} in / {output_tokens} out")

    # Estimate cost (Haiku pricing: $0.80/1M input, $4.00/1M output)
    cost = (input_tokens / 1_000_000 * 0.80) + (output_tokens / 1_000_000 * 4.00)
    print(f"  Cost: ~${cost:.4f}")

    if disagreed:
        print(f"\nDISAGREED ITEMS ({len(disagreed)}):")
        for r in disagreed:
            print(f"  line ~{r['line_approx']}: {repr(r['original'][:50])} → {repr(r['corrected'][:50])}")
            if r['verify_note']:
                print(f"    Note: {r['verify_note']}")

    # Save verify log
    output = {
        'source_log':      log_path,
        'model':           MODEL,
        'high_count':      len(high_items),
        'agree_count':     len(agreed),
        'disagree_count':  len(disagreed),
        'parse_errors':    len(errors),
        'elapsed_seconds': elapsed,
        'input_tokens':    input_tokens,
        'output_tokens':   output_tokens,
        'cost_usd':        round(cost, 6),
        'results':         results,
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nVerify log saved: {OUTPUT_FILE}")
    print(f"{'='*60}\n")

    return output


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pass 2 verify agent for HIGH-confidence corrections')
    parser.add_argument('--log', default=LOG_FILE, help=f'Path to correction_log.json (default: {LOG_FILE})')
    args = parser.parse_args()

    run_verify(args.log)

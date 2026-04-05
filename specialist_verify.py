"""
specialist_verify.py — 6-agent specialist verification pass.

Runs after verify_agent.py (Pass 2). Each specialist agent examines the
HIGH-confidence corrections from a different lens and flags additional
items for reporter review.

AGENTS:
  InterpolationAgent  — catches silent word insertions (words added not in original steno)
  GrammarAgent        — validates grammar/agreement corrections are actually right
  SpeakerAgent        — verifies speaker attribution changes (Q→A, MR.X→MR.Y, etc.)
  ConsistencyAgent    — flags corrections that contradict other mentions in transcript
  DomainAgent         — domain-specific term verification (WC, medical, legal)
  PunctuationAgent    — punctuation and capitalization correction checks

All agents use Haiku. Each runs a single batch API call. The Collector
aggregates results into specialist_verify_log.json.

Usage:
    python specialist_verify.py                          # uses correction_log.json
    python specialist_verify.py --log correction_log.json
    python specialist_verify.py --agents grammar,domain  # run specific agents only
"""

import json
import os
import sys
import re
import time
import argparse
import anthropic

# AI output can contain Unicode (arrows, quotes, em-dashes) — force UTF-8 so
# cp1252 Windows console never crashes on AI-generated text.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Config ───────────────────────────────────────────────────────────────────

MODEL      = 'claude-haiku-4-5-20251001'
MAX_TOKENS = 4096
BATCH_SIZE = 150    # items per API call — keeps output well under MAX_TOKENS
LOG_FILE   = 'correction_log.json'
OUTPUT_FILE = 'specialist_verify_log.json'

# ── Agent definitions ─────────────────────────────────────────────────────────

AGENTS = {
    'interpolation': {
        'name': 'InterpolationAgent',
        'description': 'Catches silent word insertions — words added to the corrected version that have no basis in the original steno',
        'system': """You are a court reporter AI reviewing transcript corrections for silent interpolations.

A silent interpolation is when the AI correction pass ADDED a word or phrase that is not present in the original steno — not a typo fix, not a phonetic substitution, but a new word invented by the AI that the witness may not have said.

You will receive HIGH-confidence corrections. For each item, look at: original (steno), corrected (AI version), and reason.

FLAG any correction where:
- A word appears in the corrected version that has no phonetic or visual basis in the original
- The AI appears to have "filled in" missing context rather than decoding what was written
- The change adds meaning rather than just fixing a garbled word

Respond ONLY in this exact format — one line per item:
ITEM 1: CLEAR — no interpolation
ITEM 2: FLAG — [one-line reason: what was inserted and why it's suspicious]
ITEM 3: CLEAR — no interpolation

Be conservative. Only FLAG when you can point to a specific invented word.""",
    },

    'grammar': {
        'name': 'GrammarAgent',
        'description': 'Validates grammar and agreement corrections are actually correct',
        'system': """You are a court reporter AI reviewing transcript corrections for grammar errors.

You will receive HIGH-confidence corrections tagged as grammar fixes. Your job is to verify the correction actually improves the grammar — not introduces a new error, changes voice, or alters meaning.

For each item, check:
- Subject-verb agreement: is it actually wrong in the original? Is the correction right?
- Tense: did the AI change tense unnecessarily? Deposition testimony often uses past tense.
- Voice: did the AI change active to passive (or vice versa) when the original may be intentional?
- Corrections of colloquial speech: witnesses speak colloquially — "ain't", "we was" — these are VERBATIM and should NOT be corrected.

Respond ONLY in this exact format:
ITEM 1: VALID — correction is correct
ITEM 2: FLAG — [one-line reason]
ITEM 3: VALID — correction is correct""",
    },

    'speaker': {
        'name': 'SpeakerAgent',
        'description': 'Verifies speaker attribution changes are supported',
        'system': """You are a court reporter AI reviewing transcript corrections that change speaker attribution.

Speaker attribution corrections include: changing Q. to A. or vice versa, changing MR./MS./THE WITNESS: labels, or any other change to who is speaking.

For each correction, assess:
- Is there clear evidence in the original steno that the attribution was wrong?
- Could the original attribution be correct and the AI be misreading the flow?
- Speaker attribution errors are HIGH RISK — a wrong attribution puts words in the wrong person's mouth.

Flag any attribution change where the basis is unclear or where reasonable doubt exists.

Respond ONLY in this exact format:
ITEM 1: CLEAR — attribution change is supported
ITEM 2: FLAG — [one-line reason]
ITEM 3: CLEAR — attribution change is supported""",
    },

    'consistency': {
        'name': 'ConsistencyAgent',
        'description': 'Flags corrections that contradict other mentions in the transcript',
        'system': """You are a court reporter AI reviewing transcript corrections for internal consistency.

You will receive HIGH-confidence corrections along with a sample of surrounding context from the transcript.

Check each correction against its context:
- Does the corrected version contradict something said earlier or later in the excerpt?
- Names: if a person's name was corrected, does it match other references to that person?
- Numbers: if a number was corrected, is it consistent with related numbers mentioned?
- Dates: if a date was corrected, is it consistent with the timeline established elsewhere?

Respond ONLY in this exact format:
ITEM 1: CONSISTENT — no contradictions found
ITEM 2: FLAG — [one-line reason: what contradicts what]
ITEM 3: CONSISTENT — no contradictions found""",
    },

    'domain': {
        'name': 'DomainAgent',
        'description': 'Verifies domain-specific terms (legal, medical, workers comp)',
        'system': """You are a court reporter AI reviewing transcript corrections for domain-specific accuracy.

This is a workers' compensation or civil deposition. Domain terms include: legal procedure terms, medical terminology, anatomical names, drug names, workers' comp procedural terms (WCB, IME, MMI, Schedule Loss of Use, etc.), and industry-specific jargon.

For each correction that touches a domain term, verify:
- Is the corrected term spelled and used correctly for this domain?
- Is the original potentially correct (a different term the AI may not recognize)?
- Did the AI change a technical term to something more common but less precise?

Respond ONLY in this exact format:
ITEM 1: VALID — domain term is correct
ITEM 2: FLAG — [one-line reason]
ITEM 3: VALID — domain term is correct""",
    },

    'punctuation': {
        'name': 'PunctuationAgent',
        'description': 'Checks punctuation and capitalization corrections',
        'system': """You are a court reporter AI reviewing transcript corrections to punctuation and capitalization.

Check each punctuation/capitalization correction:
- Em dash vs. hyphen: correct usage for deposition transcripts (em dash = interruption/cutoff, hyphen = compound word)
- Comma placement: does the correction change meaning via comma splice or omission?
- Capitalization: proper nouns, titles, and court-specific terms must follow consistent rules
- Ellipsis vs. period: ellipsis = trailing off, not every pause
- Q. and A. labels: these use a period, not a colon

Flag corrections where the change is wrong or ambiguous.

Respond ONLY in this exact format:
ITEM 1: VALID — punctuation correction is correct
ITEM 2: FLAG — [one-line reason]
ITEM 3: VALID — punctuation correction is correct""",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_corrections(log_path):
    if not os.path.exists(log_path):
        print(f"[ERROR] {log_path} not found.")
        sys.exit(1)
    with open(log_path, encoding='utf-8') as f:
        data = json.load(f)
    return data.get('corrections', [])


def build_items_prompt(high_items, include_context=False):
    """Build the numbered items prompt for any agent."""
    lines = [f"Review these {len(high_items)} HIGH-confidence corrections:\n"]
    for i, item in enumerate(high_items, 1):
        lines.append(f"ITEM {i}:")
        lines.append(f"  Original:  {repr(item.get('original', ''))}")
        lines.append(f"  Corrected: {repr(item.get('corrected', ''))}")
        lines.append(f"  Reason:    {item.get('reason', 'none given')}")
        if include_context and item.get('context'):
            ctx = item['context'][:200].replace('\n', ' ')
            lines.append(f"  Context:   {ctx}")
        lines.append("")
    return "\n".join(lines)


def parse_agent_response(response_text, high_items, flag_keyword='FLAG'):
    """Parse ITEM N: CLEAR/VALID/FLAG response into structured results."""
    results = []
    item_map = {}
    for line in response_text.strip().split('\n'):
        m = re.match(r'ITEM\s+(\d+):\s+(\w+)\s*(?:[-—]\s*(.*))?', line.strip(), re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            verdict = m.group(2).upper()
            note = m.group(3).strip() if m.group(3) else ''
            item_map[idx] = (verdict, note)

    for i, item in enumerate(high_items):
        verdict, note = item_map.get(i, ('PARSE_ERROR', 'response line not found'))
        is_flag = (verdict == flag_keyword.upper() or verdict == 'FLAG')
        results.append({
            'line_approx': item.get('line_approx', '?'),
            'original':    item.get('original', ''),
            'corrected':   item.get('corrected', ''),
            'reason':      item.get('reason', ''),
            'verdict':     verdict,
            'flagged':     is_flag,
            'note':        note,
        })
    return results


def run_agent(agent_key, agent_cfg, high_items, client):
    """Run a single specialist agent, batching if item count exceeds BATCH_SIZE.

    Large depos (1000+ HIGH items) would overflow MAX_TOKENS in a single call.
    Each batch is BATCH_SIZE items — output stays well under 4096 tokens.
    Results are merged across batches before returning.
    """
    name = agent_cfg['name']
    include_ctx = (agent_key == 'consistency')
    batches = [high_items[i:i+BATCH_SIZE] for i in range(0, len(high_items), BATCH_SIZE)]
    n_batches = len(batches)

    print(f"\n  [{name}] {agent_cfg['description']}")
    print(f"  [{name}] {len(high_items)} items → {n_batches} batch(es) of ≤{BATCH_SIZE}")

    all_results = []
    total_input_tok = total_output_tok = 0
    t0 = time.time()

    for b_idx, batch in enumerate(batches, 1):
        prompt = build_items_prompt(batch, include_context=include_ctx)
        if n_batches > 1:
            print(f"  [{name}] Batch {b_idx}/{n_batches} ({len(batch)} items)...", end=' ', flush=True)
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=agent_cfg['system'],
                messages=[{'role': 'user', 'content': prompt}]
            )
        except Exception as e:
            print(f"\n  [{name}] API error on batch {b_idx}: {e}")
            return None

        response_text = response.content[0].text
        total_input_tok  += response.usage.input_tokens
        total_output_tok += response.usage.output_tokens
        batch_results = parse_agent_response(response_text, batch)
        all_results.extend(batch_results)
        if n_batches > 1:
            flagged_in_batch = sum(1 for r in batch_results if r['flagged'])
            print(f"{flagged_in_batch} flagged")

    elapsed = round(time.time() - t0, 1)
    cost = (total_input_tok / 1_000_000 * 0.80) + (total_output_tok / 1_000_000 * 4.00)
    flagged = [r for r in all_results if r['flagged']]

    print(f"  [{name}] Done in {elapsed}s — {len(flagged)}/{len(all_results)} flagged  (${cost:.4f})")
    for r in flagged:
        print(f"    FLAG line~{r['line_approx']}: {repr(r['original'][:50])} → {repr(r['corrected'][:50])}")
        if r['note']:
            print(f"         {r['note']}")

    return {
        'agent':          name,
        'agent_key':      agent_key,
        'items_reviewed': len(all_results),
        'flagged_count':  len(flagged),
        'elapsed_seconds': elapsed,
        'input_tokens':   total_input_tok,
        'output_tokens':  total_output_tok,
        'cost_usd':       round(cost, 6),
        'results':        all_results,
    }


def collect_flags(agent_results):
    """
    Collector: aggregate flags across all agents.
    For each item, list which agents flagged it and why.
    Returns a summary list sorted by flag count descending.
    """
    # item_key = (line_approx, original[:40])
    flag_map = {}
    for agent_result in agent_results:
        if agent_result is None:
            continue
        for r in agent_result.get('results', []):
            if not r['flagged']:
                continue
            key = (r['line_approx'], r['original'][:40])
            if key not in flag_map:
                flag_map[key] = {
                    'line_approx': r['line_approx'],
                    'original':    r['original'],
                    'corrected':   r['corrected'],
                    'reason':      r['reason'],
                    'agents':      [],
                }
            flag_map[key]['agents'].append({
                'agent': agent_result['agent'],
                'note':  r['note'],
            })

    summary = list(flag_map.values())
    summary.sort(key=lambda x: len(x['agents']), reverse=True)
    return summary


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='6-agent specialist verification pass')
    parser.add_argument('--log', default=LOG_FILE,
                        help=f'Path to correction_log.json (default: {LOG_FILE})')
    parser.add_argument('--agents', default='',
                        help='Comma-separated list of agents to run (default: all). '
                             f'Choices: {", ".join(AGENTS.keys())}')
    parser.add_argument('--out', default=OUTPUT_FILE,
                        help=f'Output path (default: {OUTPUT_FILE})')
    args = parser.parse_args()

    # Which agents to run
    if args.agents:
        requested = [a.strip().lower() for a in args.agents.split(',')]
        unknown = [a for a in requested if a not in AGENTS]
        if unknown:
            print(f"[ERROR] Unknown agents: {unknown}")
            print(f"        Valid: {', '.join(AGENTS.keys())}")
            sys.exit(1)
        agents_to_run = {k: v for k, v in AGENTS.items() if k in requested}
    else:
        agents_to_run = AGENTS

    corrections = load_corrections(args.log)
    high_items  = [c for c in corrections if c.get('confidence') == 'HIGH']

    print(f"\n{'='*60}")
    print(f"SPECIALIST VERIFY — 6-Agent Pass")
    print(f"{'='*60}")
    print(f"Correction log:  {args.log}")
    print(f"Total corrections: {len(corrections)}")
    print(f"HIGH items:        {len(high_items)}")
    print(f"Agents to run:     {', '.join(agents_to_run.keys())}")

    if not high_items:
        print("[INFO] No HIGH items. Nothing to verify.")
        return

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('[ERROR] ANTHROPIC_API_KEY not set.')
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    # Run all agents
    agent_results = []
    total_cost = 0.0
    for key, cfg in agents_to_run.items():
        result = run_agent(key, cfg, high_items, client)
        if result:
            agent_results.append(result)
            total_cost += result['cost_usd']

    # Collector pass
    flagged_items = collect_flags(agent_results)

    print(f"\n{'='*60}")
    print(f"COLLECTOR SUMMARY")
    print(f"{'='*60}")
    print(f"Total items reviewed: {len(high_items)}")
    print(f"Items flagged by 1+ agents: {len(flagged_items)}")
    print(f"Total cost: ~${total_cost:.4f}")

    if flagged_items:
        multi_flag = [x for x in flagged_items if len(x['agents']) > 1]
        print(f"\nMulti-agent flags ({len(multi_flag)}) — highest confidence issues:")
        for item in multi_flag:
            agents_str = ', '.join(a['agent'] for a in item['agents'])
            print(f"  line~{item['line_approx']} [{agents_str}]")
            print(f"    {repr(item['original'][:60])} → {repr(item['corrected'][:60])}")

    # Write output
    output = {
        'source_log':      args.log,
        'model':           MODEL,
        'high_count':      len(high_items),
        'agents_run':      list(agents_to_run.keys()),
        'total_cost_usd':  round(total_cost, 6),
        'flagged_item_count': len(flagged_items),
        'agent_results':   agent_results,
        'collector_flags': flagged_items,
    }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSpecialist log saved: {args.out}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

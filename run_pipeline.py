"""
run_pipeline.py — Master runner for mb_demo_engine_v4.

Runs all steps in order and produces the full 10-file delivery package:
  1. extract_rtf.py          → extracted_text.txt
  2. steno_cleanup.py        → cleaned_text.txt
  3. ai_engine.py            → corrected_text.txt + correction_log.json
  4. format_final.py         → FINAL_DELIVERY/Easley_YellowRock_FINAL_FORMATTED.txt
  5. build_pdf.py            → FINAL_DELIVERY/Easley_YellowRock_FINAL.pdf
  6. build_transcript.py     → FINAL_DELIVERY/Easley_YellowRock_FINAL_TRANSCRIPT.txt
  7. build_condensed.py      → FINAL_DELIVERY/Easley_YellowRock_CONDENSED.txt
  8. build_deliverables.py   → FINAL_DELIVERY/DELIVERY_CHECKLIST.txt
                               FINAL_DELIVERY/DEPOSITION_SUMMARY.txt
                               FINAL_DELIVERY/EXHIBIT_INDEX.txt
                               FINAL_DELIVERY/MEDICAL_TERMS_LOG.txt
                               FINAL_DELIVERY/PROOF_OF_WORK.txt
                               FINAL_DELIVERY/QA_FLAGS.txt
"""
import subprocess
import sys
import os

STEPS = [
    ('extract_rtf.py',       'Extract RTF -> raw text'),
    ('steno_cleanup.py',     'Steno cleanup -> cleaned text'),
    ('ai_engine.py',         'AI correction pass -> corrected text + correction log'),
    ('format_final.py',      'Format final -> FINAL_FORMATTED.txt'),
    ('build_pdf.py',         'Build PDF -> FINAL.pdf'),
    ('build_transcript.py',  'Build transcript -> FINAL_TRANSCRIPT.txt'),
    ('build_condensed.py',   'Build condensed -> CONDENSED.txt'),
    ('build_deliverables.py','Build deliverables -> 6 analysis docs'),
]

print("=" * 60)
print("MB DEMO ENGINE v4 — FULL PIPELINE")
print("=" * 60)

for script, description in STEPS:
    print(f"\n[STEP] {description}")
    print(f"       Running {script}...")
    result = subprocess.run([sys.executable, script], capture_output=False)
    if result.returncode != 0:
        print(f"\n[ERROR] {script} failed with exit code {result.returncode}")
        print("Pipeline stopped. Fix the error above and re-run.")
        sys.exit(1)

print("\n" + "=" * 60)
print("PIPELINE COMPLETE")
print("=" * 60)
print("\nFINAL_DELIVERY/ now contains:")
delivery_dir = 'FINAL_DELIVERY'
for fname in sorted(os.listdir(delivery_dir)):
    fpath = os.path.join(delivery_dir, fname)
    size = os.path.getsize(fpath)
    print(f"  {fname:<45} {size:>8,} bytes")
print()

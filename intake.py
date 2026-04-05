"""
intake.py — Job intake gate for mb_demo_engine_v4.

Creates a structured job folder, stages input files, injects cr_config.json
from the CR's profile directory, and scaffolds CASE_CAPTION.json.

USAGE:
  python intake.py --cr-id dalotto_ny_001 --rtf path/to/file.rtf
  python intake.py --cr-id muir_mb_001 --rtf path/to/file.rtf --audio path/to/audio.mp4
  python intake.py --cr-id dalotto_ny_001 --rtf path/to/file.rtf --data-dir C:/depo_transformation/data

WHAT IT CREATES:
  {DATA_DIR}/cr_profiles/{cr_id}/{job_id}/
    intake/
      {rtf_filename}        ← original (read-only after receipt)
      {audio_filename}      ← original (read-only, if --audio provided)
      CASE_INFO.json        ← simple case info skeleton (fill before running)
      INTAKE_RECEIPT.md     ← log of what was received
    work/
      CASE_CAPTION.json     ← full engine-ready caption (fill all TODO values)
      cr_config.json        ← injected from CR profile (do not edit here)
      {rtf_filename}        ← working copy for pipeline (extract_rtf.py reads this)
    delivery/               ← empty — output lands here (future automation)

JOB ID FORMAT:
  {cr_id}_{YYYYMMDD}_{case_slug}
  Example: dalotto_ny_001_20260405_fourman

CR PROFILE MUST CONTAIN (in {DATA_DIR}/cr_profiles/{cr_id}/):
  cr_config.json      ← required — formatter, module references
  (HOUSE_STYLE_MODULE.md, KNOWLEDGE_BASE.txt live here for future module migration)

RUNNING THE PIPELINE AFTER INTAKE:
  1. Fill in work/CASE_CAPTION.json  — replace all TODO values
  2. python run_pipeline.py --job-dir "{work_dir}"
     Add --skip-ai if corrected_text.txt already exists and is good.
"""
# ──────────────────────────────────────────────────────────────
# v1.1  2026-04-05  match actual structure: jobs inside cr_profile/{job_id}/intake+work+delivery
# v1.0  2026-04-05  initial
# ──────────────────────────────────────────────────────────────

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)
from paths import get_data_dir, get_cr_profile_dir, get_job_dir, get_job_work_dir


# ── CASE_INFO.json — simple intake form (what the CR would fill out on the web) ──
# Stored in intake/ as the read-only record of what the CR submitted.
def _case_info_skeleton(cr_id, slug):
    return {
        "_note": "Fill in before running pipeline. This is the raw intake form — "
                 "engine reads work/CASE_CAPTION.json.",
        "cr_id":            cr_id,
        "submission_date":  str(date.today()),
        "depo": {
            "type":   "TODO (e.g. TELEPHONIC, IN-PERSON)",
            "date":   "TODO (e.g. March 24, 2026)",
            "time":   "TODO (e.g. 4:03 p.m.)"
        },
        "witness": {
            "name":        "TODO First Last",
            "credentials": None,
            "role":        "TODO (e.g. non-party witness)"
        },
        "case": {
            "jurisdiction":    "TODO (e.g. Workers Compensation Board — State of New York)",
            "wcb_number":      None,
            "carrier_number":  None,
            "claimant":        None,
            "employer":        None,
            "date_of_accident": None
        },
        "attorneys": [
            {
                "role":    "TODO (e.g. Attorneys for Claimant)",
                "firm":    "TODO Firm Name",
                "address": "TODO Street, City, State ZIP",
                "by":      "TODO Attorney Name, Esq."
            }
        ],
        "rush":                False,
        "include_condensed":   True,
        "include_concordance": None,
        "audio_provided":      False,
        "dictionary_provided": False,
        "special_instructions": None
    }


# ── CASE_CAPTION.json — engine-ready caption (full fields, all TODO) ──────────
# Stored in work/ — this is what run_pipeline.py reads at runtime.
def _caption_skeleton(cr_id, slug):
    return {
        "_source":       "intake.py scaffold — replace all TODO values before running pipeline",
        "_last_updated": str(date.today()),

        "case_short":  slug.replace('_', ' ').title(),
        "state":       "TODO (e.g. NY or LA)",
        "cr_id":       cr_id,

        "witness_name":  "TODO WITNESS FULL NAME CAPS (e.g. JOHN DOE, M.D.)",
        "witness_last":  "TODO LASTNAME",
        "witness_title": None,
        "depo_type":     "TODO (e.g. TELEPHONIC DEPOSITION)",
        "witness_role":  "TODO (e.g. a non-party witness herein)",

        "claimant":      "TODO CLAIMANT NAME",
        "claimant_role": "TODO (e.g. Claimant,)",
        "employer":      "TODO EMPLOYER NAME",
        "employer_role": "TODO (e.g. Employer.)",

        "wcb_case_no":      None,
        "carrier_case_no":  None,
        "date_of_accident": None,

        "depo_date":       "TODO (e.g. March 24, 2026)",
        "depo_date_short": "TODO (e.g. March 24, 2026)",
        "depo_time":       "TODO (e.g. 4:03 p.m.)",

        "reporter_name":         "TODO REPORTER FULL NAME CAPS",
        "reporter_name_display": "TODO Reporter Display Name",
        "reporter_title":        "TODO (e.g. Notary Public of the State of New York)",
        "reporter_credential_1": None,
        "reporter_credential_2": None,
        "reporter_address":      "TODO Street, City, State ZIP",
        "reporter_phone":        "TODO Phone",
        "reporter_license":      "TODO LicenseNumber",

        "examining_atty": "TODO (e.g. MR. SMITH)",

        "appearances": [
            {
                "role":           "TODO Attorneys for [Party]",
                "firm":           "TODO FIRM NAME CAPS",
                "address_1":      "TODO Street Address",
                "city_state_zip": "TODO City, State ZIP",
                "attorneys": [
                    {"name": "TODO ATTORNEY NAME, ESQ."}
                ]
            }
        ],

        "exhibit_list": []
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description='Depo engine — job intake gate',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--cr-id', required=True, metavar='CR_ID',
        help='CR identifier (e.g. dalotto_ny_001, muir_mb_001). '
             'Must match a folder in data/cr_profiles/.'
    )
    parser.add_argument(
        '--rtf', metavar='PATH',
        help='Path to RTF input file. Copied to intake/ (original) and work/ (pipeline copy).'
    )
    parser.add_argument(
        '--audio', metavar='PATH',
        help='Path to audio file (mp4, m4a, wav, etc.). Optional. Copied to intake/ only.'
    )
    parser.add_argument(
        '--job-name', metavar='SLUG',
        help='Short case slug used in job ID (e.g. fourman). '
             'Auto-derived from RTF filename if omitted.'
    )
    parser.add_argument(
        '--data-dir', metavar='PATH', dest='data_dir',
        help='Override DATA_DIR. Defaults to DEPO_DATA_DIR env var or sibling data/ folder.'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Overwrite existing job folder without prompting.'
    )
    return parser.parse_args()


def derive_slug(rtf_path):
    """
    Derive a short lowercase slug from the RTF filename.
    Strips leading 4-digit date prefix (e.g. 0324) and trailing _T suffix.
    Returns 'job' if nothing useful can be extracted.

    Examples:
      0324Fourman2026_T.rtf  -> fourman
      Halprin_YellowRock.rtf -> halprin_yellowrock
    """
    if not rtf_path:
        return 'job'
    stem = os.path.splitext(os.path.basename(rtf_path))[0]
    stem = re.sub(r'^\d{4}', '', stem)                    # strip leading date (0324)
    stem = re.sub(r'_T$', '', stem, flags=re.IGNORECASE)  # strip _T suffix
    stem = re.sub(r'\d{4}$', '', stem)                    # strip trailing year
    slug = stem[:20].strip().lower().replace(' ', '_').replace('-', '_')
    return slug or 'job'


def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def main():
    args = parse_args()

    # ── Resolve DATA_DIR ─────────────────────────────────────────────────────
    try:
        data_dir = get_data_dir(args.data_dir)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    print(f"[INTAKE] DATA_DIR  : {data_dir}")

    # ── Validate CR profile ──────────────────────────────────────────────────
    profile_dir = get_cr_profile_dir(data_dir, args.cr_id)
    if not os.path.isdir(profile_dir):
        print(f"[ERROR] CR profile not found: {profile_dir}")
        print(f"        Create folder + cr_config.json to onboard this reporter.")
        sys.exit(1)

    cr_config_src = os.path.join(profile_dir, 'cr_config.json')
    if not os.path.exists(cr_config_src):
        print(f"[ERROR] cr_config.json missing from CR profile: {profile_dir}")
        print(f"        Every CR profile requires cr_config.json before intake can run.")
        sys.exit(1)

    print(f"[INTAKE] CR profile: {args.cr_id}  OK")

    # ── Validate input files ─────────────────────────────────────────────────
    if args.rtf and not os.path.exists(args.rtf):
        print(f"[ERROR] RTF file not found: {args.rtf}")
        sys.exit(1)
    if args.audio and not os.path.exists(args.audio):
        print(f"[ERROR] Audio file not found: {args.audio}")
        sys.exit(1)

    # ── Build job ID ─────────────────────────────────────────────────────────
    slug   = args.job_name or derive_slug(args.rtf)
    today  = date.today().strftime('%Y%m%d')
    job_id = f"{args.cr_id}_{today}_{slug}"

    # ── Create folder structure ───────────────────────────────────────────────
    job_dir      = get_job_dir(data_dir, args.cr_id, job_id)
    intake_dir   = os.path.join(job_dir, 'intake')
    work_dir     = os.path.join(job_dir, 'work')
    delivery_dir = os.path.join(job_dir, 'delivery')

    if os.path.exists(job_dir):
        if args.force:
            print(f"[WARN] Job folder already exists — overwriting (--force).")
        else:
            print(f"[WARN] Job folder already exists: {job_dir}")
            confirm = input("         Overwrite contents? (y/n): ").strip().lower()
            if confirm != 'y':
                print("[INTAKE] Aborted.")
                sys.exit(0)

    for d in (intake_dir, work_dir, delivery_dir):
        os.makedirs(d, exist_ok=True)

    print(f"[INTAKE] Job folder: {job_dir}")

    # ── intake/ — originals (read-only after this point) ─────────────────────
    # RTF original
    if args.rtf:
        shutil.copy2(args.rtf, os.path.join(intake_dir, os.path.basename(args.rtf)))
        print(f"[INTAKE] RTF -> intake/  : {os.path.basename(args.rtf)}")

    # Audio original
    if args.audio:
        shutil.copy2(args.audio, os.path.join(intake_dir, os.path.basename(args.audio)))
        print(f"[INTAKE] Audio -> intake/: {os.path.basename(args.audio)}")

    # CASE_INFO.json — simple intake form
    write_json(os.path.join(intake_dir, 'CASE_INFO.json'), _case_info_skeleton(args.cr_id, slug))
    print(f"[INTAKE] CASE_INFO.json skeleton -> intake/")

    # INTAKE_RECEIPT.md
    rtf_line   = f"| {os.path.basename(args.rtf)} | — | Not verified | RTF input |" if args.rtf else "| (no RTF provided) | — | — | Copy to intake/ manually |"
    audio_line = f"| {os.path.basename(args.audio)} | — | Not verified | Audio |" if args.audio else ""
    receipt_md = f"""# Intake Receipt — {job_id}
**Received:** {date.today()}
**CR:** {args.cr_id}
**Job ID:** {job_id}

## Files Received
| File | Size | Hash | Notes |
|------|------|------|-------|
{rtf_line}
{audio_line}

## Notes
Files in intake/ are READ-ONLY after receipt.
Do not modify. These are the originals as delivered.
Pipeline reads from work/ — not intake/.
"""
    with open(os.path.join(intake_dir, 'INTAKE_RECEIPT.md'), 'w', encoding='utf-8') as f:
        f.write(receipt_md.strip())
    print(f"[INTAKE] INTAKE_RECEIPT.md -> intake/")

    # ── work/ — pipeline working directory ───────────────────────────────────
    # RTF working copy — pipeline's extract_rtf.py looks for *.rtf in CWD (work/)
    if args.rtf:
        shutil.copy2(args.rtf, os.path.join(work_dir, os.path.basename(args.rtf)))
        print(f"[INTAKE] RTF -> work/    : {os.path.basename(args.rtf)}  (pipeline copy)")

    # cr_config.json — injected from CR profile, never edited in job folder
    shutil.copy2(cr_config_src, os.path.join(work_dir, 'cr_config.json'))
    print(f"[INTAKE] cr_config.json -> work/  (injected from CR profile  OK)")

    # CASE_CAPTION.json — engine-ready skeleton, fill all TODO values before running
    write_json(os.path.join(work_dir, 'CASE_CAPTION.json'), _caption_skeleton(args.cr_id, slug))
    print(f"[INTAKE] CASE_CAPTION.json skeleton -> work/  (fill TODO values before running)")

    # ── delivery/ — intentionally empty ──────────────────────────────────────
    # Future: automated copy of FINAL_DELIVERY/ contents after pipeline completes.

    # ── Done ─────────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  Job ID : {job_id}")
    print(f"  Folder : {job_dir}")
    print()
    print("  NEXT STEPS:")
    print(f"    1. Fill in work/CASE_CAPTION.json — replace all TODO values")
    print(f"       {os.path.join(work_dir, 'CASE_CAPTION.json')}")
    print()
    print(f"    2. Run pipeline:")
    run_cmd = os.path.join(ENGINE_DIR, 'run_pipeline.py')
    print(f"       python \"{run_cmd}\" --job-dir \"{work_dir}\"")
    print()
    print(f"    (Add --skip-ai if corrected_text.txt already exists and is good)")
    print("=" * 60)


if __name__ == '__main__':
    main()

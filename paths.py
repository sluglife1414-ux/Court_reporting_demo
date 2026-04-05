"""
paths.py — Data directory resolver for mb_demo_engine_v4.

Resolves DATA_DIR in this order:
  1. Explicit override (caller passes a path directly, e.g. --data-dir flag)
  2. DEPO_DATA_DIR environment variable
  3. Sibling 'data/' folder relative to the engine directory

Folder layout (data lives OUTSIDE the engine repo):

  parent/
    engine/mb_demo_engine_v4/    ← ENGINE_DIR (this file lives here)
    data/
      cr_profiles/
        dalotto_ny_001/
          CR_PROFILE.json
          cr_config.json         ← engine-specific config (formatter, modules)
          HOUSE_STYLE_MODULE.md
          KNOWLEDGE_BASE.txt
          fourman_wcb_20260324/  ← job folder, lives inside CR profile
            intake/              ← originals (read-only after receipt)
            work/                ← pipeline working dir (run_pipeline.py --job-dir here)
            delivery/            ← final output (future: copy from work/FINAL_DELIVERY/)
        muir_mb_001/
          ...same structure...
      state_modules/
        STATE_MODULE_ny_wcb.md
        STATE_MODULE_louisiana_engineering.md

Usage:
  from paths import get_data_dir, get_cr_profile_dir, get_job_dir, get_job_work_dir

  data_dir = get_data_dir()                                     # auto-resolve
  data_dir = get_data_dir('C:/depo_transformation/data')        # explicit override

  profile_dir = get_cr_profile_dir(data_dir, 'dalotto_ny_001')
  job_dir     = get_job_dir(data_dir, 'dalotto_ny_001', 'fourman_wcb_20260324')
  work_dir    = get_job_work_dir(data_dir, 'dalotto_ny_001', 'fourman_wcb_20260324')
"""
# ──────────────────────────────────────────────────────────────
# v1.1  2026-04-05  jobs live inside CR profile dir (not data/jobs/)
# v1.0  2026-04-05  initial
# ──────────────────────────────────────────────────────────────

import os

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

# Sibling 'data/' sits two levels up from the engine repo:
#   engine/mb_demo_engine_v4/ → engine/ → parent/ → data/
_SIBLING_DATA = os.path.normpath(os.path.join(_ENGINE_DIR, '..', '..', 'data'))


def get_data_dir(override=None):
    """
    Return the resolved, absolute DATA_DIR path.

    Resolution order:
      1. override argument  (explicit path from --data-dir flag)
      2. DEPO_DATA_DIR env  (set with: setx DEPO_DATA_DIR C:\\depo_transformation\\data)
      3. Sibling data/      (../data/ relative to engine repo parent)

    Raises FileNotFoundError if no candidate resolves to an existing directory.
    """
    candidates = [
        ('--data-dir flag',   override),
        ('DEPO_DATA_DIR env', os.environ.get('DEPO_DATA_DIR')),
        ('sibling data/',     _SIBLING_DATA),
    ]
    for label, path in candidates:
        if path and os.path.isdir(path):
            return os.path.abspath(path)

    tried = '\n'.join(f'    {label}: {path}' for label, path in candidates if path)
    raise FileNotFoundError(
        "DATA_DIR not found. Set DEPO_DATA_DIR or use --data-dir.\n"
        f"  Tried:\n{tried}\n\n"
        "  Quick fix (Windows): setx DEPO_DATA_DIR C:\\depo_transformation\\data"
    )


def get_cr_profiles_dir(data_dir):
    """Return path to cr_profiles/ under data_dir."""
    return os.path.join(data_dir, 'cr_profiles')


def get_cr_profile_dir(data_dir, cr_id):
    """Return path to a specific CR's profile directory."""
    return os.path.join(data_dir, 'cr_profiles', cr_id)


def get_job_dir(data_dir, cr_id, job_id):
    """
    Return path to a job's root folder.
    Jobs live INSIDE the CR profile directory.
    """
    return os.path.join(data_dir, 'cr_profiles', cr_id, job_id)


def get_job_work_dir(data_dir, cr_id, job_id):
    """
    Return path to a job's work/ subdirectory.
    This is the --job-dir value passed to run_pipeline.py.
    All pipeline intermediates (corrected_text.txt, FINAL_DELIVERY/) land here.
    """
    return os.path.join(data_dir, 'cr_profiles', cr_id, job_id, 'work')

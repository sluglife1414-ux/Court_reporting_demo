"""
config.py — Single source of truth for all pipeline scripts.
=============================================================
Import in every script:
    from config import cfg

Usage:
    cfg.case_short            → 'fourman_wcb_20260324'
    cfg.reporter_name         → 'ALICIA D\'ALOTTO'
    cfg.state                 → 'NY'
    cfg.review_filename       → 'fourman_wcb_20260324_CR_REVIEW.txt'
    cfg.get('field', default) → dict-style access (backward compat)

Fails loudly if CASE_CAPTION.json or cr_config.json is missing.
Run new_job.py to generate both files before running the pipeline.

Author:  Scott + Claude
Version: 1.0  (2026-04-04) — initial build, replaces per-script JSON loading
"""

import json
import os
import sys

_BASE = os.path.dirname(os.path.abspath(__file__))  # engine dir — scripts only
# Job data (CASE_CAPTION.json, cr_config.json, output files) live in CWD (job dir).
# _BASE is kept for any engine-level resources (state modules, etc.).


def _load_json(path, label):
    if not os.path.exists(path):
        print(f'[CONFIG ERROR] {label} not found: {path}')
        print('  Run: python new_job.py --cr <cr_id> --job <job_id>')
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


class _Config:
    """All pipeline config in one place. No hardcoded values."""

    def __init__(self):
        cap = _load_json('CASE_CAPTION.json', 'CASE_CAPTION.json')   # CWD = job dir

        # Normalize legacy field names so old CASE_CAPTION.json files work without edit
        # [TECH DEBT: remove once all job folders are migrated to current schema]
        if 'docket' not in cap and 'docket_number' in cap:
            cap['docket'] = cap['docket_number']
        if 'examining_atty' not in cap and 'examining_attorney' in cap:
            cap['examining_atty'] = cap['examining_attorney']
        if 'plaintiff' not in cap and 'case_name' in cap and ' v. ' in cap['case_name']:
            p, d = cap['case_name'].split(' v. ', 1)
            cap.setdefault('plaintiff', p.strip() + ',')
            cap.setdefault('defendant', d.strip() + ',')
        # cr_config.json: try CWD (job/work) first, then CR profile dir (../../)
        _cr_local    = 'cr_config.json'
        _cr_profile  = os.path.join('..', '..', 'cr_config.json')
        _cr_path     = _cr_local if os.path.exists(_cr_local) else _cr_profile
        cr  = _load_json(_cr_path, 'cr_config.json')

        # ── Case identity ──────────────────────────────────────────────────────
        self.case_short            = cap['case_short']
        self.state                 = cap.get('state', '')
        self.cr_id                 = cap.get('cr_id', cr.get('reporter_id', ''))

        # ── Witness ────────────────────────────────────────────────────────────
        self.witness_name          = cap.get('witness_name', '')
        self.witness_last          = cap.get('witness_last', '')
        self.witness_role          = cap.get('witness_role', '')
        self.depo_type             = cap.get('depo_type', 'DEPOSITION')
        self.depo_date             = cap.get('depo_date', '')
        self.depo_date_short       = cap.get('depo_date_short', '')
        self.depo_time             = cap.get('depo_time', '')

        # ── Reporter ───────────────────────────────────────────────────────────
        self.reporter_name         = cap.get('reporter_name', '')
        self.reporter_name_display = cap.get('reporter_name_display', self.reporter_name)
        self.reporter_title        = cap.get('reporter_title', '')
        self.reporter_credential_1 = cap.get('reporter_credential_1')
        self.reporter_credential_2 = cap.get('reporter_credential_2')
        self.reporter_address      = cap.get('reporter_address', '')
        self.reporter_phone        = cap.get('reporter_phone', '')
        self.reporter_license      = cap.get('reporter_license', '')

        # ── Attorneys ──────────────────────────────────────────────────────────
        self.examining_atty        = cap.get('examining_atty', '')
        self.appearances           = cap.get('appearances', [])
        self.zoom_attorneys        = cap.get('zoom_attorneys', [])
        self.exhibit_list          = cap.get('exhibit_list', [])

        # ── Louisiana-specific caption fields ──────────────────────────────────
        self.parish                = cap.get('parish', '')
        self.court                 = cap.get('court', '')
        self.plaintiff             = cap.get('plaintiff', '')
        self.plaintiff_role        = cap.get('plaintiff_role', 'Plaintiff,')
        self.defendant             = cap.get('defendant', '')
        self.defendant_role        = cap.get('defendant_role', 'Defendant.')
        self.docket                = cap.get('docket', '')
        self.division              = cap.get('division', '')
        self.venue_name            = cap.get('venue_name', '')
        self.location_1            = cap.get('location_1', '')
        self.location_2            = cap.get('location_2', '')
        self.cert_year             = cap.get('cert_year',
                                        str(__import__('datetime').date.today().year))

        # ── NY WCB-specific caption fields ─────────────────────────────────────
        self.wcb_case_no           = cap.get('wcb_case_no', '')
        self.carrier_case_no       = cap.get('carrier_case_no', '')
        self.date_of_accident      = cap.get('date_of_accident', '')
        self.claimant              = cap.get('claimant', '')
        self.claimant_role         = cap.get('claimant_role', 'Claimant,')
        self.employer              = cap.get('employer', '')
        self.employer_role         = cap.get('employer_role', 'Employer.')

        # ── CR profile fields (from cr_config.json) ────────────────────────────
        self.reporter_id           = cr.get('reporter_id', self.cr_id)
        self.state_label           = cr.get('state_label', self.state)
        self.job_id                = cr.get('job_id', self.case_short)
        self.modules               = cr.get('modules', {})

        # ── Derived ────────────────────────────────────────────────────────────
        self.delivery_dir          = 'FINAL_DELIVERY'
        self.review_filename       = f'{self.case_short}_CR_REVIEW.txt'
        self.review_path           = os.path.join(
                                        'FINAL_DELIVERY', self.review_filename)  # CWD = job dir

    def get(self, key, default=None):
        """dict-style get for backward compatibility during migration."""
        return getattr(self, key, default)

    def __getitem__(self, key):
        """dict-style [] access for backward compatibility during migration."""
        val = getattr(self, key, None)
        if val is None:
            raise KeyError(key)
        return val


cfg = _Config()

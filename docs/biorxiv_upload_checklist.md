# bioRxiv Upload Checklist

## Core Submission Files

- Manuscript draft:
  - `docs/biorxiv_manuscript_submission_ready.md`
- Figure caption:
  - `docs/biorxiv_figure_caption_submission_ready.md`
- Main figure:
  - `docs/figures/biorxiv_revision_timeline_camera_ready.svg`
- Main validation table:
  - `runs/biorxiv_external_validation_main_table_current.md`
- Supplementary task table:
  - `runs/biorxiv_external_validation_supplementary_task_table_current.md`

## Reviewer-Facing Validation Artifacts

- Current reviewer package:
  - `runs/biorxiv_external_validation_package_current.zip`
- Reviewer index:
  - `runs/biorxiv_external_validation_reviewer_index_current.html`
- Current audit:
  - `runs/biorxiv_external_validation_audit_current.json`
- Claim matrix:
  - `runs/biorxiv_external_validation_claim_matrix_current.md`

## Current Acceptance State

- Promoted current run:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1`
- Primary claim status:
  - `set1_core_blind = PASS`
- Secondary generalization status:
  - `set2_expanded_ood = PASS`
- Reproducibility-support status:
  - `set3_operational_smoke = PASS`
- Package audit:
  - `pass = true`
  - `failure_count = 0`

## Claim-Scope Sanity Check

- Manuscript should describe the package as:
  - a preregistered, audited, cross-domain computational validation package
- Manuscript should not describe the package as:
  - an experimentally validated screening platform
  - a prospective wet-lab hit-discovery result
  - a clinically validated discovery system
- Scope note:
  - `docs/biorxiv_claim_scope_note.md`

## Temporal-Scaffold Sanity Check

- Temporal baseline:
  - `runs/biorxiv_temporal_submission_baseline_current.md`
- Current counts:
  - `202/206 item-ready`
  - `4/206 dataset-ready`
- Remaining-policy report:
  - `runs/biorxiv_temporal_idp_remaining_policy_current.md`
- The manuscript should keep temporal claims provisional and mixed item-level/dataset-level.

## Pre-Upload Final Checks

- Rebuild submission assets:
  - `python3 tools/build_biorxiv_submission_assets.py`
- Confirm bundle exists:
  - `runs/biorxiv_submission_assets_current.zip`
- Confirm audit still passes:
  - `runs/biorxiv_external_validation_audit_current.json`
- Confirm current manuscript references:
  - `2026-03-22_biorxiv_v7r1`
  - `2026-03-22_biorxiv_v6r3` as the first all-pass corrective close-out

## Recommended Upload Bundle

- Upload-ready asset bundle:
  - `runs/biorxiv_submission_assets_current.zip`
- If reviewers need the full executable validation bundle, include:
  - `runs/biorxiv_external_validation_package_current.zip`

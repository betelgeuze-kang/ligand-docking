# bioRxiv Submission Summary

## Manuscript

- Title:
  - `Preregistered Cross-Domain Blind Validation of a Unified Molecular Architecture`
- Main draft:
  - `docs/biorxiv_manuscript_submission_ready.md`
- Author metadata template:
  - `docs/biorxiv_author_metadata_template.md`

## Central Claim

- The accepted `v7r1` package supports a preregistered cross-domain computational validation claim across GPCR, ion-channel, kinase/protease, and IDP tasks.
- The package is audited and reviewer-facing.
- The package is not claimed as a prospective wet-lab hit-discovery or experimentally validated screening platform.

## Current Accepted Validation State

- Current promoted run:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1`
- Robustness battery:
  - `runs/biorxiv_robustness_comparison_summary_current.md`
  - completed scenarios: `embed_seed_shift1`, `decoy_seed_shift1`, `decoy_pressure_12k`
  - all preregistered sets preserved, `0` pass-to-fail transitions
- First all-pass corrective close-out:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v6r3`
- Current package audit:
  - `runs/biorxiv_external_validation_audit_current.json`
  - `pass = true`
  - `failure_count = 0`

## Claim Layers

- `set1_core_blind`
  - `PASS`
- `set2_expanded_ood`
  - `PASS`
- `set3_operational_smoke`
  - `PASS`

## Domain Coverage

- GPCR
  - blind/core: `PASS`
  - expanded OOD: `PASS`
  - smoke: `PASS`
- Ion channel (`TRPV1`)
  - blind/core: `PASS`
  - expanded OOD: `PASS`
  - smoke: `PASS`
- Kinase/protease
  - blind/core: `PASS`
  - expanded OOD: `PASS`
  - smoke: `PASS`
- IDP
  - current release reference: `PASS`
  - smoke reference: `PASS`

## Temporal Scaffold

- Current temporal baseline:
  - `runs/biorxiv_temporal_submission_baseline_current.md`
- Current readiness:
  - `202/206 item-ready`
  - `4/206 dataset-ready`
- Current interpretation:
  - conservative mixed item-level and dataset-level scaffold
  - not yet a completed future-only temporal split benchmark
- Remaining dataset-level rows are policy-coded:
  - `no_public_anchor_found`
  - `fragment_anchor_missing`
  - `intentional_dataset_control`

## Key Submission Files

- Main figure:
  - `docs/figures/biorxiv_revision_timeline_camera_ready.svg`
- Main validation table:
  - `runs/biorxiv_external_validation_main_table_current.md`
- Supplementary task table:
  - `runs/biorxiv_external_validation_supplementary_task_table_current.md`
- Claim-scope note:
  - `docs/biorxiv_claim_scope_note.md`
- Upload checklist:
  - `docs/biorxiv_upload_checklist.md`

## Recommended Bundles

- Submission-assets bundle:
  - `runs/biorxiv_submission_assets_current.zip`
- Full reviewer-facing validation bundle:
  - `runs/biorxiv_external_validation_package_current.zip`

## Remaining Manual Entry Fields

- ORCID `[optional]`
- final bioRxiv category and keyword choices

# bioRxiv Temporal Validation Plan

## Goal

Add a reviewer-facing temporal split that is stricter than the current cross-domain blind/OOD package while remaining fully computational.

## Proposed Rule

- define a protocol freeze date per domain
- allow only reference items with public provenance dates at or before the freeze date into fit/calibration
- reserve post-freeze items for blinded evaluation
- keep labels hidden from model-selection steps until the prediction package is sealed

## Domain Requirements

### GPCR / Ion Channel / Kinase

Need per-ligand public provenance fields such as:
- ChEMBL first-publication year or release stamp
- curated dataset release date
- assay publication date when available

### IDP

Need per-holdout provenance fields such as:
- experimental publication year
- benchmark inclusion date
- freeze date for corrected labels

## Deliverables

- temporal spec JSON derived from the template below
- runnable provisional temporal spec using dataset-level freeze governance
- one-shot temporal runner wrapper
- sealed prediction package
- temporal comparison table versus promoted `v7r1`
- manuscript supplement table for post-freeze generalization

## Current Status

- runnable provisional spec created:
  - `config/external_validation_biorxiv_temporal_sets_v1_provisional.json`
- launch wrapper created:
  - `tools/run_biorxiv_temporal_validation_current.py`
- editable provenance mapping templates created:
  - `config/biorxiv_temporal_ligand_provenance_v1.csv`
  - `config/biorxiv_temporal_idp_provenance_v1.csv`
- provenance mapping coverage checker created:
  - `tools/check_biorxiv_temporal_provenance_maps.py`
- current mapping coverage summary:
  - `runs/biorxiv_temporal_provenance_mapping_coverage_current.md`
- current curation-priority summary:
  - `runs/biorxiv_temporal_curation_priority_current.md`
- source-normalization table:
  - `config/biorxiv_temporal_source_normalization_v1.csv`
- local release-facts table:
  - `config/biorxiv_temporal_local_release_facts_v1.csv`
- local release-facts apply summary:
  - `runs/biorxiv_temporal_local_release_facts_apply_current.md`
- IDP local release-facts table:
  - `config/biorxiv_temporal_idp_local_release_facts_v1.csv`
- IDP local release-facts apply summary:
  - `runs/biorxiv_temporal_idp_local_release_facts_apply_current.md`
- source-pool sanity check:
  - `runs/biorxiv_temporal_source_pool_sanity_check_current.md`
- family-specific helper bundle:
  - `runs/biorxiv_temporal_family_helpers_current/`
- provenance inventory created:
  - `runs/biorxiv_temporal_provenance_inventory_current.md`
  - `runs/biorxiv_temporal_provenance_inventory_current.csv`
- IDP item-level helper and explicit-year facts created:
  - `runs/biorxiv_temporal_idp_item_helpers_current.md`
  - `runs/biorxiv_temporal_idp_item_provenance_facts_current.md`
  - `runs/biorxiv_temporal_idp_item_provenance_apply_current.md`
- IDP unresolved-row manual curation bundle created:
  - `runs/biorxiv_temporal_idp_manual_curation_current/`
- two ligand source families now have dataset-level local release anchors:
  - `literature_proxy_v2`
  - `gpcr_blind_proxy_v1`
  - `chembl_blind_adrb2_v1`
  - `disjoint_proxy_v2`
- all current ligand provenance rows are now also `item_ready`
- the current IDP provenance map is mixed:
  - `16/20` IDP rows are now `item_ready`
  - this includes the full `pdb` subset, `alpha_synuclein_full`, and a curated synthetic subset with construct-level literature anchors
  - the remaining `4/20` IDP rows remain `dataset_ready`
- the remaining item-level temporal gap is therefore confined to the unresolved synthetic IDP holdouts
- those remaining rows should still be treated as dataset-level temporal scaffolding rather than item-level publication evidence
- `prion_like_polyq_control` is intentionally retained as a dataset-level synthetic control until a construct-matched public disorder anchor is identified
- the other unresolved synthetic rows reflect conservative no-promotion decisions after the current public-anchor sweep rather than missing dataset-level release provenance
- current recommendation:
  - treat the provisional temporal spec as a mixed scaffold: ligand rows now support item-level temporal claims, and IDP currently mixes `16` item-level rows with `4` dataset-level anchors
  - use `runs/biorxiv_temporal_idp_manual_curation_current/` as the next per-holdout curation workspace before making full item-level temporal claims for the remaining unresolved synthetic IDP holdouts

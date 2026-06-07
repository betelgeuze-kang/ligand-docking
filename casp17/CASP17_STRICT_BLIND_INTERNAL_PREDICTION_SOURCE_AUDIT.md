# CASP17 Strict-Blind Internal Prediction Source Audit

- generated: `2026-06-01T02:29:23+09:00`
- status: `internal_prediction_source_missing_for_first_slot`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- first open field/status: `prediction_pdb` `open_missing_file`
- local candidates eligible/total/prediction-present: `0/17/15`
- source routes allowed/total: `0/17`
- official baseline ready/strict-blocked/total: `24/24/24`
- bridge native/internal-blocked/operator-only: `2/1/6`
- allowed internal sources: `0`
- manifest template: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- first blocker: `pre_native_internal_prediction_pdb_missing`

## Source Audit

| source | class | status | ready/blocked/total | allowed | proof use | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `required_prediction_dropzone` | `first_slot_evidence` | `missing_internal_prediction_pdb` | `0/1/1` | `false` | required_internal_prediction_evidence | `place prediction_pdb evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` |
| `local_candidate_inventory` | `local_internal_candidates` | `no_local_strict_blind_prediction_candidates` | `0/17/17` | `false` | internal_candidate_review_only_until_operator_clearance | `casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json` |
| `first_slot_source_route` | `route_decision` | `first_slot_requires_pre_native_monomer_source_or_replacement` | `0/17/17` | `false` | route_gate_for_internal_prediction_source | `casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json` |
| `official_archive_prediction_tarballs` | `external_baseline` | `blocked_external_other_team_baseline_only` | `24/24/24` | `false` | baseline_only_not_internal_competitive_proof | `casp17/casp17_historical_seed_official_archive_baseline_lane_current.json` |
| `native_authority_source_bridge` | `native_authority_bridge` | `first_slot_source_bridge_internal_prediction_required` | `2/7/9` | `false` | native_authority_preview_only_until_internal_prediction_supplied | `casp17/casp17_strict_blind_first_slot_source_bridge_current.json` |
| `operator_internal_source_manifest` | `operator_template` | `ready_for_operator_internal_source_entry` | `1/0/1` | `false` | template_only_not_evidence | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` |

Local CASP17 strict-blind internal prediction source audit only. It audits whether the first historical strict-blind slot has a pre-native internal prediction source and writes an operator manifest template. It does not create prediction PDBs, download official archive tarballs, reclassify external models as internal proof, approve no-leak provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP.

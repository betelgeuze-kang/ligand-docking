# CASP17 Strict-Blind First Unlock Handoff

- generated: `2026-06-01T21:00:10+09:00`
- status: `awaiting_first_unlock_operator_values`
- benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- source request: `source_request_001` `HIST_BBA5` rank `1`
- fields ready/blocked/total: `0/11/11`
- current chronology blocker: `prediction_not_before_native` prediction/native `2026-02-19` / `2004-05-13`
- first blocked field: `source_id` `operator_value_missing`
- next action: fill operator_value for source_id
- operator template: `casp17/strict_blind_source_gate_source_request_packet/source_request_001/operator_source_values_template.csv`
- source manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- prediction dropzone: `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb`

## Fields

| order | field | status | blocker | destination | next action |
| ---: | --- | --- | --- | --- | --- |
| 1 | `source_id` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for source_id |
| 2 | `prediction_pdb` | `awaiting_operator_value` | `operator_value_missing` | `-` | fill operator_value for prediction_pdb |
| 3 | `prediction_pdb_dropzone` | `awaiting_file_copy` | `operator_value_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | fill operator_value for prediction_pdb_dropzone |
| 4 | `prediction_created_at` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for prediction_created_at |
| 5 | `native_release_date` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for native_release_date |
| 6 | `prediction_created_at/native_release_date` | `awaiting_derived_date_order` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for prediction_created_at/native_release_date |
| 7 | `native_authority_ref` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for native_authority_ref |
| 8 | `creation_evidence_ref` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for creation_evidence_ref |
| 9 | `no_leak_evidence_ref` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for no_leak_evidence_ref |
| 10 | `method_summary` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for method_summary |
| 11 | `operator_clearance` | `awaiting_operator_value` | `operator_value_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | fill operator_value for operator_clearance |

## Claim Boundary

Local CASP17 strict-blind first-unlock handoff only. It consolidates the first source-request operator fields needed before the first historical strict-blind slot can pass the internal prediction source gate. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

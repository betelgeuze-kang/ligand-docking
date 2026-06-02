# CASP17 Batch Native/Provenance Value Actions: H1319

- target: `H1319` `Human astrovirus VA1 capsid spike - antibody 7C8 complex`
- open actions: `12`
- first blocker: `native_source_pdb_required`
- intake CSV: `casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv`

## Actions

| rank | field | group | blocker | next action |
| ---: | --- | --- | --- | --- |
| `1` | `native_source_pdb` | `native_file` | `native_source_pdb_required` | Fill native_source_pdb in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with local protein PDB path distinct from prediction, then rerun the value gate. |
| `2` | `no_leak_evidence_ref` | `evidence` | `no_leak_evidence_ref_required` | Fill no_leak_evidence_ref in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with local no-leak evidence file, then rerun the value gate. |
| `3` | `leakage_clearance` | `clearance` | `leakage_clearance_required` | Fill leakage_clearance in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with cleared/no_leak style clearance value, then rerun the value gate. |
| `4` | `operator_clearance` | `clearance` | `operator_clearance_required` | Fill operator_clearance in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with operator-cleared value, then rerun the value gate. |
| `5` | `operator` | `operator` | `operator_required` | Fill operator in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with operator id, then rerun the value gate. |
| `6` | `prediction_created_at` | `date` | `prediction_created_at_required_iso_date` | Fill prediction_created_at in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with ISO date before native release, then rerun the value gate. |
| `7` | `native_release_date` | `date` | `native_release_date_required_iso_date` | Fill native_release_date in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with ISO native release date, then rerun the value gate. |
| `8` | `prediction_generated_before_native_release` | `boolean` | `prediction_generated_before_native_release_required` | Fill prediction_generated_before_native_release in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with true confirmation, then rerun the value gate. |
| `9` | `public_template_or_native_used_for_prediction` | `boolean` | `public_template_or_native_used_for_prediction_must_be_false` | Fill public_template_or_native_used_for_prediction in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with false confirmation, then rerun the value gate. |
| `10` | `other_team_model_used` | `boolean` | `other_team_model_used_must_be_false` | Fill other_team_model_used in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with false confirmation, then rerun the value gate. |
| `11` | `post_release_information_used` | `boolean` | `post_release_information_used_must_be_false` | Fill post_release_information_used in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with false confirmation, then rerun the value gate. |
| `12` | `current_casp17_target` | `boolean` | `current_casp17_target_must_be_false` | Fill current_casp17_target in casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv with false confirmation, then rerun the value gate. |

## Claim Boundary

CASP17 competitive-floor batch native/provenance value action board only. It expands the dry value gate into field-level operator actions and target-named folders. It does not fill values, fetch native structures, copy coordinate files, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP.

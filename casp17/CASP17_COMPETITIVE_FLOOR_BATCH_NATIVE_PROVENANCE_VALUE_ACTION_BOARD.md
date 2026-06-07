# CASP17 Competitive Floor Batch Native/Provenance Value Action Board

- generated: `2026-06-02T06:46:27+09:00`
- status: `casp17_competitive_floor_batch_native_provenance_value_action_board_open_actions`
- targets open/ready/total: `3/0/3`
- actions open/total: `36/36`
- lanes native/evidence/clearance/operator/date/boolean/review: `3/3/6/3/6/15/0`
- coordinate copies: `0`
- proof/author: `0/0`
- first open: `H1319` `native_source_pdb` `native_source_pdb_required`
- out dir: `casp17/competitive_floor_batch_native_provenance_value_action_board`

## Actions

| rank | target | field | group | blocker |
| ---: | --- | --- | --- | --- |
| `1` | `H1319` | `native_source_pdb` | `native_file` | `native_source_pdb_required` |
| `2` | `H1319` | `no_leak_evidence_ref` | `evidence` | `no_leak_evidence_ref_required` |
| `3` | `H1319` | `leakage_clearance` | `clearance` | `leakage_clearance_required` |
| `4` | `H1319` | `operator_clearance` | `clearance` | `operator_clearance_required` |
| `5` | `H1319` | `operator` | `operator` | `operator_required` |
| `6` | `H1319` | `prediction_created_at` | `date` | `prediction_created_at_required_iso_date` |
| `7` | `H1319` | `native_release_date` | `date` | `native_release_date_required_iso_date` |
| `8` | `H1319` | `prediction_generated_before_native_release` | `boolean` | `prediction_generated_before_native_release_required` |
| `9` | `H1319` | `public_template_or_native_used_for_prediction` | `boolean` | `public_template_or_native_used_for_prediction_must_be_false` |
| `10` | `H1319` | `other_team_model_used` | `boolean` | `other_team_model_used_must_be_false` |
| `11` | `H1319` | `post_release_information_used` | `boolean` | `post_release_information_used_must_be_false` |
| `12` | `H1319` | `current_casp17_target` | `boolean` | `current_casp17_target_must_be_false` |
| `13` | `H1321` | `native_source_pdb` | `native_file` | `native_source_pdb_required` |
| `14` | `H1321` | `no_leak_evidence_ref` | `evidence` | `no_leak_evidence_ref_required` |
| `15` | `H1321` | `leakage_clearance` | `clearance` | `leakage_clearance_required` |
| `16` | `H1321` | `operator_clearance` | `clearance` | `operator_clearance_required` |
| `17` | `H1321` | `operator` | `operator` | `operator_required` |
| `18` | `H1321` | `prediction_created_at` | `date` | `prediction_created_at_required_iso_date` |
| `19` | `H1321` | `native_release_date` | `date` | `native_release_date_required_iso_date` |
| `20` | `H1321` | `prediction_generated_before_native_release` | `boolean` | `prediction_generated_before_native_release_required` |
| `21` | `H1321` | `public_template_or_native_used_for_prediction` | `boolean` | `public_template_or_native_used_for_prediction_must_be_false` |
| `22` | `H1321` | `other_team_model_used` | `boolean` | `other_team_model_used_must_be_false` |
| `23` | `H1321` | `post_release_information_used` | `boolean` | `post_release_information_used_must_be_false` |
| `24` | `H1321` | `current_casp17_target` | `boolean` | `current_casp17_target_must_be_false` |
| `25` | `H2324` | `native_source_pdb` | `native_file` | `native_source_pdb_required` |
| `26` | `H2324` | `no_leak_evidence_ref` | `evidence` | `no_leak_evidence_ref_required` |
| `27` | `H2324` | `leakage_clearance` | `clearance` | `leakage_clearance_required` |
| `28` | `H2324` | `operator_clearance` | `clearance` | `operator_clearance_required` |
| `29` | `H2324` | `operator` | `operator` | `operator_required` |
| `30` | `H2324` | `prediction_created_at` | `date` | `prediction_created_at_required_iso_date` |
| `31` | `H2324` | `native_release_date` | `date` | `native_release_date_required_iso_date` |
| `32` | `H2324` | `prediction_generated_before_native_release` | `boolean` | `prediction_generated_before_native_release_required` |
| `33` | `H2324` | `public_template_or_native_used_for_prediction` | `boolean` | `public_template_or_native_used_for_prediction_must_be_false` |
| `34` | `H2324` | `other_team_model_used` | `boolean` | `other_team_model_used_must_be_false` |
| `35` | `H2324` | `post_release_information_used` | `boolean` | `post_release_information_used_must_be_false` |
| `36` | `H2324` | `current_casp17_target` | `boolean` | `current_casp17_target_must_be_false` |

## Claim Boundary

CASP17 competitive-floor batch native/provenance value action board only. It expands the dry value gate into field-level operator actions and target-named folders. It does not fill values, fetch native structures, copy coordinate files, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP.

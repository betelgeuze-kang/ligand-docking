# CASP17 Competitive Floor Batch Native/Provenance Value Gate

- generated: `2026-06-02T06:35:40+09:00`
- status: `casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values`
- targets ready/blocked/total: `0/3/3`
- fields per-target/total: `13/39`
- values ready/blocked: `3/36`
- native/evidence ready: `0/0`
- clearance/date/boolean ready: `0/0/0`
- coordinate copies batch/target: `0/0`
- proof/author: `0/0`
- first blocked: `H1319` `native_source_pdb_required`
- batch intake: `casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv`

## Targets

| target | status | values | native | evidence | clearance | date | boolean | blockers |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- |
| `H1319` | `blocked_awaiting_operator_values` | `1/12` | `blocked` | `blocked` | `0/2` | `0/2` | `0/5` | `native_source_pdb_required,no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` |
| `H1321` | `blocked_awaiting_operator_values` | `1/12` | `blocked` | `blocked` | `0/2` | `0/2` | `0/5` | `native_source_pdb_required,no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` |
| `H2324` | `blocked_awaiting_operator_values` | `1/12` | `blocked` | `blocked` | `0/2` | `0/2` | `0/5` | `native_source_pdb_required,no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` |

## Claim Boundary

CASP17 competitive-floor batch native/provenance value gate only. It dry-validates operator-filled batch native PDB paths, no-leak evidence files, provenance dates, and true/false controls against the same local rules as target identity operator intake. It does not apply values, copy coordinates, fetch native structures, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP.

# CASP17 Competitive-Floor Target Identity Clearance Workorder Audit

- generated: `2026-05-26T01:58:49+09:00`
- clearance_workorder_audit_status: `blocked`
- clearance_workorder_status: `awaiting_native_or_provenance`
- audit pass/blocked/total: `0/3/3`
- prediction/native/provenance/manifest ready: `3/0/0/0`
- first blocked: `H1319` `blocked`
- next action: place the cleared native PDB in the per-target native dropzone

## Audit Rows

| target | audit | native | atoms | provenance | manifest | prediction | blockers | next action |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `H1319` | `blocked` | `missing` | 0 | `blocked` | `blocked` | `present` | `native_pdb_missing,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` | place the cleared native PDB in the per-target native dropzone |
| `H1321` | `blocked` | `missing` | 0 | `blocked` | `blocked` | `present` | `native_pdb_missing,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` | place the cleared native PDB in the per-target native dropzone |
| `H2324` | `blocked` | `missing` | 0 | `blocked` | `blocked` | `present` | `native_pdb_missing,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` | place the cleared native PDB in the per-target native dropzone |

## Claim Boundary

Local competitive-floor target identity clearance workorder audit only. It verifies per-target native dropzones, provenance templates, and manifest stubs before any manual promotion. It does not fetch native structures, clear no-leak provenance, choose historical targets, score native accuracy, mutate identity intake files, or submit to CASP.

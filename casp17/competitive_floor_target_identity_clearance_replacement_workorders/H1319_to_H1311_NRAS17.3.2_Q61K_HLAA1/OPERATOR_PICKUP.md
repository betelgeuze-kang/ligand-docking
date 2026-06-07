# H1319 -> H1311 Replacement Pickup

- pickup_status: `awaiting_operator_pickup`
- next_action: place the cleared native PDB in the native dropzone
- native_dropzone_pdb: `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/native/H1311_native.pdb`
- provenance_template_csv: `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/provenance_template.csv`
- manifest_stub_csv: `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/manifest_stub.csv`
- prediction_pdb: `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb`
- audit_status: `blocked`
- native/provenance/manifest: `missing/blocked/blocked`
- required provenance fields: `leakage_clearance,prediction_created_at,native_release_date,prediction_generated_before_native_release,public_template_or_native_used_for_prediction,other_team_model_used,post_release_information_used,current_casp17_target,operator_clearance,operator,evidence_ref`
- blockers: `native_pdb_missing,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template`

## Operator Sequence

1. Place only an operator-cleared native PDB at the native dropzone path.
2. Fill every required provenance field with no-leak evidence and operator clearance.
3. Rerun the replacement workorder audit before any promotion or intake sync.

## Claim Boundary

Local CASP17 replacement clearance pickup packet only. It consolidates already-materialized replacement workorders, native dropzones, provenance templates, manifest stubs, and audit blockers for operator execution. It does not fetch native structures, clear no-leak provenance, choose final targets, score native accuracy, mutate live intake files, or submit to CASP.

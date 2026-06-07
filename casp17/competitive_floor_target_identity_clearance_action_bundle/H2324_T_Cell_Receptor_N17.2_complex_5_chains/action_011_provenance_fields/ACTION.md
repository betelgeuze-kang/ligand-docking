# H2324 provenance_fields Action

- action_rank: `11`
- action_status: `open`
- required_artifact: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv`
- required_field: `provenance_template_required_fields`
- blockers: `operator_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false`
- recommended_action: Fill no-leak/operator clearance, prediction/native dates, and all true/false provenance confirmations in the provenance template.
- unlocks: `provenance_ready_count,manifest_sync_ready_to_sync_count`
- verification_command: `python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py`
- request_md: `casp17/competitive_floor_target_identity_clearance_action_bundle/H2324_T_Cell_Receptor_N17.2_complex_5_chains/action_011_provenance_fields/provenance_fill_request.md`

## Claim Boundary

Local CASP17 competitive-floor target identity clearance action bundle only. It materializes action-board rows into per-target operator request folders. Request files are templates and are intentionally not clearance evidence. It does not fetch native structures, fill provenance, clear no-leak review, mutate workorders, mutate identity intake files, score native accuracy, or submit to CASP.

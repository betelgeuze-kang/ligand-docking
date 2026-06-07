# H1319 manifest_stub_sync Action

- action_rank: `4`
- action_status: `open`
- required_artifact: `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/manifest_stub.csv`
- required_field: `manifest_stub_fields`
- blockers: `manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required`
- recommended_action: After provenance is ready, sync the cleared provenance fields into the manifest stub and rerun the clearance cycle.
- unlocks: `manifest_stub_ready_count,manifest_provenance_matched_count,promotion_plan`
- verification_command: `python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py`
- request_md: `casp17/competitive_floor_target_identity_clearance_action_bundle/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/action_004_manifest_stub_sync/manifest_sync_request.md`

## Claim Boundary

Local CASP17 competitive-floor target identity clearance action bundle only. It materializes action-board rows into per-target operator request folders. Request files are templates and are intentionally not clearance evidence. It does not fetch native structures, fill provenance, clear no-leak review, mutate workorders, mutate identity intake files, score native accuracy, or submit to CASP.

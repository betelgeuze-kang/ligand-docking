# H1319 native_dropzone Action

- action_rank: `1`
- action_status: `open`
- required_artifact: `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/native/H1319_native.pdb`
- required_field: `native_pdb`
- blockers: `native_pdb_missing,manifest_native_pdb_not_found`
- recommended_action: Place an operator-cleared native protein PDB in the native dropzone; ensure it is distinct from the prediction and has valid ATOM coordinates.
- unlocks: `native_valid_count,native_prediction_distinct_count,manifest_native_pdb`
- verification_command: `python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py`
- request_md: `casp17/competitive_floor_target_identity_clearance_action_bundle/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/action_001_native_dropzone/native_dropzone_request.md`

## Claim Boundary

Local CASP17 competitive-floor target identity clearance action bundle only. It materializes action-board rows into per-target operator request folders. Request files are templates and are intentionally not clearance evidence. It does not fetch native structures, fill provenance, clear no-leak review, mutate workorders, mutate identity intake files, score native accuracy, or submit to CASP.

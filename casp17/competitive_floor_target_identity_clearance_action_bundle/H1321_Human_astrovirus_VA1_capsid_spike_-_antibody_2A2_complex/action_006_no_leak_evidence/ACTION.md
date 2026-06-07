# H1321 no_leak_evidence Action

- action_rank: `6`
- action_status: `open`
- required_artifact: `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/provenance_template.csv`
- required_field: `evidence_ref`
- blockers: `evidence_ref_required,identity_discovery_no_leak_clearance_required`
- recommended_action: Create a local evidence file that names the target and no-leak review, then write that path into the provenance template evidence_ref field.
- unlocks: `evidence_ref_verified_count,identity_discovery_cleared_count`
- verification_command: `python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py`
- request_md: `casp17/competitive_floor_target_identity_clearance_action_bundle/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/action_006_no_leak_evidence/evidence_request.md`

## Claim Boundary

Local CASP17 competitive-floor target identity clearance action bundle only. It materializes action-board rows into per-target operator request folders. Request files are templates and are intentionally not clearance evidence. It does not fetch native structures, fill provenance, clear no-leak review, mutate workorders, mutate identity intake files, score native accuracy, or submit to CASP.

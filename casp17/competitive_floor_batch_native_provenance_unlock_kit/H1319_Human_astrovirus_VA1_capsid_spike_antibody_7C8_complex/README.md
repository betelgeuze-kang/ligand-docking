# CASP17 Batch Native/Provenance Unlock Target Kit: H1319

- status: `casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill`
- target: `H1319` `Human astrovirus VA1 capsid spike - antibody 7C8 complex`
- fields/actions/bundle: `13/4/4`
- packet/workorder/runway: `true`/`false`/`false`
- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `1/1/1/0/1/1/1/1`
- provenance/evidence/identity: `false`/`false`/`false`
- proof/author: `false`/`false`
- first blocker: `native_pdb_missing`

## Operator Files

- fill intake row: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/operator_fill_intake.csv`
- required actions: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/required_actions.csv`
- rerun commands: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/rerun_commands.md`
- manifest: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/kit_manifest.json`

## Source Links

- native dropzone: `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/native/H1319_native.pdb`
- provenance template: `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/provenance_template.csv`
- manifest stub: `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/manifest_stub.csv`
- packet folder: `casp17/competitive_floor_native_provenance_operator_packet/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex`
- metric runway: `casp17/competitive_floor_target_identity_metric_runway/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/METRIC_RUNWAY.md`

## Claim Boundary

CASP17 competitive-floor batch native/provenance unlock operator kit only. It collects all blocked native/provenance target packets into one operator-fill workspace with per-target folders, a batch intake CSV, action matrix, and rerun commands. It does not fetch native structures, copy coordinates, fill or trust provenance, clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP.

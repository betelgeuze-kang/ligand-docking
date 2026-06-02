# CASP17 Batch Native/Provenance Unlock Target Kit: H2324

- status: `casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill`
- target: `H2324` `T Cell Receptor N17.2, complex (5 chains)`
- fields/actions/bundle: `13/4/4`
- packet/workorder/runway: `true`/`false`/`false`
- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `1/1/1/0/1/1/1/1`
- provenance/evidence/identity: `false`/`false`/`false`
- proof/author: `false`/`false`
- first blocker: `native_pdb_missing`

## Operator Files

- fill intake row: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H2324_T_Cell_Receptor_N17_2_complex_5_chains/operator_fill_intake.csv`
- required actions: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H2324_T_Cell_Receptor_N17_2_complex_5_chains/required_actions.csv`
- rerun commands: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H2324_T_Cell_Receptor_N17_2_complex_5_chains/rerun_commands.md`
- manifest: `casp17/competitive_floor_batch_native_provenance_unlock_kit/H2324_T_Cell_Receptor_N17_2_complex_5_chains/kit_manifest.json`

## Source Links

- native dropzone: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/native/H2324_native.pdb`
- provenance template: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv`
- manifest stub: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/manifest_stub.csv`
- packet folder: `casp17/competitive_floor_native_provenance_operator_packet/H2324_T_Cell_Receptor_N17_2_complex_5_chains`
- metric runway: `casp17/competitive_floor_target_identity_metric_runway/H2324_T_Cell_Receptor_N17_2_complex_5_chains/METRIC_RUNWAY.md`

## Claim Boundary

CASP17 competitive-floor batch native/provenance unlock operator kit only. It collects all blocked native/provenance target packets into one operator-fill workspace with per-target folders, a batch intake CSV, action matrix, and rerun commands. It does not fetch native structures, copy coordinates, fill or trust provenance, clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP.

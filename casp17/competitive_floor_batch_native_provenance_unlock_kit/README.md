# CASP17 Batch Native/Provenance Unlock Kit

- status: `casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill`
- targets ready/blocked/total: `3/0/3`
- target ids: `H1319,H1321,H2324`
- fields per-target/total: `13/39`
- actions required/bundle: `12/12`
- packet/workorder/runway ready: `3/0/0`
- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `3/3/3/0/3/3/3/3`
- provenance/evidence/identity: `0/0/0`
- proof/author: `0/0`

## Operator Files

- fill intake batch: `casp17/competitive_floor_batch_native_provenance_unlock_kit/operator_fill_intake_batch.csv`
- required actions batch: `casp17/competitive_floor_batch_native_provenance_unlock_kit/required_actions_batch.csv`
- rerun commands: `casp17/competitive_floor_batch_native_provenance_unlock_kit/rerun_commands.md`
- manifest: `casp17/competitive_floor_batch_native_provenance_unlock_kit/batch_manifest.json`

## Claim Boundary

CASP17 competitive-floor batch native/provenance unlock operator kit only. It collects all blocked native/provenance target packets into one operator-fill workspace with per-target folders, a batch intake CSV, action matrix, and rerun commands. It does not fetch native structures, copy coordinates, fill or trust provenance, clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP.

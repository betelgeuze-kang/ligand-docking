# T1331_5AT Coordinate Materialization Plan

- object_count: `1`
- ready/blocked: `1/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/T1331_5AT/objects/chain_A/models/T1331_chain_A.pdb` | `casp17/casp17_3d_molecular_object_atlas/T1331_5AT/current_chain_A/coordinates/T1331_chain_A.pdb` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

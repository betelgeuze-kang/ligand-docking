# H1344_HSV_gD_HAB72 Coordinate Materialization Plan

- object_count: `3`
- ready/blocked: `3/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H1344_HSV_gD_HAB72/objects/chain_A/models/H1344_chain_A.pdb` | `casp17/casp17_3d_molecular_object_atlas/H1344_HSV_gD_HAB72/current_chain_A/coordinates/H1344_chain_A.pdb` | `-` |
| `current_chain_B` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H1344_HSV_gD_HAB72/objects/chain_B/models/H1344_chain_B.pdb` | `casp17/casp17_3d_molecular_object_atlas/H1344_HSV_gD_HAB72/current_chain_B/coordinates/H1344_chain_B.pdb` | `-` |
| `current_chain_C` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H1344_HSV_gD_HAB72/objects/chain_C/models/H1344_chain_C.pdb` | `casp17/casp17_3d_molecular_object_atlas/H1344_HSV_gD_HAB72/current_chain_C/coordinates/H1344_chain_C.pdb` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

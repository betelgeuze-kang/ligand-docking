# R2341_RRE_core Coordinate Materialization Plan

- object_count: `1`
- ready/blocked: `1/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `massivefold_model1_candidate` | `coordinate_materialization_ready_dry_run` | `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/model.cif` | `casp17/casp17_3d_molecular_object_atlas/R2341_RRE_core/massivefold_model1_candidate/coordinates/model.cif` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

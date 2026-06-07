# T2313_P66 Coordinate Materialization Plan

- object_count: `2`
- ready/blocked: `2/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/T2313_P66/objects/chain_A/models/T2313_chain_A.pdb` | `casp17/casp17_3d_molecular_object_atlas/T2313_P66/current_chain_A/coordinates/T2313_chain_A.pdb` | `-` |
| `massivefold_model1_candidate` | `coordinate_materialization_ready_dry_run` | `casp17/massivefold_representative_viewers/t2313/selection_085_afm_woTemplates_v3_model_5/model.cif` | `casp17/casp17_3d_molecular_object_atlas/T2313_P66/massivefold_model1_candidate/coordinates/model.cif` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

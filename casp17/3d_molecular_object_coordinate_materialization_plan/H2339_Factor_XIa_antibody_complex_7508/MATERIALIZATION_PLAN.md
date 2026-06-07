# H2339_Factor_XIa_antibody_complex_7508 Coordinate Materialization Plan

- object_count: `5`
- ready/blocked: `5/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2339_Factor_XIa_antibody_complex_7508/objects/chain_A/models/H2339_chain_A.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2339_Factor_XIa_antibody_complex_7508/current_chain_A/coordinates/H2339_chain_A.pdb` | `-` |
| `current_chain_B` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2339_Factor_XIa_antibody_complex_7508/objects/chain_B/models/H2339_chain_B.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2339_Factor_XIa_antibody_complex_7508/current_chain_B/coordinates/H2339_chain_B.pdb` | `-` |
| `current_chain_C` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2339_Factor_XIa_antibody_complex_7508/objects/chain_C/models/H2339_chain_C.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2339_Factor_XIa_antibody_complex_7508/current_chain_C/coordinates/H2339_chain_C.pdb` | `-` |
| `current_chain_D` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2339_Factor_XIa_antibody_complex_7508/objects/chain_D/models/H2339_chain_D.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2339_Factor_XIa_antibody_complex_7508/current_chain_D/coordinates/H2339_chain_D.pdb` | `-` |
| `massivefold_model1_candidate` | `coordinate_materialization_ready_dry_run` | `casp17/massivefold_representative_viewers/h2339/selection_111_afm_basic_v1_model_135/model.cif` | `casp17/casp17_3d_molecular_object_atlas/H2339_Factor_XIa_antibody_complex_7508/massivefold_model1_candidate/coordinates/model.cif` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

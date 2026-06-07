# H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex Coordinate Materialization Plan

- object_count: `4`
- ready/blocked: `4/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/objects/chain_A/models/H2319_chain_A.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/current_chain_A/coordinates/H2319_chain_A.pdb` | `-` |
| `current_chain_B` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/objects/chain_B/models/H2319_chain_B.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/current_chain_B/coordinates/H2319_chain_B.pdb` | `-` |
| `current_chain_C` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/objects/chain_C/models/H2319_chain_C.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/current_chain_C/coordinates/H2319_chain_C.pdb` | `-` |
| `massivefold_model1_candidate` | `coordinate_materialization_ready_dry_run` | `casp17/massivefold_representative_viewers/h2319/selection_125_afm_basic_v3_model_1/model.cif` | `casp17/casp17_3d_molecular_object_atlas/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex/massivefold_model1_candidate/coordinates/model.cif` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

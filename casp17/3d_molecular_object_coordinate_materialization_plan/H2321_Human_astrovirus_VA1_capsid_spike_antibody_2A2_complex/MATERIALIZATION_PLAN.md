# H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex Coordinate Materialization Plan

- object_count: `4`
- ready/blocked: `4/0`
- policy: `dry_run_no_copy`

| object | status | source coordinate | proposed coordinate copy | blockers |
| --- | --- | --- | --- | --- |
| `current_chain_A` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/objects/chain_A/models/H2321_chain_A.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/current_chain_A/coordinates/H2321_chain_A.pdb` | `-` |
| `current_chain_B` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/objects/chain_B/models/H2321_chain_B.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/current_chain_B/coordinates/H2321_chain_B.pdb` | `-` |
| `current_chain_C` | `coordinate_materialization_ready_dry_run` | `casp17/targets_current/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/objects/chain_C/models/H2321_chain_C.pdb` | `casp17/casp17_3d_molecular_object_atlas/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/current_chain_C/coordinates/H2321_chain_C.pdb` | `-` |
| `massivefold_model1_candidate` | `coordinate_materialization_ready_dry_run` | `casp17/massivefold_representative_viewers/h2321/selection_086_afm_dropout_full_v3_model_3/model.cif` | `casp17/casp17_3d_molecular_object_atlas/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex/massivefold_model1_candidate/coordinates/model.cif` | `-` |

## Claim Boundary

CASP17 3D molecular object coordinate materialization dry-run only. It verifies that each protein/object atlas folder has a present source coordinate model and a deterministic proposed destination under the per-object folder. It does not copy coordinates, alter source models, compute native accuracy, serialize a CASP author code, or submit to CASP.

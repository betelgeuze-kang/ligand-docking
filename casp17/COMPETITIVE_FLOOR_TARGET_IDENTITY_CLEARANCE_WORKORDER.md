# CASP17 Competitive-Floor Target Identity Clearance Workorder

- generated: `2026-05-26T01:16:21+09:00`
- clearance_workorder_status: `awaiting_native_or_provenance`
- clearance_queue_status: `awaiting_target_identity_clearance`
- workorders: `3`
- ready/native+provenance/native/provenance: `0/3/0/0`
- dropzones/templates/stubs: `3/3/3`
- first open: `H1319` `native_and_provenance_required`
- next action: place a cleared native PDB and complete the no-leak provenance template

## Workorders

| rank | target | status | folder | native dropzone | provenance template | manifest stub | next action |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `H1319` | `native_and_provenance_required` | `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex` | `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/native/H1319_native.pdb` | `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/provenance_template.csv` | `casp17/competitive_floor_target_identity_clearance_workorders/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/manifest_stub.csv` | place a cleared native PDB and complete the no-leak provenance template |
| 2 | `H1321` | `native_and_provenance_required` | `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex` | `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/native/H1321_native.pdb` | `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/provenance_template.csv` | `casp17/competitive_floor_target_identity_clearance_workorders/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/manifest_stub.csv` | place a cleared native PDB and complete the no-leak provenance template |
| 3 | `H2324` | `native_and_provenance_required` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/native/H2324_native.pdb` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/manifest_stub.csv` | place a cleared native PDB and complete the no-leak provenance template |

## Claim Boundary

Local competitive-floor target identity clearance workorder only. It creates per-target folders, native dropzone paths, provenance templates, and manifest stubs from the clearance queue. It does not fetch native structures, clear no-leak provenance, choose historical targets, score native accuracy, mutate identity intake files, or submit to CASP.

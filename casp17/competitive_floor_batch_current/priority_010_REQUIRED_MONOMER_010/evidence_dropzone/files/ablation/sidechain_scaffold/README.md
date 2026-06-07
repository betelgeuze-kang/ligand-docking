# ablation_file dropzone

- dropzone_folder: `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/evidence_dropzone`
- class_folder: `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/evidence_dropzone/files/ablation/sidechain_scaffold`
- open actions: `1`

| column | blocker | drop path | note |
| --- | --- | --- | --- |
| `sidechain_scaffold_prediction_pdb` | `sidechain_scaffold_prediction_pdb_placeholder` | `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/evidence_dropzone/files/ablation/sidechain_scaffold/<HISTORICAL_TARGET_ID>TS.pdb` | place validated local PDB in casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/evidence_dropzone/files/ablation/sidechain_scaffold/<HISTORICAL_TARGET_ID>TS.pdb, then update sidechain_scaffold_prediction_pdb in row_fill.csv |

## Claim Boundary

Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, run predictors, clear provenance, score native accuracy, or submit to CASP.

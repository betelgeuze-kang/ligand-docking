# core_file dropzone

- dropzone_folder: `casp17/competitive_floor_batch_current/priority_003_REQUIRED_MONOMER_003/evidence_dropzone`
- class_folder: `casp17/competitive_floor_batch_current/priority_003_REQUIRED_MONOMER_003/evidence_dropzone/files/core`
- open actions: `2`

| column | blocker | drop path | note |
| --- | --- | --- | --- |
| `prediction_pdb` | `prediction_pdb_placeholder` | `casp17/competitive_floor_batch_current/priority_003_REQUIRED_MONOMER_003/evidence_dropzone/files/core/<HISTORICAL_TARGET_ID>_prediction.pdb` | place validated local PDB in casp17/competitive_floor_batch_current/priority_003_REQUIRED_MONOMER_003/evidence_dropzone/files/core/<HISTORICAL_TARGET_ID>_prediction.pdb, then update prediction_pdb in row_fill.csv |
| `native_pdb` | `native_pdb_placeholder` | `casp17/competitive_floor_batch_current/priority_003_REQUIRED_MONOMER_003/evidence_dropzone/files/core/<HISTORICAL_TARGET_ID>_native.pdb` | place validated local PDB in casp17/competitive_floor_batch_current/priority_003_REQUIRED_MONOMER_003/evidence_dropzone/files/core/<HISTORICAL_TARGET_ID>_native.pdb, then update native_pdb in row_fill.csv |

## Claim Boundary

Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, run predictors, clear provenance, score native accuracy, or submit to CASP.

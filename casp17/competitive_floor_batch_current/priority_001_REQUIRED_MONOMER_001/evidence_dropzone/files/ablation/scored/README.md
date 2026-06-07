# ablation_file dropzone

- dropzone_folder: `casp17/competitive_floor_batch_current/priority_001_REQUIRED_MONOMER_001/evidence_dropzone`
- class_folder: `casp17/competitive_floor_batch_current/priority_001_REQUIRED_MONOMER_001/evidence_dropzone/files/ablation/scored`
- open actions: `1`

| column | blocker | drop path | note |
| --- | --- | --- | --- |
| `scored_prediction_pdb` | `scored_prediction_pdb_placeholder` | `casp17/competitive_floor_batch_current/priority_001_REQUIRED_MONOMER_001/evidence_dropzone/files/ablation/scored/<HISTORICAL_TARGET_ID>TS.pdb` | place validated local PDB in casp17/competitive_floor_batch_current/priority_001_REQUIRED_MONOMER_001/evidence_dropzone/files/ablation/scored/<HISTORICAL_TARGET_ID>TS.pdb, then update scored_prediction_pdb in row_fill.csv |

## Claim Boundary

Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, run predictors, clear provenance, score native accuracy, or submit to CASP.

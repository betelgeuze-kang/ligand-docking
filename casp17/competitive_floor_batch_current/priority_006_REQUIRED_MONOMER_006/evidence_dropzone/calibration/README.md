# calibration dropzone

- dropzone_folder: `casp17/competitive_floor_batch_current/priority_006_REQUIRED_MONOMER_006/evidence_dropzone`
- class_folder: `casp17/competitive_floor_batch_current/priority_006_REQUIRED_MONOMER_006/evidence_dropzone/calibration`
- open actions: `6`

| column | blocker | drop path | note |
| --- | --- | --- | --- |
| `selected_model_rank` | `selected_model_rank_requires_rank_1_to_5` | `-` | fill selected_model_rank from the local historical scoring/calibration packet |
| `best_model_rank` | `best_model_rank_requires_rank_1_to_5` | `-` | fill best_model_rank from the local historical scoring/calibration packet |
| `selected_native_metric` | `selected_native_metric_requires_numeric` | `-` | fill selected_native_metric from the local historical scoring/calibration packet |
| `best_native_metric` | `best_native_metric_requires_numeric` | `-` | fill best_native_metric from the local historical scoring/calibration packet |
| `selected_score` | `selected_score_requires_numeric` | `-` | fill selected_score from the local historical scoring/calibration packet |
| `best_score` | `best_score_requires_numeric` | `-` | fill best_score from the local historical scoring/calibration packet |

## Claim Boundary

Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, run predictors, clear provenance, score native accuracy, or submit to CASP.

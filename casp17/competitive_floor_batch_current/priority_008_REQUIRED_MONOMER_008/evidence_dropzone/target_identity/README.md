# target_identity dropzone

- dropzone_folder: `casp17/competitive_floor_batch_current/priority_008_REQUIRED_MONOMER_008/evidence_dropzone`
- class_folder: `casp17/competitive_floor_batch_current/priority_008_REQUIRED_MONOMER_008/evidence_dropzone/target_identity`
- open actions: `2`

| column | blocker | drop path | note |
| --- | --- | --- | --- |
| `benchmark_id` | `benchmark_id_placeholder` | `-` | replace benchmark_id in row_fill.csv after choosing a cleared historical target |
| `target_id` | `target_id_placeholder` | `-` | replace target_id in row_fill.csv after choosing a cleared historical target |

## Claim Boundary

Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, run predictors, clear provenance, score native accuracy, or submit to CASP.

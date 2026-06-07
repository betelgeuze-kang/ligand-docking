# CASP17 Competitive-Floor Evidence Intake

- dropzone_id: `priority_014_REQUIRED_COMPLEX_004`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_014_REQUIRED_COMPLEX_004/row_fill.csv`
- patch_candidate_csv: `casp17/competitive_floor_batch_current/priority_014_REQUIRED_COMPLEX_004/ROW_FILL_PATCH_CANDIDATE.csv`
- open intake rows: `30`

| rank | class | column | status | recommended value | next action |
| ---: | --- | --- | --- | --- | --- |
| 391 | `target_identity` | `benchmark_id` | `awaiting_operator_value` | `-` | fill benchmark_id in row_fill.csv from cleared local evidence |
| 392 | `target_identity` | `target_id` | `awaiting_operator_value` | `-` | fill target_id in row_fill.csv from cleared local evidence |
| 393 | `core_file` | `prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 394 | `core_file` | `native_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 395 | `provenance` | `leakage_clearance` | `awaiting_operator_value` | `-` | fill leakage_clearance in row_fill.csv from cleared local evidence |
| 396 | `provenance` | `prediction_method` | `awaiting_operator_value` | `-` | fill prediction_method in row_fill.csv from cleared local evidence |
| 397 | `provenance` | `prediction_created_at` | `awaiting_operator_value` | `-` | fill prediction_created_at in row_fill.csv from cleared local evidence |
| 398 | `provenance` | `native_release_date` | `awaiting_operator_value` | `-` | fill native_release_date in row_fill.csv from cleared local evidence |
| 399 | `provenance` | `prediction_generated_before_native_release` | `awaiting_operator_value` | `-` | fill prediction_generated_before_native_release in row_fill.csv from cleared local evidence |
| 400 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_operator_value` | `-` | fill public_template_or_native_used_for_prediction in row_fill.csv from cleared local evidence |
| 401 | `provenance` | `other_team_model_used` | `awaiting_operator_value` | `-` | fill other_team_model_used in row_fill.csv from cleared local evidence |
| 402 | `provenance` | `post_release_information_used` | `awaiting_operator_value` | `-` | fill post_release_information_used in row_fill.csv from cleared local evidence |
| 403 | `provenance` | `current_casp17_target` | `awaiting_operator_value` | `-` | fill current_casp17_target in row_fill.csv from cleared local evidence |
| 404 | `provenance` | `operator_clearance` | `awaiting_operator_value` | `-` | fill operator_clearance in row_fill.csv from cleared local evidence |
| 405 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 406 | `ablation_file` | `scored_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 407 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 408 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 409 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 410 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 411 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 412 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 413 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 414 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 415 | `calibration` | `selected_model_rank` | `awaiting_operator_value` | `-` | fill selected_model_rank in row_fill.csv from cleared local evidence |
| 416 | `calibration` | `best_model_rank` | `awaiting_operator_value` | `-` | fill best_model_rank in row_fill.csv from cleared local evidence |
| 417 | `calibration` | `selected_native_metric` | `awaiting_operator_value` | `-` | fill selected_native_metric in row_fill.csv from cleared local evidence |
| 418 | `calibration` | `best_native_metric` | `awaiting_operator_value` | `-` | fill best_native_metric in row_fill.csv from cleared local evidence |
| 419 | `calibration` | `selected_score` | `awaiting_operator_value` | `-` | fill selected_score in row_fill.csv from cleared local evidence |
| 420 | `calibration` | `best_score` | `awaiting_operator_value` | `-` | fill best_score in row_fill.csv from cleared local evidence |

## Claim Boundary

Local competitive-floor evidence intake only. It audits files and operator-filled fields already placed in dropzones and writes row_fill patch candidates; it does not choose targets, fetch native structures, clear provenance, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP.

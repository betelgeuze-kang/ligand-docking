# CASP17 Competitive-Floor Evidence Intake

- dropzone_id: `priority_012_REQUIRED_COMPLEX_002`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_012_REQUIRED_COMPLEX_002/row_fill.csv`
- patch_candidate_csv: `casp17/competitive_floor_batch_current/priority_012_REQUIRED_COMPLEX_002/ROW_FILL_PATCH_CANDIDATE.csv`
- open intake rows: `30`

| rank | class | column | status | recommended value | next action |
| ---: | --- | --- | --- | --- | --- |
| 331 | `target_identity` | `benchmark_id` | `awaiting_operator_value` | `-` | fill benchmark_id in row_fill.csv from cleared local evidence |
| 332 | `target_identity` | `target_id` | `awaiting_operator_value` | `-` | fill target_id in row_fill.csv from cleared local evidence |
| 333 | `core_file` | `prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 334 | `core_file` | `native_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 335 | `provenance` | `leakage_clearance` | `awaiting_operator_value` | `-` | fill leakage_clearance in row_fill.csv from cleared local evidence |
| 336 | `provenance` | `prediction_method` | `awaiting_operator_value` | `-` | fill prediction_method in row_fill.csv from cleared local evidence |
| 337 | `provenance` | `prediction_created_at` | `awaiting_operator_value` | `-` | fill prediction_created_at in row_fill.csv from cleared local evidence |
| 338 | `provenance` | `native_release_date` | `awaiting_operator_value` | `-` | fill native_release_date in row_fill.csv from cleared local evidence |
| 339 | `provenance` | `prediction_generated_before_native_release` | `awaiting_operator_value` | `-` | fill prediction_generated_before_native_release in row_fill.csv from cleared local evidence |
| 340 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_operator_value` | `-` | fill public_template_or_native_used_for_prediction in row_fill.csv from cleared local evidence |
| 341 | `provenance` | `other_team_model_used` | `awaiting_operator_value` | `-` | fill other_team_model_used in row_fill.csv from cleared local evidence |
| 342 | `provenance` | `post_release_information_used` | `awaiting_operator_value` | `-` | fill post_release_information_used in row_fill.csv from cleared local evidence |
| 343 | `provenance` | `current_casp17_target` | `awaiting_operator_value` | `-` | fill current_casp17_target in row_fill.csv from cleared local evidence |
| 344 | `provenance` | `operator_clearance` | `awaiting_operator_value` | `-` | fill operator_clearance in row_fill.csv from cleared local evidence |
| 345 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 346 | `ablation_file` | `scored_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 347 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 348 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 349 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 350 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 351 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 352 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 353 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 354 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 355 | `calibration` | `selected_model_rank` | `awaiting_operator_value` | `-` | fill selected_model_rank in row_fill.csv from cleared local evidence |
| 356 | `calibration` | `best_model_rank` | `awaiting_operator_value` | `-` | fill best_model_rank in row_fill.csv from cleared local evidence |
| 357 | `calibration` | `selected_native_metric` | `awaiting_operator_value` | `-` | fill selected_native_metric in row_fill.csv from cleared local evidence |
| 358 | `calibration` | `best_native_metric` | `awaiting_operator_value` | `-` | fill best_native_metric in row_fill.csv from cleared local evidence |
| 359 | `calibration` | `selected_score` | `awaiting_operator_value` | `-` | fill selected_score in row_fill.csv from cleared local evidence |
| 360 | `calibration` | `best_score` | `awaiting_operator_value` | `-` | fill best_score in row_fill.csv from cleared local evidence |

## Claim Boundary

Local competitive-floor evidence intake only. It audits files and operator-filled fields already placed in dropzones and writes row_fill patch candidates; it does not choose targets, fetch native structures, clear provenance, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP.

# CASP17 Competitive-Floor Evidence Intake

- dropzone_id: `priority_001_REQUIRED_MONOMER_001`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_001_REQUIRED_MONOMER_001/row_fill.csv`
- patch_candidate_csv: `casp17/competitive_floor_batch_current/priority_001_REQUIRED_MONOMER_001/ROW_FILL_PATCH_CANDIDATE.csv`
- open intake rows: `30`

| rank | class | column | status | recommended value | next action |
| ---: | --- | --- | --- | --- | --- |
| 1 | `target_identity` | `benchmark_id` | `awaiting_operator_value` | `-` | fill benchmark_id in row_fill.csv from cleared local evidence |
| 2 | `target_identity` | `target_id` | `awaiting_operator_value` | `-` | fill target_id in row_fill.csv from cleared local evidence |
| 3 | `core_file` | `prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 4 | `core_file` | `native_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 5 | `provenance` | `leakage_clearance` | `awaiting_operator_value` | `-` | fill leakage_clearance in row_fill.csv from cleared local evidence |
| 6 | `provenance` | `prediction_method` | `awaiting_operator_value` | `-` | fill prediction_method in row_fill.csv from cleared local evidence |
| 7 | `provenance` | `prediction_created_at` | `awaiting_operator_value` | `-` | fill prediction_created_at in row_fill.csv from cleared local evidence |
| 8 | `provenance` | `native_release_date` | `awaiting_operator_value` | `-` | fill native_release_date in row_fill.csv from cleared local evidence |
| 9 | `provenance` | `prediction_generated_before_native_release` | `awaiting_operator_value` | `-` | fill prediction_generated_before_native_release in row_fill.csv from cleared local evidence |
| 10 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_operator_value` | `-` | fill public_template_or_native_used_for_prediction in row_fill.csv from cleared local evidence |
| 11 | `provenance` | `other_team_model_used` | `awaiting_operator_value` | `-` | fill other_team_model_used in row_fill.csv from cleared local evidence |
| 12 | `provenance` | `post_release_information_used` | `awaiting_operator_value` | `-` | fill post_release_information_used in row_fill.csv from cleared local evidence |
| 13 | `provenance` | `current_casp17_target` | `awaiting_operator_value` | `-` | fill current_casp17_target in row_fill.csv from cleared local evidence |
| 14 | `provenance` | `operator_clearance` | `awaiting_operator_value` | `-` | fill operator_clearance in row_fill.csv from cleared local evidence |
| 15 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 16 | `ablation_file` | `scored_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 17 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 18 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 19 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 20 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 21 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 22 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 23 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 24 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 25 | `calibration` | `selected_model_rank` | `awaiting_operator_value` | `-` | fill selected_model_rank in row_fill.csv from cleared local evidence |
| 26 | `calibration` | `best_model_rank` | `awaiting_operator_value` | `-` | fill best_model_rank in row_fill.csv from cleared local evidence |
| 27 | `calibration` | `selected_native_metric` | `awaiting_operator_value` | `-` | fill selected_native_metric in row_fill.csv from cleared local evidence |
| 28 | `calibration` | `best_native_metric` | `awaiting_operator_value` | `-` | fill best_native_metric in row_fill.csv from cleared local evidence |
| 29 | `calibration` | `selected_score` | `awaiting_operator_value` | `-` | fill selected_score in row_fill.csv from cleared local evidence |
| 30 | `calibration` | `best_score` | `awaiting_operator_value` | `-` | fill best_score in row_fill.csv from cleared local evidence |

## Claim Boundary

Local competitive-floor evidence intake only. It audits files and operator-filled fields already placed in dropzones and writes row_fill patch candidates; it does not choose targets, fetch native structures, clear provenance, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP.

# CASP17 Competitive-Floor Evidence Intake

- dropzone_id: `priority_008_REQUIRED_MONOMER_008`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_008_REQUIRED_MONOMER_008/row_fill.csv`
- patch_candidate_csv: `casp17/competitive_floor_batch_current/priority_008_REQUIRED_MONOMER_008/ROW_FILL_PATCH_CANDIDATE.csv`
- open intake rows: `30`

| rank | class | column | status | recommended value | next action |
| ---: | --- | --- | --- | --- | --- |
| 211 | `target_identity` | `benchmark_id` | `awaiting_operator_value` | `-` | fill benchmark_id in row_fill.csv from cleared local evidence |
| 212 | `target_identity` | `target_id` | `awaiting_operator_value` | `-` | fill target_id in row_fill.csv from cleared local evidence |
| 213 | `core_file` | `prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 214 | `core_file` | `native_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 215 | `provenance` | `leakage_clearance` | `awaiting_operator_value` | `-` | fill leakage_clearance in row_fill.csv from cleared local evidence |
| 216 | `provenance` | `prediction_method` | `awaiting_operator_value` | `-` | fill prediction_method in row_fill.csv from cleared local evidence |
| 217 | `provenance` | `prediction_created_at` | `awaiting_operator_value` | `-` | fill prediction_created_at in row_fill.csv from cleared local evidence |
| 218 | `provenance` | `native_release_date` | `awaiting_operator_value` | `-` | fill native_release_date in row_fill.csv from cleared local evidence |
| 219 | `provenance` | `prediction_generated_before_native_release` | `awaiting_operator_value` | `-` | fill prediction_generated_before_native_release in row_fill.csv from cleared local evidence |
| 220 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_operator_value` | `-` | fill public_template_or_native_used_for_prediction in row_fill.csv from cleared local evidence |
| 221 | `provenance` | `other_team_model_used` | `awaiting_operator_value` | `-` | fill other_team_model_used in row_fill.csv from cleared local evidence |
| 222 | `provenance` | `post_release_information_used` | `awaiting_operator_value` | `-` | fill post_release_information_used in row_fill.csv from cleared local evidence |
| 223 | `provenance` | `current_casp17_target` | `awaiting_operator_value` | `-` | fill current_casp17_target in row_fill.csv from cleared local evidence |
| 224 | `provenance` | `operator_clearance` | `awaiting_operator_value` | `-` | fill operator_clearance in row_fill.csv from cleared local evidence |
| 225 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 226 | `ablation_file` | `scored_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 227 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 228 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 229 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 230 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 231 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 232 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 233 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 234 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_dropzone_file` | `-` | place the validated no-leak local PDB in the indicated dropzone folder |
| 235 | `calibration` | `selected_model_rank` | `awaiting_operator_value` | `-` | fill selected_model_rank in row_fill.csv from cleared local evidence |
| 236 | `calibration` | `best_model_rank` | `awaiting_operator_value` | `-` | fill best_model_rank in row_fill.csv from cleared local evidence |
| 237 | `calibration` | `selected_native_metric` | `awaiting_operator_value` | `-` | fill selected_native_metric in row_fill.csv from cleared local evidence |
| 238 | `calibration` | `best_native_metric` | `awaiting_operator_value` | `-` | fill best_native_metric in row_fill.csv from cleared local evidence |
| 239 | `calibration` | `selected_score` | `awaiting_operator_value` | `-` | fill selected_score in row_fill.csv from cleared local evidence |
| 240 | `calibration` | `best_score` | `awaiting_operator_value` | `-` | fill best_score in row_fill.csv from cleared local evidence |

## Claim Boundary

Local competitive-floor evidence intake only. It audits files and operator-filled fields already placed in dropzones and writes row_fill patch candidates; it does not choose targets, fetch native structures, clear provenance, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP.

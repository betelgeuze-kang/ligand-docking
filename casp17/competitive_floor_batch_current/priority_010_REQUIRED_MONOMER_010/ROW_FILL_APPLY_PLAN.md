# CASP17 Competitive-Floor Row Fill Apply Plan

- dropzone_id: `priority_010_REQUIRED_MONOMER_010`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/row_fill.csv`
- apply_plan_csv: `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/ROW_FILL_APPLY_PLAN.csv`
- action count: `30`

| rank | class | column | status | current | recommended | next action |
| ---: | --- | --- | --- | --- | --- | --- |
| 271 | `target_identity` | `benchmark_id` | `awaiting_evidence` | `hist_REQUIRED_MONOMER_010` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 272 | `target_identity` | `target_id` | `awaiting_evidence` | `REQUIRED_MONOMER_010` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 273 | `core_file` | `prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_predictions_current/REQUIRED_MONOMER_010_prediction.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 274 | `core_file` | `native_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_natives_current/REQUIRED_MONOMER_010_native.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 275 | `provenance` | `leakage_clearance` | `awaiting_evidence` | `REQUIRED_NO_LEAK_CLEARANCE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 276 | `provenance` | `prediction_method` | `awaiting_evidence` | `REQUIRED_INTERNAL_METHOD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 277 | `provenance` | `prediction_created_at` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 278 | `provenance` | `native_release_date` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 279 | `provenance` | `prediction_generated_before_native_release` | `awaiting_evidence` | `REQUIRED_TRUE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 280 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 281 | `provenance` | `other_team_model_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 282 | `provenance` | `post_release_information_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 283 | `provenance` | `current_casp17_target` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 284 | `provenance` | `operator_clearance` | `awaiting_evidence` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 285 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/recursive/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 286 | `ablation_file` | `scored_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/scored/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 287 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_scaffold/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 288 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_repacked/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 289 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_completed/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 290 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/steric_relaxed/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 291 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/rotamer_minimized/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 292 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/polar_refined/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 293 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/forcefield_minimized/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 294 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/statistical_rotamer/REQUIRED_MONOMER_010TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 295 | `calibration` | `selected_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 296 | `calibration` | `best_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 297 | `calibration` | `selected_native_metric` | `awaiting_evidence` | `REQUIRED_NATIVE_METRIC` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 298 | `calibration` | `best_native_metric` | `awaiting_evidence` | `REQUIRED_ORACLE_METRIC` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 299 | `calibration` | `selected_score` | `awaiting_evidence` | `REQUIRED_INTERNAL_SCORE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 300 | `calibration` | `best_score` | `awaiting_evidence` | `REQUIRED_ORACLE_SCORE` | `-` | wait for cleared evidence, then rerun intake and patch gate |

## Claim Boundary

Local competitive-floor row_fill apply plan only. By default it writes review plans and does not mutate row_fill.csv. The optional --apply mode applies only ready_to_patch rows with non-placeholder recommendations and still does not choose targets, clear no-leak provenance, score native accuracy, fetch native structures, run predictors, or submit to CASP.

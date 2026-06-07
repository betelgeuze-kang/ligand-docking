# CASP17 Competitive-Floor Row Fill Apply Plan

- dropzone_id: `priority_012_REQUIRED_COMPLEX_002`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_012_REQUIRED_COMPLEX_002/row_fill.csv`
- apply_plan_csv: `casp17/competitive_floor_batch_current/priority_012_REQUIRED_COMPLEX_002/ROW_FILL_APPLY_PLAN.csv`
- action count: `30`

| rank | class | column | status | current | recommended | next action |
| ---: | --- | --- | --- | --- | --- | --- |
| 331 | `target_identity` | `benchmark_id` | `awaiting_evidence` | `hist_REQUIRED_COMPLEX_002` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 332 | `target_identity` | `target_id` | `awaiting_evidence` | `REQUIRED_COMPLEX_002` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 333 | `core_file` | `prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_predictions_current/REQUIRED_COMPLEX_002_prediction.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 334 | `core_file` | `native_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_natives_current/REQUIRED_COMPLEX_002_native.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 335 | `provenance` | `leakage_clearance` | `awaiting_evidence` | `REQUIRED_NO_LEAK_CLEARANCE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 336 | `provenance` | `prediction_method` | `awaiting_evidence` | `REQUIRED_INTERNAL_METHOD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 337 | `provenance` | `prediction_created_at` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 338 | `provenance` | `native_release_date` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 339 | `provenance` | `prediction_generated_before_native_release` | `awaiting_evidence` | `REQUIRED_TRUE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 340 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 341 | `provenance` | `other_team_model_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 342 | `provenance` | `post_release_information_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 343 | `provenance` | `current_casp17_target` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 344 | `provenance` | `operator_clearance` | `awaiting_evidence` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 345 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/recursive/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 346 | `ablation_file` | `scored_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/scored/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 347 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_scaffold/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 348 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_repacked/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 349 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_completed/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 350 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/steric_relaxed/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 351 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/rotamer_minimized/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 352 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/polar_refined/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 353 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/forcefield_minimized/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 354 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/statistical_rotamer/REQUIRED_COMPLEX_002TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 355 | `calibration` | `selected_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 356 | `calibration` | `best_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 357 | `calibration` | `selected_native_metric` | `awaiting_evidence` | `REQUIRED_NATIVE_METRIC` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 358 | `calibration` | `best_native_metric` | `awaiting_evidence` | `REQUIRED_ORACLE_METRIC` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 359 | `calibration` | `selected_score` | `awaiting_evidence` | `REQUIRED_INTERNAL_SCORE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 360 | `calibration` | `best_score` | `awaiting_evidence` | `REQUIRED_ORACLE_SCORE` | `-` | wait for cleared evidence, then rerun intake and patch gate |

## Claim Boundary

Local competitive-floor row_fill apply plan only. By default it writes review plans and does not mutate row_fill.csv. The optional --apply mode applies only ready_to_patch rows with non-placeholder recommendations and still does not choose targets, clear no-leak provenance, score native accuracy, fetch native structures, run predictors, or submit to CASP.

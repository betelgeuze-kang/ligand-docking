# CASP17 Competitive-Floor Row Fill Patch Dry Run

- dropzone_id: `priority_011_REQUIRED_COMPLEX_001`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_011_REQUIRED_COMPLEX_001/row_fill.csv`
- dry_run_csv: `casp17/competitive_floor_batch_current/priority_011_REQUIRED_COMPLEX_001/ROW_FILL_PATCH_DRY_RUN.csv`
- action count: `30`

| rank | class | column | status | current | recommended | next action |
| ---: | --- | --- | --- | --- | --- | --- |
| 301 | `target_identity` | `benchmark_id` | `awaiting_evidence` | `hist_REQUIRED_COMPLEX_001` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 302 | `target_identity` | `target_id` | `awaiting_evidence` | `REQUIRED_COMPLEX_001` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 303 | `core_file` | `prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_predictions_current/REQUIRED_COMPLEX_001_prediction.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 304 | `core_file` | `native_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_natives_current/REQUIRED_COMPLEX_001_native.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 305 | `provenance` | `leakage_clearance` | `awaiting_evidence` | `REQUIRED_NO_LEAK_CLEARANCE` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 306 | `provenance` | `prediction_method` | `awaiting_evidence` | `REQUIRED_INTERNAL_METHOD` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 307 | `provenance` | `prediction_created_at` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 308 | `provenance` | `native_release_date` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 309 | `provenance` | `prediction_generated_before_native_release` | `awaiting_evidence` | `REQUIRED_TRUE_CONFIRMATION` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 310 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 311 | `provenance` | `other_team_model_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 312 | `provenance` | `post_release_information_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 313 | `provenance` | `current_casp17_target` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 314 | `provenance` | `operator_clearance` | `awaiting_evidence` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 315 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/recursive/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 316 | `ablation_file` | `scored_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/scored/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 317 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_scaffold/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 318 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_repacked/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 319 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_completed/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 320 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/steric_relaxed/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 321 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/rotamer_minimized/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 322 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/polar_refined/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 323 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/forcefield_minimized/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 324 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/statistical_rotamer/REQUIRED_COMPLEX_001TS.pdb` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 325 | `calibration` | `selected_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 326 | `calibration` | `best_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 327 | `calibration` | `selected_native_metric` | `awaiting_evidence` | `REQUIRED_NATIVE_METRIC` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 328 | `calibration` | `best_native_metric` | `awaiting_evidence` | `REQUIRED_ORACLE_METRIC` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 329 | `calibration` | `selected_score` | `awaiting_evidence` | `REQUIRED_INTERNAL_SCORE` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |
| 330 | `calibration` | `best_score` | `awaiting_evidence` | `REQUIRED_ORACLE_SCORE` | `-` | provide the missing cleared evidence, then rerun intake and this patch gate |

## Claim Boundary

Local competitive-floor row_fill patch gate only. It dry-runs row_fill.csv updates from intake patch candidates and writes operator review artifacts; it does not mutate row_fill.csv, choose historical targets, clear no-leak provenance, score native accuracy, fetch native structures, run predictors, or submit to CASP.

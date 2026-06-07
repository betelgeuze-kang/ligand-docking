# CASP17 Competitive-Floor Row Fill Apply Plan

- dropzone_id: `priority_007_REQUIRED_MONOMER_007`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_007_REQUIRED_MONOMER_007/row_fill.csv`
- apply_plan_csv: `casp17/competitive_floor_batch_current/priority_007_REQUIRED_MONOMER_007/ROW_FILL_APPLY_PLAN.csv`
- action count: `30`

| rank | class | column | status | current | recommended | next action |
| ---: | --- | --- | --- | --- | --- | --- |
| 181 | `target_identity` | `benchmark_id` | `awaiting_evidence` | `hist_REQUIRED_MONOMER_007` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 182 | `target_identity` | `target_id` | `awaiting_evidence` | `REQUIRED_MONOMER_007` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 183 | `core_file` | `prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_predictions_current/REQUIRED_MONOMER_007_prediction.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 184 | `core_file` | `native_pdb` | `awaiting_evidence` | `runs/casp17_historical_benchmark_natives_current/REQUIRED_MONOMER_007_native.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 185 | `provenance` | `leakage_clearance` | `awaiting_evidence` | `REQUIRED_NO_LEAK_CLEARANCE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 186 | `provenance` | `prediction_method` | `awaiting_evidence` | `REQUIRED_INTERNAL_METHOD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 187 | `provenance` | `prediction_created_at` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 188 | `provenance` | `native_release_date` | `awaiting_evidence` | `YYYY-MM-DD` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 189 | `provenance` | `prediction_generated_before_native_release` | `awaiting_evidence` | `REQUIRED_TRUE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 190 | `provenance` | `public_template_or_native_used_for_prediction` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 191 | `provenance` | `other_team_model_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 192 | `provenance` | `post_release_information_used` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 193 | `provenance` | `current_casp17_target` | `awaiting_evidence` | `REQUIRED_FALSE_CONFIRMATION` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 194 | `provenance` | `operator_clearance` | `awaiting_evidence` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 195 | `ablation_file` | `recursive_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/recursive/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 196 | `ablation_file` | `scored_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/scored/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 197 | `ablation_file` | `sidechain_scaffold_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_scaffold/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 198 | `ablation_file` | `sidechain_repacked_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_repacked/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 199 | `ablation_file` | `sidechain_completed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/sidechain_completed/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 200 | `ablation_file` | `steric_relaxed_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/steric_relaxed/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 201 | `ablation_file` | `rotamer_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/rotamer_minimized/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 202 | `ablation_file` | `polar_refined_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/polar_refined/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 203 | `ablation_file` | `forcefield_minimized_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/forcefield_minimized/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 204 | `ablation_file` | `statistical_rotamer_prediction_pdb` | `awaiting_evidence` | `runs/casp17_historical_ablation_predictions_current/statistical_rotamer/REQUIRED_MONOMER_007TS.pdb` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 205 | `calibration` | `selected_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 206 | `calibration` | `best_model_rank` | `awaiting_evidence` | `REQUIRED_1_TO_5` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 207 | `calibration` | `selected_native_metric` | `awaiting_evidence` | `REQUIRED_NATIVE_METRIC` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 208 | `calibration` | `best_native_metric` | `awaiting_evidence` | `REQUIRED_ORACLE_METRIC` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 209 | `calibration` | `selected_score` | `awaiting_evidence` | `REQUIRED_INTERNAL_SCORE` | `-` | wait for cleared evidence, then rerun intake and patch gate |
| 210 | `calibration` | `best_score` | `awaiting_evidence` | `REQUIRED_ORACLE_SCORE` | `-` | wait for cleared evidence, then rerun intake and patch gate |

## Claim Boundary

Local competitive-floor row_fill apply plan only. By default it writes review plans and does not mutate row_fill.csv. The optional --apply mode applies only ready_to_patch rows with non-placeholder recommendations and still does not choose targets, clear no-leak provenance, score native accuracy, fetch native structures, run predictors, or submit to CASP.

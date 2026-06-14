# R9 Calibration Cross-Validation Probe

- status: `refine_tier_public_benchmark_calibration_cross_validation_probe_ready`
- cross_validation_mode: `leave_one_target_out`
- combined_pair_count: `25`
- target_fold_count: `25`
- baseline_holdout/combined/p05: `0.6428571428571429/0.5315384615384615/0.23053846153846155`
- fit_trained_best_model_id: `density_size_ridge_l0.1`
- fit_trained_best_model_bootstrap_p05: `0.4944230769230769`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_holdout/combined/p05: `0.5952380952380952/0.6361538461538462/0.4035769230769231`
- locked_cv_bootstrap_p05_drop_from_fit_trained: `0.0908461538461538`
- best_cv_model_id: `density_size_ridge_l0.1`
- best_cv_holdout/combined/p05: `0.5952380952380952/0.6361538461538462/0.4035769230769231`
- holdout_guarded_eligible_model_count: `0`
- cross_validation_generalization_ready: `False`

## Top Cross-Validated Models

| model | features | lambda | holdout | combined | p05 | p05 delta | holdout guarded | claim-grade p05 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `density_size_ridge_l0.1` | `contact_per_atom;pose_atom_count` | `0.1` | `0.595238095238` | `0.636153846154` | `0.403576923077` | `0.173038461538` | `False` | `False` |
| `density_size_ridge_l1` | `contact_per_atom;pose_atom_count` | `1` | `0.595238095238` | `0.597692307692` | `0.324423076923` | `0.0938846153846` | `False` | `False` |
| `descriptor_only_ridge_l0.1` | `contact_per_atom;contact_sqrt_norm;pose_atom_count;min_distance_a` | `0.1` | `0.52380952381` | `0.553076923077` | `0.282846153846` | `0.0523076923077` | `False` | `False` |
| `baseline_density_sqrt_size_ridge_l1` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;pose_atom_count` | `1` | `0.52380952381` | `0.546923076923` | `0.278115384615` | `0.0475769230769` | `False` | `False` |
| `baseline_density_size_ridge_l1` | `baseline_proxy;contact_per_atom;pose_atom_count` | `1` | `0.52380952381` | `0.548461538462` | `0.272769230769` | `0.0422307692308` | `False` | `False` |
| `descriptor_only_ridge_l1` | `contact_per_atom;contact_sqrt_norm;pose_atom_count;min_distance_a` | `1` | `0.52380952381` | `0.544615384615` | `0.270230769231` | `0.0396923076923` | `False` | `False` |
| `baseline_density_size_ridge_l0.1` | `baseline_proxy;contact_per_atom;pose_atom_count` | `0.1` | `0.595238095238` | `0.530769230769` | `0.256692307692` | `0.0261538461538` | `False` | `False` |
| `baseline_contact_min_distance_ridge_l1` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;min_distance_a` | `1` | `0.52380952381` | `0.518461538462` | `0.243692307692` | `0.0131538461538` | `False` | `False` |
| `baseline_contact_min_distance_ridge_l0.1` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;min_distance_a` | `0.1` | `0.52380952381` | `0.518461538462` | `0.243692307692` | `0.0131538461538` | `False` | `False` |
| `descriptor_only_ridge_l10` | `contact_per_atom;contact_sqrt_norm;pose_atom_count;min_distance_a` | `10` | `0.52380952381` | `0.531538461538` | `0.237384615385` | `0.00684615384615` | `False` | `False` |
| `baseline_density_sqrt_size_ridge_l10` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;pose_atom_count` | `10` | `0.52380952381` | `0.519230769231` | `0.220038461538` | `-0.0105` | `False` | `False` |
| `density_size_ridge_l10` | `contact_per_atom;pose_atom_count` | `10` | `0.52380952381` | `0.512307692308` | `0.219038461538` | `-0.0115` | `False` | `False` |

## Locked Model Residuals

| target | pose | source | split | variant rank | reference rank | rank abs error |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `fit` | `2` | `16` | `14` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `fit` | `22` | `9` | `13` |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `holdout` | `17` | `6` | `11` |
| `4j28` | `4j28_123` | `candidate_fill_preview` | `holdout` | `25` | `15` | `10` |
| `1gpk` | `1gpk_364` | `candidate_fill_preview` | `fit` | `10` | `19` | `9` |
| `3n7a` | `3n7a_955` | `candidate_fill_preview` | `holdout` | `16` | `23` | `7` |
| `1syi` | `1syi_353` | `existing_materialized` | `holdout` | `12` | `18` | `6` |
| `3uo4` | `3uo4_374` | `candidate_fill_preview` | `fit` | `5` | `11` | `6` |
| `4ivc` | `4ivc_20` | `candidate_fill_preview` | `holdout` | `7` | `1` | `6` |
| `4ivb` | `4ivb_253` | `candidate_fill_preview` | `fit` | `9` | `4` | `5` |

## Claim Boundary

R9 calibration cross-validation probe only; it trains predeclared scoring hypotheses while leaving one target out at a time and reports out-of-fold diagnostics. It does not rewrite candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Do not use the near-threshold fit-trained model for production scoring. Add independent/operator-reviewed R9 evidence or reduce top residual targets, then rerun cross-validation and claim-grade bootstrap gates.

# R9 Fit-Trained Calibration Probe

- status: `refine_tier_public_benchmark_fit_trained_calibration_probe_ready`
- combined_pair_count: `25`
- fit_pair_count: `17`
- holdout_pair_count: `8`
- feature_complete_pair_count: `25`
- baseline_fit/holdout/combined: `0.5343137254901961/0.6428571428571429/0.5315384615384615`
- baseline_bootstrap_p05: `0.23053846153846155`
- best_model_id: `density_size_ridge_l0.1`
- best_model_features: `contact_per_atom;pose_atom_count`
- best_model_fit/holdout/combined: `0.6617647058823529/0.6904761904761905/0.7`
- best_model_bootstrap_p05: `0.4944230769230769`
- best_model_bootstrap_p05_gap_to_claim_grade: `0.00557692307692309`
- best_model_claim_grade_p05_ready: `False`
- calibration_generalization_ready: `False`

## Top Fit-Trained Models

| model | features | lambda | fit | holdout | combined | p05 | p05 delta | holdout guarded | claim-grade p05 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `density_size_ridge_l0.1` | `contact_per_atom;pose_atom_count` | `0.1` | `0.661764705882` | `0.690476190476` | `0.7` | `0.494423076923` | `0.263884615385` | `True` | `False` |
| `density_size_ridge_l1` | `contact_per_atom;pose_atom_count` | `1` | `0.661764705882` | `0.690476190476` | `0.696153846154` | `0.486884615385` | `0.256346153846` | `True` | `False` |
| `descriptor_only_ridge_l0.1` | `contact_per_atom;contact_sqrt_norm;pose_atom_count;min_distance_a` | `0.1` | `0.634803921569` | `0.690476190476` | `0.688461538462` | `0.482192307692` | `0.251653846154` | `True` | `False` |
| `descriptor_only_ridge_l1` | `contact_per_atom;contact_sqrt_norm;pose_atom_count;min_distance_a` | `1` | `0.676470588235` | `0.690476190476` | `0.68` | `0.454230769231` | `0.223692307692` | `True` | `False` |
| `baseline_density_size_ridge_l0.1` | `baseline_proxy;contact_per_atom;pose_atom_count` | `0.1` | `0.625` | `0.690476190476` | `0.666153846154` | `0.447115384615` | `0.216576923077` | `True` | `False` |
| `baseline_density_size_ridge_l1` | `baseline_proxy;contact_per_atom;pose_atom_count` | `1` | `0.634803921569` | `0.690476190476` | `0.663846153846` | `0.439653846154` | `0.209115384615` | `True` | `False` |
| `baseline_density_sqrt_size_ridge_l0.1` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;pose_atom_count` | `0.1` | `0.627450980392` | `0.690476190476` | `0.660769230769` | `0.439461538462` | `0.208923076923` | `True` | `False` |
| `density_size_ridge_l10` | `contact_per_atom;pose_atom_count` | `10` | `0.622549019608` | `0.690476190476` | `0.646923076923` | `0.410730769231` | `0.180192307692` | `True` | `False` |
| `baseline_density_sqrt_size_ridge_l1` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;pose_atom_count` | `1` | `0.629901960784` | `0.690476190476` | `0.643846153846` | `0.386692307692` | `0.156153846154` | `True` | `False` |
| `descriptor_only_ridge_l10` | `contact_per_atom;contact_sqrt_norm;pose_atom_count;min_distance_a` | `10` | `0.654411764706` | `0.595238095238` | `0.65` | `0.365076923077` | `0.134538461538` | `False` | `False` |
| `baseline_contact_min_distance_ridge_l1` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;min_distance_a` | `1` | `0.588235294118` | `0.595238095238` | `0.606923076923` | `0.324269230769` | `0.0937307692308` | `False` | `False` |
| `baseline_contact_min_distance_ridge_l10` | `baseline_proxy;contact_per_atom;contact_sqrt_norm;min_distance_a` | `10` | `0.610294117647` | `0.52380952381` | `0.610769230769` | `0.323961538462` | `0.0934230769231` | `False` | `False` |

## Best Model Residuals

| target | pose | source | split | variant rank | reference rank | rank abs error |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `fit` | `2` | `16` | `14` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `fit` | `21` | `9` | `12` |
| `1gpk` | `1gpk_364` | `candidate_fill_preview` | `fit` | `10` | `19` | `9` |
| `4j28` | `4j28_123` | `candidate_fill_preview` | `holdout` | `24` | `15` | `9` |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `holdout` | `13` | `6` | `7` |
| `1syi` | `1syi_353` | `existing_materialized` | `holdout` | `12` | `18` | `6` |
| `3n7a` | `3n7a_955` | `candidate_fill_preview` | `holdout` | `17` | `23` | `6` |
| `4ivb` | `4ivb_253` | `candidate_fill_preview` | `fit` | `9` | `4` | `5` |
| `4ivc` | `4ivc_20` | `candidate_fill_preview` | `holdout` | `6` | `1` | `5` |
| `4k77` | `4k77_167` | `candidate_fill_preview` | `fit` | `15` | `10` | `5` |

## Claim Boundary

R9 fit-trained calibration probe only; it trains predeclared linear/ridge scoring hypotheses on the current fit split and reports holdout/public-benchmark diagnostics. It does not rewrite candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Treat the best fit-trained model as a near-threshold descriptor hypothesis only. Verify it on operator-reviewed metric-source payloads or an independent R9 holdout, then reduce remaining top rank residuals before any score mutation, payload write, canonical intake, or claim promotion.

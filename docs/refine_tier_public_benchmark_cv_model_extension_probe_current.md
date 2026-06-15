# R9 CV Model-Extension Probe

- status: `refine_tier_public_benchmark_cv_model_extension_probe_ready`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- locked_cv_bootstrap_p05_gap_to_claim_grade: `0.09642307692307689`
- extension_model_candidate_count: `35`
- material_extension_improvement_count: `0`
- claim_grade_extension_model_count: `0`
- best_extension_model_id: `density_size_quadratic_ridge_l1`
- best_extension_features: `contact_per_atom;pose_atom_count;contact_per_atom_sq;pose_atom_count_sq`
- best_extension_bootstrap_p05: `0.40449999999999997`
- best_extension_bootstrap_p05_delta_from_locked_cv: `0.0009230769230768598`
- best_extension_bootstrap_p05_gap_to_claim_grade: `0.09550000000000003`
- best_extension_material_p05_delta_ready: `False`
- best_extension_claim_grade_p05_ready: `False`
- model_extension_generalization_ready: `False`
- claim_promotion_allowed: `False`

## Top Extension Models

| model | features | lambda | holdout | combined | p05 | delta vs locked | material delta | claim-grade p05 | top residual |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `density_size_quadratic_ridge_l1` | `contact_per_atom;pose_atom_count;contact_per_atom_sq;pose_atom_count_sq` | `1` | `0.595238095238` | `0.633846153846` | `0.4045` | `0.000923076923077` | `False` | `False` | `3n86/14` |
| `density_size_ridge_l0.3` | `contact_per_atom;pose_atom_count` | `0.3` | `0.595238095238` | `0.636153846154` | `0.403576923077` | `` | `False` | `False` | `3n86/14` |
| `density_size_ridge_l0.1` | `contact_per_atom;pose_atom_count` | `0.1` | `0.595238095238` | `0.636153846154` | `0.403576923077` | `` | `False` | `False` | `3n86/14` |
| `density_size_quadratic_ridge_l3` | `contact_per_atom;pose_atom_count;contact_per_atom_sq;pose_atom_count_sq` | `3` | `0.595238095238` | `0.628461538462` | `0.399807692308` | `-0.00376923076923` | `False` | `False` | `3n86/14` |
| `density_size_min_distance_ridge_l1` | `contact_per_atom;pose_atom_count;min_distance_a` | `1` | `0.595238095238` | `0.608461538462` | `0.349730769231` | `-0.0538461538462` | `False` | `False` | `3n86/14` |
| `density_size_log_ridge_l1` | `contact_per_atom;pose_atom_count;log_contact_per_atom` | `1` | `0.595238095238` | `0.613076923077` | `0.3495` | `-0.0540769230769` | `False` | `False` | `3n86/14` |
| `density_size_min_distance_ridge_l0.3` | `contact_per_atom;pose_atom_count;min_distance_a` | `0.3` | `0.595238095238` | `0.606923076923` | `0.339230769231` | `-0.0643461538462` | `False` | `False` | `3n86/15` |
| `density_size_min_distance_ridge_l0.1` | `contact_per_atom;pose_atom_count;min_distance_a` | `0.1` | `0.595238095238` | `0.606923076923` | `0.339230769231` | `-0.0643461538462` | `False` | `False` | `3n86/15` |
| `density_size_ridge_l1` | `contact_per_atom;pose_atom_count` | `1` | `0.595238095238` | `0.597692307692` | `0.324423076923` | `-0.0791538461538` | `False` | `False` | `2j7h/14` |
| `density_size_log_ridge_l3` | `contact_per_atom;pose_atom_count;log_contact_per_atom` | `3` | `0.52380952381` | `0.586153846154` | `0.320346153846` | `-0.0832307692308` | `False` | `False` | `2j7h/14` |
| `density_size_quadratic_ridge_l0.3` | `contact_per_atom;pose_atom_count;contact_per_atom_sq;pose_atom_count_sq` | `0.3` | `0.52380952381` | `0.586153846154` | `0.315807692308` | `-0.0877692307692` | `False` | `False` | `2j7h/14` |
| `density_size_log_ridge_l0.3` | `contact_per_atom;pose_atom_count;log_contact_per_atom` | `0.3` | `0.52380952381` | `0.594615384615` | `0.312846153846` | `-0.0907307692308` | `False` | `False` | `3f3e/14` |

## Best Extension Residuals

| target | pose | source | split | variant rank | reference rank | rank abs error |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `fit` | `2` | `16` | `14` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `fit` | `22` | `9` | `13` |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `holdout` | `17` | `6` | `11` |
| `4j28` | `4j28_123` | `candidate_fill_preview` | `holdout` | `25` | `15` | `10` |
| `1gpk` | `1gpk_364` | `candidate_fill_preview` | `fit` | `11` | `19` | `8` |
| `3n7a` | `3n7a_955` | `candidate_fill_preview` | `holdout` | `16` | `23` | `7` |
| `3uo4` | `3uo4_374` | `candidate_fill_preview` | `fit` | `4` | `11` | `7` |
| `1syi` | `1syi_353` | `existing_materialized` | `holdout` | `12` | `18` | `6` |
| `4ivc` | `4ivc_20` | `candidate_fill_preview` | `holdout` | `7` | `1` | `6` |
| `4ivb` | `4ivb_253` | `candidate_fill_preview` | `fit` | `9` | `4` | `5` |
| `1nvq` | `1nvq_710` | `existing_materialized` | `holdout` | `1` | `5` | `4` |
| `4e5w` | `4e5w_121` | `existing_materialized` | `fit` | `3` | `7` | `4` |

## Claim Boundary

R9 CV model-extension probe only evaluates predeclared interaction/nonlinear descriptor hypotheses with leave-one-target-out diagnostics. It does not rewrite scores, write reviewed metric payloads, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Do not promote nonlinear/interaction extensions unless an extension clears claim-grade p05 and materially improves locked CV. Current failures should continue through reviewed metric payload, pose assignment, descriptor coverage, and independent holdout evidence before another calibration gate.

# R9 Residual Remediation Board

- status: `refine_tier_public_benchmark_residual_remediation_board_ready`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- locked_cv_bootstrap_p05_gap_to_claim_grade: `0.09642307692307689`
- locked_cv_holdout_non_degradation_ready: `False`
- remediation_action_row_count: `12`
- high_priority_action_row_count: `7`
- leave_one_out_leverage_row_count: `2`
- cv_worse_than_baseline_row_count: `5`
- required_reviewed_metric_payload_count_for_listed_rows: `36`
- claim_promotion_allowed: `False`

## Top Actions

| rank | target | pose | split | direction | cv err | baseline err | p05 delta if removed | action |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `1` | `3n86` | `3n86_99` | `fit` | `overranked_stronger_than_reference` | `14` | `13` | `-0.0358862876254` | `target_heldout_generalization_regression_review` |
| `2` | `2j7h` | `2j7h_48` | `fit` | `underranked_weaker_than_reference` | `13` | `16` | `0.0816789297659` | `underbinding_pose_contact_coverage_review` |
| `3` | `3f3e` | `3f3e_197` | `holdout` | `underranked_weaker_than_reference` | `11` | `18` | `0.124157190635` | `priority_metric_payload_and_pose_assignment_review` |
| `4` | `4j28` | `4j28_123` | `holdout` | `underranked_weaker_than_reference` | `10` | `1` | `-0.0320602006689` | `target_heldout_generalization_regression_review` |
| `5` | `1gpk` | `1gpk_364` | `fit` | `overranked_stronger_than_reference` | `9` | `5` | `-0.0867993311037` | `target_heldout_generalization_regression_review` |
| `6` | `3n7a` | `3n7a_955` | `holdout` | `overranked_stronger_than_reference` | `7` | `5` | `-0.058016722408` | `target_heldout_generalization_regression_review` |
| `7` | `1syi` | `1syi_353` | `holdout` | `overranked_stronger_than_reference` | `6` | `7` | `-0.0585819397993` | `overbinding_contact_density_inflation_review` |
| `8` | `3uo4` | `3uo4_374` | `fit` | `overranked_stronger_than_reference` | `6` | `7` | `-0.0794949832776` | `overbinding_contact_density_inflation_review` |
| `9` | `4ivc` | `4ivc_20` | `holdout` | `underranked_weaker_than_reference` | `6` | `6` | `-0.121929765886` | `underbinding_pose_contact_coverage_review` |
| `10` | `4ivb` | `4ivb_253` | `fit` | `underranked_weaker_than_reference` | `5` | `6` | `-0.0614080267559` | `underbinding_pose_contact_coverage_review` |
| `11` | `4k77` | `4k77_167` | `fit` | `underranked_weaker_than_reference` | `4` | `5` | `0.0146789297659` | `underbinding_pose_contact_coverage_review` |
| `12` | `4e5w` | `4e5w_121` | `fit` | `overranked_stronger_than_reference` | `4` | `1` | `-0.0289297658863` | `target_heldout_generalization_regression_review` |

## Claim Boundary

R9 residual remediation board only ranks target/pose residuals from existing read-only diagnostics and lists evidence needed before another calibration probe. It does not rewrite candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Review the listed residual targets with DockQ/lDDT-PLI/internal_deltaG payload evidence, then rerun candidate fill, cross-validation, and bootstrap gates. Do not promote the locked CV model while p05 and holdout non-degradation remain below claim-grade requirements.

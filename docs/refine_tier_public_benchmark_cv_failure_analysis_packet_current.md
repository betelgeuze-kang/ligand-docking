# R9 CV Failure Analysis Packet

- status: `refine_tier_public_benchmark_cv_failure_analysis_packet_ready`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- locked_cv_bootstrap_p05_gap_to_claim_grade: `0.09642307692307689`
- locked_cv_bootstrap_p05_drop_from_fit_trained: `0.0908461538461538`
- locked_cv_holdout_spearman_delta_from_baseline: `-0.04761904761904767`
- failure_row_count: `25`
- high_error_failure_row_count: `4`
- cv_regression_row_count: `9`
- holdout_high_error_row_count: `2`
- payload_priority_matched_failure_row_count: `12`
- operator_receipt_blocked_payload_count: `27`
- operator_receipt_missing_payload_count: `9`
- existing_metric_source_artifact_present_without_receipt_count: `9`
- top_failure_target_id: `3n86`
- top_failure_pose_id: `3n86_99`
- claim_promotion_allowed: `False`

## Top Failure Rows

| rank | target | pose | split | class | locked err | baseline err | delta | payloads | gaps | next step |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `1` | `3n86` | `3n86_99` | `fit` | `high_error_cv_regression_with_payload_review` | `14` | `13` | `1` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `2` | `2j7h` | `2j7h_48` | `fit` | `high_error_payload_review` | `13` | `16` | `-3` | `3` | `existing_metric_payload_present_without_operator_receipt:3` | `Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence.` |
| `3` | `3f3e` | `3f3e_197` | `holdout` | `high_error_payload_review` | `11` | `18` | `-7` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `4` | `4j28` | `4j28_123` | `holdout` | `high_error_cv_regression_with_payload_review` | `10` | `1` | `9` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `5` | `1gpk` | `1gpk_364` | `fit` | `cv_regression` | `9` | `5` | `4` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `6` | `3n7a` | `3n7a_955` | `holdout` | `cv_regression` | `7` | `5` | `2` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `7` | `4ivc` | `4ivc_20` | `holdout` | `monitor_after_payload_review` | `6` | `6` | `0` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `8` | `1syi` | `1syi_353` | `holdout` | `monitor_after_payload_review` | `6` | `7` | `-1` | `3` | `existing_metric_payload_present_without_operator_receipt:3` | `Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence.` |
| `9` | `3uo4` | `3uo4_374` | `fit` | `monitor_after_payload_review` | `6` | `7` | `-1` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `10` | `4ivb` | `4ivb_253` | `fit` | `monitor_after_payload_review` | `5` | `6` | `-1` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |
| `11` | `4e5w` | `4e5w_121` | `fit` | `cv_regression` | `4` | `1` | `3` | `3` | `existing_metric_payload_present_without_operator_receipt:3` | `Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence.` |
| `12` | `4k77` | `4k77_167` | `fit` | `monitor_after_payload_review` | `4` | `5` | `-1` | `3` | `operator_receipt_blocked_placeholders:3` | `Fill and review the blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose.` |

## Claim Boundary

R9 CV failure analysis packet only joins existing cross-validation residual diagnostics with metric-payload priority/receipt status to rank science follow-up work. It does not train models, rewrite scores, compute DockQ/lDDT/internal DeltaG, write reviewed metric payloads, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

- Resolve the top CV failure rows by reviewing their metric payloads/receipts and receptor-pose descriptor assignments, then rerun calibration cross-validation and bootstrap gates.

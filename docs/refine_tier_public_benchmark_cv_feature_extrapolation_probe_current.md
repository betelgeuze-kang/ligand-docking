# R9 CV Feature-Extrapolation Probe

- status: `refine_tier_public_benchmark_cv_feature_extrapolation_probe_ready`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_feature_names: `contact_per_atom;pose_atom_count`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- locked_cv_bootstrap_p05_gap_to_claim_grade: `0.09642307692307689`
- feature_extrapolation_probe_row_count: `25`
- high_error_row_count: `4`
- high_error_feature_extrapolation_count: `2`
- high_error_in_distribution_count: `2`
- feature_extrapolation_row_count: `3`
- feature_shift_warning_row_count: `5`
- operator_receipt_blocked_payload_count: `27`
- operator_receipt_missing_payload_count: `9`
- claim_promotion_allowed: `False`

## Top Rows

| rank | target | pose | split | class | cv err | delta | top feature | abs z | outside | gaps | next |
| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- | --- |
| `1` | `3n86` | `3n86_99` | `fit` | `high_error_in_distribution` | `14` | `1` | `contact_per_atom` | `1.2369728889` | `` | `operator_receipt_blocked_placeholders:3` | Prioritize metric payload, pose assignment, and model-form review; fold feature range alone does not explain the residual. |
| `2` | `2j7h` | `2j7h_48` | `fit` | `high_error_in_distribution` | `13` | `-3` | `pose_atom_count` | `1.42600493822` | `` | `existing_metric_payload_present_without_operator_receipt:3` | Add operator receipt coverage for existing metric-source JSON before using this row as reviewed evidence. |
| `3` | `3f3e` | `3f3e_197` | `holdout` | `high_error_feature_extrapolation` | `11` | `-7` | `contact_per_atom` | `2.51321120797` | `contact_per_atom` | `operator_receipt_blocked_placeholders:3` | Add/review target-held-out evidence near this feature range before adding stronger calibration terms. |
| `4` | `4j28` | `4j28_123` | `holdout` | `high_error_feature_extrapolation` | `10` | `9` | `contact_per_atom` | `1.5846358512` | `contact_per_atom` | `operator_receipt_blocked_placeholders:3` | Add/review target-held-out evidence near this feature range before adding stronger calibration terms. |
| `5` | `1gpk` | `1gpk_364` | `fit` | `cv_regression_in_distribution` | `9` | `4` | `contact_per_atom` | `0.320451047108` | `` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `6` | `3n7a` | `3n7a_955` | `holdout` | `cv_regression_in_distribution` | `7` | `2` | `pose_atom_count` | `1.08878270374` | `` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `7` | `4e5w` | `4e5w_121` | `fit` | `cv_regression_in_distribution` | `4` | `3` | `pose_atom_count` | `1.45372509611` | `` | `existing_metric_payload_present_without_operator_receipt:3` | Add operator receipt coverage for existing metric-source JSON before using this row as reviewed evidence. |
| `8` | `3dx1` | `3dx1_20` | `fit` | `cv_regression_in_distribution` | `3` | `1` | `pose_atom_count` | `1.60136699443` | `` | `` | Monitor after higher-priority residual and payload rows are closed. |
| `9` | `3b27` | `3b27_307` | `fit` | `cv_regression_in_distribution` | `3` | `3` | `contact_per_atom` | `0.882187896625` | `` | `` | Monitor after higher-priority residual and payload rows are closed. |
| `10` | `3fv1` | `3fv1_115` | `fit` | `cv_regression_in_distribution` | `3` | `2` | `contact_per_atom` | `0.747449863687` | `` | `` | Monitor after higher-priority residual and payload rows are closed. |
| `11` | `3bgz` | `3bgz_97` | `fit` | `cv_regression_in_distribution` | `2` | `1` | `contact_per_atom` | `1.22058124828` | `` | `` | Monitor after higher-priority residual and payload rows are closed. |
| `12` | `1syi` | `1syi_353` | `holdout` | `payload_receipt_gap_monitor` | `6` | `-1` | `contact_per_atom` | `0.488345492954` | `` | `existing_metric_payload_present_without_operator_receipt:3` | Add operator receipt coverage for existing metric-source JSON before using this row as reviewed evidence. |

## Claim Boundary

R9 CV feature-extrapolation probe only compares locked leave-one-target-out residual rows against the feature distribution available in each training fold. It does not train new production models, rewrite scores, write reviewed metric payloads, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Use feature-extrapolation rows to separate descriptor coverage gaps from in-distribution residuals; review top metric payloads and add independent/operator-reviewed evidence before rerunning CV and bootstrap gates. Do not promote scoring while p05 remains below 0.5 or payload receipts remain blocked.

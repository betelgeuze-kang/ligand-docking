# R9 Score-Variant Failure Decomposition

- status: `refine_tier_public_benchmark_score_variant_failure_decomposition_ready`
- best_variant_id: `sqrt_contact_density_only`
- best_variant_bootstrap_p05: `0.36630769230769233`
- best_variant_bootstrap_p05_gap_to_claim_grade: `0.13369230769230767`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- decomposition_row_count: `25`
- variant_improved/worsened/unchanged: `16/6/3`
- best_variant_high_error_row_count: `4`
- locked_cv_high_error_row_count: `4`
- persistent_high_error_row_count: `3`
- payload_priority_matched_row_count: `12`
- operator_receipt_blocked_payload_count: `27`
- operator_receipt_missing_payload_count: `9`

## Top Decomposition Rows

| rank | target | pose | split | class | baseline err | best err | best delta | cv err | cv delta | gaps | next |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `1` | `3n86` | `3n86_99` | `fit` | `score_variant_worsens_high_error` | `13` | `15` | `2` | `14` | `1` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `2` | `3f3e` | `3f3e_197` | `holdout` | `score_variant_improves_but_cv_high_error` | `18` | `13` | `-5` | `11` | `-7` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `3` | `2j7h` | `2j7h_48` | `fit` | `score_variant_improves_but_cv_high_error` | `16` | `13` | `-3` | `13` | `-3` | `existing_metric_payload_present_without_operator_receipt:3` | Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence. |
| `4` | `1gpk` | `1gpk_364` | `fit` | `score_variant_worsens_high_error` | `5` | `10` | `5` | `9` | `4` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `5` | `4j28` | `4j28_123` | `holdout` | `holdout_variant_cv_generalization_review` | `1` | `9` | `8` | `10` | `9` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `6` | `3n7a` | `3n7a_955` | `holdout` | `holdout_variant_cv_generalization_review` | `5` | `8` | `3` | `7` | `2` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `7` | `1syi` | `1syi_353` | `holdout` | `holdout_variant_cv_generalization_review` | `7` | `8` | `1` | `6` | `-1` | `existing_metric_payload_present_without_operator_receipt:3` | Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence. |
| `8` | `4ivc` | `4ivc_20` | `holdout` | `score_variant_improvement_monitor` | `6` | `4` | `-2` | `6` | `0` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `9` | `3uo4` | `3uo4_374` | `fit` | `score_variant_improvement_monitor` | `7` | `0` | `-7` | `6` | `-1` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `10` | `4ivb` | `4ivb_253` | `fit` | `score_variant_improvement_monitor` | `6` | `4` | `-2` | `5` | `-1` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `11` | `4k77` | `4k77_167` | `fit` | `score_variant_improvement_monitor` | `5` | `2` | `-3` | `4` | `-1` | `operator_receipt_blocked_placeholders:3` | Fill and review blocked DockQ/lDDT-PLI/internal_deltaG receipt rows for this target-pose. |
| `12` | `4e5w` | `4e5w_121` | `fit` | `cv_regression_after_score_variant` | `1` | `1` | `0` | `4` | `3` | `existing_metric_payload_present_without_operator_receipt:3` | Add operator receipt coverage for existing seeded metric JSON before treating it as reviewed evidence. |

## Claim Boundary

R9 score-variant failure decomposition only joins existing score-variant, cross-validation, and metric-payload priority packets to explain residual movement. It does not train models, rewrite scores, write reviewed metric payloads, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Use the top decomposition rows to decide whether the next R9 work is descriptor calibration or metric payload receipt review; keep claim promotion blocked until reviewed payload evidence and bootstrap p05 >= 0.5 are both true.

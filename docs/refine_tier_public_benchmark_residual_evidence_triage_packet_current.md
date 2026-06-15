# R9 Residual Evidence Triage Packet

- status: `refine_tier_public_benchmark_residual_evidence_triage_packet_ready`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- locked_cv_bootstrap_p05_gap_to_claim_grade: `0.09642307692307689`
- model_extension_generalization_ready: `False`
- triage_row_count: `12`
- in_distribution_high_error_triage_count: `1`
- feature_extrapolation_high_error_triage_count: `2`
- seeded_payload_receipt_gap_triage_count: `3`
- seeded_backfill_template_ready_triage_count: `3`
- seeded_backfill_template_ready_payload_count: `9`
- seeded_backfill_operator_manual_pending_field_count: `99`
- operator_receipt_blocked_payload_count: `27`
- operator_receipt_missing_payload_count: `9`
- claim_promotion_allowed: `False`

## Top Triage Rows

| rank | target | pose | lane | residual class | cv err | p05 delta if removed | payload gaps | next |
| ---: | --- | --- | --- | --- | ---: | ---: | --- | --- |
| `1` | `3n86` | `3n86_99` | `metric_payload_pose_model_form_review` | `high_error_in_distribution` | `14` | `-0.0358862876254` | `operator_receipt_blocked_placeholders:3` | Review metric payload values, pose assignment, and model-form assumptions; feature range alone does not explain this residual. |
| `2` | `3f3e` | `3f3e_197` | `descriptor_coverage_target_heldout_evidence` | `high_error_feature_extrapolation` | `11` | `0.124157190635` | `operator_receipt_blocked_placeholders:3` | Add target-held-out evidence or descriptor coverage near this feature range before stronger calibration terms. |
| `3` | `4j28` | `4j28_123` | `descriptor_coverage_target_heldout_evidence` | `high_error_feature_extrapolation` | `10` | `-0.0320602006689` | `operator_receipt_blocked_placeholders:3` | Add target-held-out evidence or descriptor coverage near this feature range before stronger calibration terms. |
| `4` | `2j7h` | `2j7h_48` | `seeded_payload_receipt_coverage_first` | `high_error_in_distribution` | `13` | `0.0816789297659` | `existing_metric_payload_present_without_operator_receipt:3` | Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage through a separate approved procedure. |
| `5` | `1syi` | `1syi_353` | `seeded_payload_receipt_coverage_first` | `payload_receipt_gap_monitor` | `6` | `-0.0585819397993` | `existing_metric_payload_present_without_operator_receipt:3` | Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage through a separate approved procedure. |
| `6` | `4e5w` | `4e5w_121` | `seeded_payload_receipt_coverage_first` | `cv_regression_in_distribution` | `4` | `-0.0289297658863` | `existing_metric_payload_present_without_operator_receipt:3` | Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage through a separate approved procedure. |
| `7` | `1gpk` | `1gpk_364` | `cv_regression_payload_review` | `cv_regression_in_distribution` | `9` | `-0.0867993311037` | `operator_receipt_blocked_placeholders:3` | Review CV regression payloads and fold scaling before another calibration attempt. |
| `8` | `3n7a` | `3n7a_955` | `cv_regression_payload_review` | `cv_regression_in_distribution` | `7` | `-0.058016722408` | `operator_receipt_blocked_placeholders:3` | Review CV regression payloads and fold scaling before another calibration attempt. |
| `9` | `4ivc` | `4ivc_20` | `blocked_receipt_fill` | `monitor` | `6` | `-0.121929765886` | `operator_receipt_blocked_placeholders:3` | Fill blocked metric-source receipt placeholders and keep claim promotion closed. |
| `10` | `3uo4` | `3uo4_374` | `blocked_receipt_fill` | `monitor` | `6` | `-0.0794949832776` | `operator_receipt_blocked_placeholders:3` | Fill blocked metric-source receipt placeholders and keep claim promotion closed. |
| `11` | `4ivb` | `4ivb_253` | `blocked_receipt_fill` | `monitor` | `5` | `-0.0614080267559` | `operator_receipt_blocked_placeholders:3` | Fill blocked metric-source receipt placeholders and keep claim promotion closed. |
| `12` | `4k77` | `4k77_167` | `blocked_receipt_fill` | `monitor` | `4` | `0.0146789297659` | `operator_receipt_blocked_placeholders:3` | Fill blocked metric-source receipt placeholders and keep claim promotion closed. |

## Claim Boundary

R9 residual evidence triage packet only joins existing residual, feature-extrapolation, model-extension, and metric-payload priority artifacts to choose the next review lane per target/pose. It does not compute metrics, write metric payload JSON, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Use this target/pose triage to close the highest-leverage R9 evidence lanes: review in-distribution metric payload and pose/model-form rows first, add seeded-payload receipt coverage where JSON already exists, and add descriptor coverage for feature-extrapolation rows before rerunning CV/bootstrap gates.

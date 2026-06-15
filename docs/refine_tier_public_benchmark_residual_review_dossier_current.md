# R9 Residual Review Dossier

- status: `refine_tier_public_benchmark_residual_review_dossier_ready`
- dossier_row_count: `6`
- review_package_ready_count: `6`
- metric_payload_pose_model_review_count: `1`
- descriptor_coverage_target_heldout_review_count: `2`
- seeded_backfill_review_count: `3`
- seeded_backfill_template_ready_review_count: `3`
- operator_receipt_blocked_payload_count: `9`
- operator_receipt_missing_payload_count: `9`
- seeded_backfill_operator_manual_pending_field_count: `99`
- claim_promotion_allowed: `False`

## Target-Pose Dossiers

| rank | target | pose | lane | package ready | residual class | metric rows | artifacts present | next action |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | --- |
| `1` | `3n86` | `3n86_99` | `metric_payload_pose_model_form_review` | `True` | `high_error_in_distribution` | `3` | `2/2` | Review DockQ/lDDT-PLI/internal_deltaG values, methods, input hashes, pose assignment, and model-form assumptions before changing calibration. |
| `2` | `3f3e` | `3f3e_197` | `descriptor_coverage_target_heldout_evidence` | `True` | `high_error_feature_extrapolation` | `3` | `2/2` | Review descriptor range diagnostics and add target-held-out evidence near the out-of-range feature before stronger calibration terms. |
| `3` | `4j28` | `4j28_123` | `descriptor_coverage_target_heldout_evidence` | `True` | `high_error_feature_extrapolation` | `3` | `2/2` | Review descriptor range diagnostics and add target-held-out evidence near the out-of-range feature before stronger calibration terms. |
| `4` | `2j7h` | `2j7h_48` | `seeded_payload_receipt_coverage_first` | `True` | `high_error_in_distribution` | `3` | `3/3` | Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage through a separate approved procedure. |
| `5` | `1syi` | `1syi_353` | `seeded_payload_receipt_coverage_first` | `True` | `payload_receipt_gap_monitor` | `3` | `3/3` | Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage through a separate approved procedure. |
| `6` | `4e5w` | `4e5w_121` | `seeded_payload_receipt_coverage_first` | `True` | `cv_regression_in_distribution` | `3` | `3/3` | Review the generated seeded-payload backfill template rows, then extend canonical receipt coverage through a separate approved procedure. |

## Claim Boundary

R9 residual review dossier only joins existing triage, metric-payload priority, feature-extrapolation, and seeded-backfill artifacts into target-pose review packages. It does not compute metrics, write metric payload JSON, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Use these target-pose dossiers as the immediate R9 science-review queue: top metric/pose/model-form review first, feature-extrapolation coverage second, and seeded backfill template review third.

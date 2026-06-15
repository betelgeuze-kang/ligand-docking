# R9 Bootstrap Driver Operator Machine Prefill Template

- status: `refine_tier_public_benchmark_bootstrap_driver_operator_machine_prefill_template_ready`
- prefill_row_count: `6`
- machine_supported_prefilled_field_count: `36`
- remaining_pending_field_count: `30`
- operator_only_remaining_field_count: `30`
- machine_remaining_field_count: `0`
- unclassified_remaining_field_count: `0`
- remaining_placeholder_row_count: `6`
- approval_token_required: `APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`
- canonical_worksheet_edited: `False`
- claim_promotion_allowed: `False`

## Rows

| worksheet | target | pose | metric | prefilled | remaining | operator-only remaining |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `r9_bootstrap_driver_operator_review_001` | `3f3e` | `3f3e_197` | `dockq` | `6` | `5` | `5` |
| `r9_bootstrap_driver_operator_review_002` | `3f3e` | `3f3e_197` | `internal_deltaG` | `6` | `5` | `5` |
| `r9_bootstrap_driver_operator_review_003` | `3f3e` | `3f3e_197` | `lddt_pli` | `6` | `5` | `5` |
| `r9_bootstrap_driver_operator_review_004` | `2j7h` | `2j7h_48` | `dockq` | `6` | `5` | `5` |
| `r9_bootstrap_driver_operator_review_005` | `2j7h` | `2j7h_48` | `lddt_pli` | `6` | `5` | `5` |
| `r9_bootstrap_driver_operator_review_006` | `2j7h` | `2j7h_48` | `internal_deltaG` | `6` | `5` | `5` |

## Claim Boundary

R9 bootstrap-driver operator machine prefill template only creates a separate candidate worksheet CSV where machine-supported review-confirmation fields are prefilled from current local evidence. It leaves operator decision, license review, operator identity, timestamp, and approval token as operator-only placeholders. It does not edit the canonical worksheet, mark operator approval, write metric payload JSON, copy canonical receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Use the prefilled candidate worksheet for operator review only: record accept/reject, license_ok, operator_id, reviewed_at_utc, and the approval token, then rerun the staging apply preview before any payload or canonical receipt write.

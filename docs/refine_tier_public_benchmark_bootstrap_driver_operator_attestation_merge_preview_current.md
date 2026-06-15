# R9 Bootstrap Driver Operator Attestation Merge Preview

- status: `blocked_refine_tier_public_benchmark_bootstrap_driver_operator_attestation_merge_preview`
- attestation_merge_ready: `False`
- rows pass/blocked/total: `0/6/6`
- prefill_row_fingerprint_verified_count: `6`
- prefill_row_fingerprint_mismatch_count: `0`
- merged_candidate_row_count: `0`
- approval_token_required: `APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`
- payload_write_allowed: `False`
- canonical_receipt_write_allowed: `False`
- claim_promotion_allowed: `False`
- most_common_row_blocker: `operator_only_placeholders_unfilled`

## Blockers
- `blocked_attestation_rows_present`

## Rows

| merge | target | pose | metric | fingerprint | status | blockers |
| --- | --- | --- | --- | --- | --- | --- |
| `r9_bootstrap_driver_operator_attestation_merge_001` | `3f3e` | `3f3e_197` | `dockq` | `True` | `blocked` | `operator_only_placeholders_unfilled;operator_decision_missing_or_not_accept;license_review_not_true;operator_id_missing;reviewed_at_utc_missing_or_invalid;approval_token_missing_or_invalid` |
| `r9_bootstrap_driver_operator_attestation_merge_002` | `3f3e` | `3f3e_197` | `internal_deltaG` | `True` | `blocked` | `operator_only_placeholders_unfilled;operator_decision_missing_or_not_accept;license_review_not_true;operator_id_missing;reviewed_at_utc_missing_or_invalid;approval_token_missing_or_invalid` |
| `r9_bootstrap_driver_operator_attestation_merge_003` | `3f3e` | `3f3e_197` | `lddt_pli` | `True` | `blocked` | `operator_only_placeholders_unfilled;operator_decision_missing_or_not_accept;license_review_not_true;operator_id_missing;reviewed_at_utc_missing_or_invalid;approval_token_missing_or_invalid` |
| `r9_bootstrap_driver_operator_attestation_merge_004` | `2j7h` | `2j7h_48` | `dockq` | `True` | `blocked` | `operator_only_placeholders_unfilled;operator_decision_missing_or_not_accept;license_review_not_true;operator_id_missing;reviewed_at_utc_missing_or_invalid;approval_token_missing_or_invalid` |
| `r9_bootstrap_driver_operator_attestation_merge_005` | `2j7h` | `2j7h_48` | `lddt_pli` | `True` | `blocked` | `operator_only_placeholders_unfilled;operator_decision_missing_or_not_accept;license_review_not_true;operator_id_missing;reviewed_at_utc_missing_or_invalid;approval_token_missing_or_invalid` |
| `r9_bootstrap_driver_operator_attestation_merge_006` | `2j7h` | `2j7h_48` | `internal_deltaG` | `True` | `blocked` | `operator_only_placeholders_unfilled;operator_decision_missing_or_not_accept;license_review_not_true;operator_id_missing;reviewed_at_utc_missing_or_invalid;approval_token_missing_or_invalid` |

## Claim Boundary

R9 bootstrap-driver operator attestation merge preview validates operator-only attestations against machine-prefill row fingerprints and builds a separate merged candidate worksheet only for passing rows. It does not edit the canonical worksheet, write metric payload JSON, copy canonical receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Fill all operator attestation rows, verify prefill fingerprints, then use the merged candidate worksheet as the input to the staging apply preview before any payload or canonical receipt write.

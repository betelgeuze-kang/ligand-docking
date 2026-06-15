# R9 Bootstrap Driver Operator Attestation Template

- status: `refine_tier_public_benchmark_bootstrap_driver_operator_attestation_template_ready`
- attestation_row_count: `6`
- attestation pass/blocked: `0/6`
- operator_only_pending_field_count: `30`
- machine_prefilled_field_count: `36`
- prefill_row_fingerprint_count: `6`
- approval_ready: `False`
- approval_token_required: `APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`
- payload_write_allowed: `False`
- claim_promotion_allowed: `False`
- most_common_row_blocker: `operator_only_fields_pending`

## Rows

| attestation | target | pose | metric | status | pending | fingerprint |
| --- | --- | --- | --- | --- | ---: | --- |
| `r9_bootstrap_driver_operator_attestation_001` | `3f3e` | `3f3e_197` | `dockq` | `blocked` | `5` | `79e5455951a5f07be1ded03186827bea88922ec13d7f58d99852b6f0497e4a5f` |
| `r9_bootstrap_driver_operator_attestation_002` | `3f3e` | `3f3e_197` | `internal_deltaG` | `blocked` | `5` | `79b86c1dad4c47975404191d5481da5c73dc0816e4b9e39197004861f2d20a1e` |
| `r9_bootstrap_driver_operator_attestation_003` | `3f3e` | `3f3e_197` | `lddt_pli` | `blocked` | `5` | `f3e0ff616df4aa8f8ea9a88aa7eeedc21730f8e57a259df6ee34ad03ab71fc4a` |
| `r9_bootstrap_driver_operator_attestation_004` | `2j7h` | `2j7h_48` | `dockq` | `blocked` | `5` | `fef5a383fa442587c2488ab04c45a5cfdb032fb56c10d8977ee63c2dd70e21aa` |
| `r9_bootstrap_driver_operator_attestation_005` | `2j7h` | `2j7h_48` | `lddt_pli` | `blocked` | `5` | `26e38df1e2b933c217d7516f0e9c142582de93c6ccb4f1289a1cccd65d217385` |
| `r9_bootstrap_driver_operator_attestation_006` | `2j7h` | `2j7h_48` | `internal_deltaG` | `blocked` | `5` | `c09500541b999902fbdd089a1b3c2927d2a86e461f8d08f53fe2b0679a6d125d` |

## Claim Boundary

R9 bootstrap-driver operator attestation template only extracts the remaining operator-only decision/license/operator identity/timestamp/approval fields from the machine-prefilled worksheet and pins each row to a prefill-row SHA-256 fingerprint. It does not edit the canonical worksheet, accept approvals, write metric payload JSON, copy canonical receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Operator fills the six attestation rows with accept/reject, license review, operator identity, review timestamp, and the approval token; then merge back into the machine-prefilled candidate worksheet and rerun staging apply before any payload or receipt write.

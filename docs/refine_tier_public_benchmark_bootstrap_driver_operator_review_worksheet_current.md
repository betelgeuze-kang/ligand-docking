# R9 Bootstrap Driver Operator Review Worksheet

- status: `refine_tier_public_benchmark_bootstrap_driver_operator_review_worksheet_ready`
- worksheet_row_count: `6`
- candidate_preview_review_row_count: `3`
- existing_payload_backfill_review_row_count: `3`
- candidate_preview_input_hash_verified_row_count: `3`
- existing_payload_validation_pass_row_count: `3`
- existing_payload_input_hash_verified_row_count: `3`
- operator_manual_pending_field_count: `66`
- approval_token_required: `APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`
- claim_promotion_allowed: `False`

## Worksheet Rows

| worksheet | target | pose | metric | surface | value | method | hash verified | pending fields |
| --- | --- | --- | --- | --- | ---: | --- | --- | ---: |
| `r9_bootstrap_driver_operator_review_001` | `3f3e` | `3f3e_197` | `dockq` | `candidate_preview_payload_write_review` | `0.733726` | `candidate_internal_ligand_pose_reference_dockq_proxy_v1` | `True` | `11` |
| `r9_bootstrap_driver_operator_review_002` | `3f3e` | `3f3e_197` | `internal_deltaG` | `candidate_preview_payload_write_review` | `-2.392981` | `candidate_internal_contact_shell_normalized_mm_gbsa_v2` | `True` | `11` |
| `r9_bootstrap_driver_operator_review_003` | `3f3e` | `3f3e_197` | `lddt_pli` | `candidate_preview_payload_write_review` | `1.000000` | `candidate_internal_ligand_pose_reference_lddt_pli_proxy_v1` | `True` | `11` |
| `r9_bootstrap_driver_operator_review_004` | `2j7h` | `2j7h_48` | `dockq` | `existing_payload_backfill_receipt_review` | `0.731168` | `internal_ligand_pose_reference_dockq_proxy_v1` | `True` | `11` |
| `r9_bootstrap_driver_operator_review_005` | `2j7h` | `2j7h_48` | `lddt_pli` | `existing_payload_backfill_receipt_review` | `1.0` | `internal_ligand_pose_reference_lddt_pli_proxy_v1` | `True` | `11` |
| `r9_bootstrap_driver_operator_review_006` | `2j7h` | `2j7h_48` | `internal_deltaG` | `existing_payload_backfill_receipt_review` | `-2.153397` | `internal_contact_normalized_mm_gbsa_v2` | `True` | `11` |

## Claim Boundary

R9 bootstrap driver operator review worksheet only expands the top bootstrap-driver evidence audit into metric-row review templates. It does not write metric source payload JSON, approve receipts, extend canonical receipt coverage, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Operator must review the six top-driver metric rows, confirm values/methods/input hashes/license, and provide the approval token in a separate approved procedure before any payload or receipt write.

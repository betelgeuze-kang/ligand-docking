# R9 Seeded Metric Payload Receipt Backfill Packet

- status: `refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_ready`
- locked_cv_model_id: `density_size_ridge_l0.1`
- locked_cv_bootstrap_p05: `0.4035769230769231`
- seeded_backfill_row_count: `9`
- seeded_backfill_target_count: `3`
- seeded_backfill_targets: `1syi;2j7h;4e5w`
- metric_source_artifact_present_count: `9`
- payload_schema_valid_count: `9`
- input_artifact_sha256_verified_row_count: `9`
- operator_manual_pending_field_count: `99`
- operator_receipt_backfill_ready: `False`
- canonical_receipt_write_allowed: `False`
- claim_promotion_allowed: `False`

## Backfill Rows

| rank | target | pose | metric | validation | value | method | pending fields |
| ---: | --- | --- | --- | --- | ---: | --- | ---: |
| `4` | `2j7h` | `2j7h_48` | `dockq` | `pass` | `0.731168` | `internal_ligand_pose_reference_dockq_proxy_v1` | `11` |
| `5` | `2j7h` | `2j7h_48` | `lddt_pli` | `pass` | `1.0` | `internal_ligand_pose_reference_lddt_pli_proxy_v1` | `11` |
| `6` | `2j7h` | `2j7h_48` | `internal_deltaG` | `pass` | `-2.153397` | `internal_contact_normalized_mm_gbsa_v2` | `11` |
| `19` | `1syi` | `1syi_353` | `dockq` | `pass` | `0.731514` | `internal_ligand_pose_reference_dockq_proxy_v1` | `11` |
| `20` | `1syi` | `1syi_353` | `lddt_pli` | `pass` | `1.0` | `internal_ligand_pose_reference_lddt_pli_proxy_v1` | `11` |
| `21` | `1syi` | `1syi_353` | `internal_deltaG` | `pass` | `-5.934925` | `internal_contact_normalized_mm_gbsa_v2` | `11` |
| `34` | `4e5w` | `4e5w_121` | `dockq` | `pass` | `0.731069` | `internal_ligand_pose_reference_dockq_proxy_v1` | `11` |
| `35` | `4e5w` | `4e5w_121` | `lddt_pli` | `pass` | `1.0` | `internal_ligand_pose_reference_lddt_pli_proxy_v1` | `11` |
| `36` | `4e5w` | `4e5w_121` | `internal_deltaG` | `pass` | `-7.432395` | `internal_contact_normalized_mm_gbsa_v2` | `11` |

## Claim Boundary

R9 seeded metric payload receipt backfill packet only validates existing local seeded metric JSON artifacts and emits an operator-fill template for missing receipt coverage. It does not modify the canonical operator receipt, write metric payload JSON, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Operator must review the backfill template rows, confirm existing seeded metric values, input artifacts, hashes, payload schema, license, and approval token, then use a separate explicit procedure to extend canonical receipt coverage. This packet does not write that canonical receipt.

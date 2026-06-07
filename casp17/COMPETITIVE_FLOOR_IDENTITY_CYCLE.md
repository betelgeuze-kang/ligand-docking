# CASP17 Competitive-Floor Identity Cycle

- generated: `2026-05-26T00:32:36+09:00`
- identity_cycle_status: `awaiting_intake`
- apply_sync/apply_identity/apply_import: `False/False/False`
- stages ready/blocked/total: `1/6/7`
- sync status: `awaiting_intake` rows synced/ready/awaiting/blocked `0/0/15/0` missing fields `60` applied `0`
- identity round: `awaiting_identity` ready/awaiting/blocked `0/15/0`
- file/value plans: `waiting_on_identity`/`waiting_on_identity`
- execution/readiness/workbench: `awaiting_identity`/`awaiting_identity`/`ready_for_operator_fill`
- first next action: fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle

## Cycle Stages

| stage | status | ready | awaiting | blocked | total | path | next action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `identity_sync` | `awaiting_intake` | 0 | 15 | 0 | 15 | `casp17/casp17_competitive_floor_identity_intake_sync_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| `identity_round` | `awaiting_identity` | 0 | 15 | 15 | 15 | `casp17/casp17_competitive_floor_identity_unlock_round_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the identity kit |
| `file_source_plan` | `waiting_on_identity` | 0 | 180 | 0 | 180 | `casp17/casp17_competitive_floor_file_source_plan_current.json` | fill and apply the compact identity unlock kit first |
| `value_entry_plan` | `waiting_on_identity` | 0 | 270 | 0 | 270 | `casp17/casp17_competitive_floor_value_entry_plan_current.json` | fill and apply the compact identity unlock kit first |
| `execution_board` | `awaiting_identity` | 0 | 15 | 0 | 15 | `casp17/casp17_competitive_floor_execution_board_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance |
| `readiness_gate` | `awaiting_identity` | 1 | 0 | 5 | 6 | `casp17/casp17_competitive_floor_readiness_gate_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance |
| `workbench` | `ready_for_operator_fill` | 16 | 0 | 0 | 16 | `casp17/casp17_workbench_index_current.json` | Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target. |

## Claim Boundary

Local CASP17 competitive-floor identity cycle only. It chains the existing identity intake sync, identity unlock round, identity-aware file/value plans, execution board, readiness gate, and workbench refresh. It does not choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv directly, copy evidence files unless downstream apply flags are explicitly provided, or submit to CASP.

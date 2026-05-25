# CASP17 Competitive-Floor Identity Unlock Round

- generated: `2026-05-26T00:32:36+09:00`
- identity_round_status: `awaiting_identity`
- apply_identity/apply_import: `False/False`
- rows: `15`
- identity ready/awaiting/blocked: `0/15/0`
- applied identity import cells: `0`
- import ready/applied: `0/0`
- identity open/target_id open: `30/15`
- file actions waiting on identity: `180`
- next action: fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the identity kit

## Round Stages

| stage | status | ready | awaiting | blocked | applied | path | next action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `identity_kit` | `awaiting_identity` | 0 | 15 | 0 | 0 | `casp17/casp17_competitive_floor_identity_unlock_kit_current.json` | proposed_benchmark_id_required,proposed_target_id_required,evidence_ref_required,operator_clearance_required |
| `evidence_import` | `awaiting_import` | 0 | 450 | 0 | 0 | `casp17/casp17_competitive_floor_evidence_import_current.json` | enter proposed_value, evidence_ref, and operator_clearance in the import CSV |
| `unlock_priority` | `identity_unlock_required` | 30 | 30 | 180 | 0 | `casp17/casp17_competitive_floor_evidence_unlock_priority_current.json` | fill benchmark_id and target_id values first; target_id unlocks canonical file recommendations |

## Claim Boundary

Local competitive-floor identity unlock round only. It chains the compact identity kit, evidence import audit/apply gate, and unlock-priority audit so cleared benchmark_id/target_id entries can be reviewed and applied consistently. It does not choose historical targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP.

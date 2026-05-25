# CASP17 Competitive-Floor Target Identity Clearance Cycle

- generated: `2026-05-26T02:22:43+09:00`
- clearance_cycle_status: `awaiting_provenance`
- apply_manifest_sync/apply_candidate_intake: `False/False`
- stages ready/blocked/total: `1/5/6`
- manifest sync: `awaiting_provenance` ready/awaiting/synced/applied `0/3/0/0`
- audit: `blocked` pass/blocked `0/3`
- promotion: `blocked_by_audit` promoted/blocked `0/3`
- intake staging: `waiting_on_promoted_manifest` staged/blocked `0/0`
- candidate intake sync: `waiting_on_staged_identity` ready/waiting/applied `0/15/0`
- workbench: `ready_for_operator_fill`
- first next action: complete the no-leak provenance template before syncing the manifest stub

## Cycle Stages

| stage | status | ready | awaiting | blocked | total | path | next action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `manifest_sync` | `awaiting_provenance` | 0 | 3 | 0 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json` | complete the no-leak provenance template before syncing the manifest stub |
| `workorder_audit` | `blocked` | 0 | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json` | place the cleared native PDB in the per-target native dropzone |
| `promotion_plan` | `blocked_by_audit` | 0 | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json` | clear the native/provenance workorder audit before promotion |
| `intake_staging` | `waiting_on_promoted_manifest` | 0 | 0 | 0 | 0 | `casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.json` | wait for promoted clearance manifest rows |
| `candidate_intake_sync` | `waiting_on_staged_identity` | 0 | 15 | 0 | 15 | `casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.json` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `workbench` | `ready_for_operator_fill` | 16 | 0 | 0 | 16 | `casp17/casp17_workbench_index_current.json` | Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target. |

## Claim Boundary

Local CASP17 competitive-floor target identity clearance cycle only. It chains manifest-stub sync, workorder audit, audited manifest promotion, clearance-to-intake staging, and workbench refresh. It does not rebuild workorders, fetch native structures, clear no-leak provenance, choose targets, score native accuracy, run predictors, mutate live identity intake files, or submit to CASP. Manifest stubs are modified only when --apply-manifest-sync is explicitly provided; live identity intake is modified only when --apply-candidate-intake is explicitly provided.

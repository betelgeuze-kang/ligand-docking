# CASP17 Competitive-Floor Target Identity Clearance Cycle

- generated: `2026-05-26T04:08:51+09:00`
- clearance_cycle_status: `awaiting_operator_intake`
- apply_operator_intake/apply_manifest_sync/apply_candidate_intake: `False/False/False`
- stages ready/blocked/total: `1/8/9`
- operator intake: `awaiting_input` ready/awaiting/blocked/applied `0/3/0/0` native/provenance applied `0/0`
- manifest sync: `awaiting_provenance` ready/awaiting/synced/applied `0/3/0/0`
- audit: `blocked` pass/blocked `0/3`
- action board: `open_actions` actions/open `12/12`
- action bundle: `open_actions` actions/open/files/folders `12/12/24/12`
- promotion: `blocked_by_audit` promoted/blocked `0/3`
- intake staging: `waiting_on_promoted_manifest` staged/blocked `0/0`
- candidate intake sync: `waiting_on_staged_identity` ready/waiting/applied `0/15/0`
- workbench: `ready_for_operator_fill`
- first next action: fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls

## Cycle Stages

| stage | status | ready | awaiting | blocked | total | path | next action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `operator_intake` | `awaiting_input` | 0 | 3 | 0 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.json` | fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls |
| `manifest_sync` | `awaiting_provenance` | 0 | 3 | 0 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json` | complete the no-leak provenance template before syncing the manifest stub |
| `workorder_audit` | `blocked` | 0 | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json` | complete target-origin and no-leak evidence review before native/provenance promotion |
| `action_board` | `open_actions` | 0 | 0 | 12 | 12 | `casp17/casp17_competitive_floor_target_identity_clearance_action_board_current.json` | Place an operator-cleared native protein PDB in the native dropzone; ensure it is distinct from the prediction and has valid ATOM coordinates. |
| `action_bundle` | `open_actions` | 0 | 0 | 12 | 12 | `casp17/casp17_competitive_floor_target_identity_clearance_action_bundle_current.json` | casp17/competitive_floor_target_identity_clearance_action_bundle/H1319_Human_astrovirus_VA1_capsid_spike_-_antibody_7C8_complex/action_001_native_dropzone/ACTION.md |
| `promotion_plan` | `blocked_by_audit` | 0 | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json` | clear the native/provenance workorder audit before promotion |
| `intake_staging` | `waiting_on_promoted_manifest` | 0 | 0 | 0 | 0 | `casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.json` | wait for promoted clearance manifest rows |
| `candidate_intake_sync` | `waiting_on_staged_identity` | 0 | 15 | 0 | 15 | `casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.json` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `workbench` | `ready_for_operator_fill` | 16 | 0 | 0 | 16 | `casp17/casp17_workbench_index_current.json` | Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target. |

## Claim Boundary

Local CASP17 competitive-floor target identity clearance cycle only. It chains operator intake validation, manifest-stub sync, workorder audit, action-board expansion, action-bundle materialization, audited manifest promotion, clearance-to-intake staging, and workbench refresh. It does not rebuild workorders, fetch native structures, clear no-leak provenance, choose targets, score native accuracy, run predictors, mutate live identity intake files, or submit to CASP. Native/provenance workorders are modified only when --apply-operator-intake is explicitly provided; manifest stubs are modified only when --apply-manifest-sync is explicitly provided; live identity intake is modified only when --apply-candidate-intake is explicitly provided.

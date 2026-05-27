# CASP17 Replacement Decision Preflight

- generated: `2026-05-28T01:34:05+09:00`
- decision_preflight_status: `awaiting_operator_decision`
- decision_bundle_status: `open_operator_decision`
- decisions ready-new/ready-duplicate/awaiting/conflict/total: `0/0/1/0/1`
- blocker rows new-unique/duplicate-exception: `1/1`
- first open: `H1321`
- first next action: fill either the new unique candidate intake or the duplicate reuse exception, then rerun this preflight

## Preflight Rows

| replace | preflight | new unique | duplicate exception | ready branch | next action | blockers |
| --- | --- | --- | --- | --- | --- | --- |
| `H1321` | `awaiting_operator_decision` | `awaiting_operator_input` | `awaiting_operator_input` | `-` | fill either the new unique candidate intake or the duplicate reuse exception, then rerun this preflight | `proposed_candidate_target_id_required,proposed_candidate_name_required,closed_protein_target_required,current_target_collision_checked_required,cancellation_checked_required,local_prediction_pdb_required,raw_validation_json_required,scorecard_json_required,no_leak_evidence_ref_required,operator_clearance_required,operator_required,local_prediction_pdb_not_found,raw_validation_json_not_found,scorecard_json_not_found;allow_duplicate_reuse_required,no_leak_evidence_ref_required,operator_clearance_required,operator_required,approval_date_required,rationale_required` |

## Claim Boundary

Local CASP17 replacement decision preflight only. It validates whether a filled replacement decision bundle contains either a safe new unique candidate path or an explicit duplicate-reuse exception. It does not choose targets, approve exceptions, fetch native structures, clear no-leak provenance, mutate replacement workorders, score native accuracy, or submit to CASP.

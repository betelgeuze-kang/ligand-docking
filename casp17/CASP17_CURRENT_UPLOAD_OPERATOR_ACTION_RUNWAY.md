# CASP17 Current Upload Operator Action Runway

- status: `current_upload_operator_action_runway_ready_for_human_decisions`
- active/technical/blocked: `8/8/0`
- operator/author/runtime-ready: `8/0/0`
- urgency today/soon/future: `2/4/2`
- first action: `H1344` `operator_decision_required` `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` `operator_decision_missing`
- fill surface: `casp17/current_upload_operator_decision_kit/operator_decision_intake.csv`
- next action: start with H1344; enter approve, hold, or reject in the active operator decision intake row

## Claim Boundary

CASP17 current upload operator action runway only. It merges the active decision-rule gate, operator decision kit, completion audit, and active-manifest lock into a human fill plan. It does not enter approve/hold/reject decisions, serialize a CASP author code, create final upload files, submit to CASP, compute native accuracy, or mark strict-blind competitive proof.

## Action Rows

| rank | target | urgency | action status | required fields | blockers | decision file |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `H1344` | `today` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/01_h1344/DECISION.md` |
| 2 | `H2321` | `today` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/02_h2321/DECISION.md` |
| 3 | `H1346` | `soon` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/03_h1346/DECISION.md` |
| 4 | `H1347` | `soon` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/04_h1347/DECISION.md` |
| 5 | `H1348` | `soon` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/05_h1348/DECISION.md` |
| 6 | `H1349` | `soon` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/06_h1349/DECISION.md` |
| 7 | `H1354` | `future` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/07_h1354/DECISION.md` |
| 8 | `H1355` | `future` | `operator_decision_required` | `operator_decision,operator_id,operator_decision_ref,operator_notes_optional` | `operator_decision_missing` | `casp17/current_upload_operator_decision_kit/08_h1355/DECISION.md` |

## Source Files

- decision_rule_gate_json: `casp17/casp17_current_upload_decision_rule_gate_current.json`
- operator_decision_kit_json: `casp17/casp17_current_upload_operator_decision_kit_current.json`
- operator_decision_kit_completion_audit_json: `casp17/casp17_current_upload_operator_decision_kit_completion_audit_current.json`
- active_manifest_lock_json: `casp17/casp17_current_upload_active_manifest_lock_current.json`

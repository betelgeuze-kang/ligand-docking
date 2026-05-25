# CASP17 Target Identity Clearance Operator Intake

- generated: `2026-05-26T04:08:51+09:00`
- operator_intake_status: `awaiting_input`
- apply_mode: `dry_run`
- intake_csv: `casp17/casp17_competitive_floor_target_identity_clearance_operator_intake_current.csv`
- rows ready/awaiting/blocked/applied: `0/3/0/0`
- native ready/copied: `0/0`
- provenance ready/patched: `0/0`
- first open: `H1319` `awaiting_input`
- first next action: fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls

## Intake Rows

| target | status | native | provenance | evidence | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- |
| `H1319` | `awaiting_input` | `waiting_on_input` | `waiting_on_input` | `-` | `native_source_pdb_required,no_leak_evidence_ref_required,operator_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` | fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls |
| `H1321` | `awaiting_input` | `waiting_on_input` | `waiting_on_input` | `-` | `native_source_pdb_required,no_leak_evidence_ref_required,operator_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` | fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls |
| `H2324` | `awaiting_input` | `waiting_on_input` | `waiting_on_input` | `-` | `native_source_pdb_required,no_leak_evidence_ref_required,operator_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` | fill native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls |

## Claim Boundary

Local CASP17 competitive-floor target identity clearance operator intake only. It validates operator-supplied native PDB paths, no-leak evidence refs, provenance dates, and true/false provenance controls before optional local workorder patching. It does not fetch native structures, clear no-leak provenance, trust external URLs, score native accuracy, mutate identity intake files, or submit to CASP.

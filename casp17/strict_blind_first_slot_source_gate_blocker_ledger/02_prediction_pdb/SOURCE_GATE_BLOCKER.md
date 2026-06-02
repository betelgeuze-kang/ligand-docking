# prediction_pdb Source Gate Blocker

- ledger_rank: `2`
- status: `blocked_source_gate_field`
- priority_class: `02_prediction_file`
- affected_check_ids: `manifest_prediction_pdb_present,manifest_prediction_pdb_exists,prediction_pdb_has_atom_records`
- gate_blockers: `prediction_pdb_missing,prediction_pdb_not_found,prediction_pdb_has_no_atom_records`
- review_first_blocker: `template_operator_value_missing`
- file_status: `file_path_missing`
- evidence_stub_md: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_pdb.md`
- next_action: fill operator_value for prediction_pdb in operator_evidence_template.csv

## Claim Boundary

Local CASP17 strict-blind first-slot source-gate blocker ledger only. It merges source-gate checks, field actions, operator packet state, and first-unlock evidence review state into one closure ledger. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

# prediction_pdb_dropzone Source Gate Blocker

- ledger_rank: `3`
- status: `blocked_source_gate_field`
- priority_class: `03_prediction_dropzone_copy`
- affected_check_ids: `dropzone_prediction_pdb_exists`
- gate_blockers: `dropzone_prediction_pdb_missing`
- review_first_blocker: `template_operator_value_missing`
- file_status: `file_path_missing`
- evidence_stub_md: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_pdb_dropzone.md`
- next_action: fill operator_value for prediction_pdb_dropzone in operator_evidence_template.csv

## Claim Boundary

Local CASP17 strict-blind first-slot source-gate blocker ledger only. It merges source-gate checks, field actions, operator packet state, and first-unlock evidence review state into one closure ledger. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

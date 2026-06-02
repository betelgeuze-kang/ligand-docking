# source_id Source Gate Blocker

- ledger_rank: `1`
- status: `blocked_source_gate_field`
- priority_class: `01_source_identity`
- affected_check_ids: `source_id_internal`
- gate_blockers: `internal_source_id_missing_or_external`
- review_first_blocker: `template_operator_value_missing`
- file_status: `file_not_required`
- evidence_stub_md: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/source_id.md`
- next_action: fill operator_value for source_id in operator_evidence_template.csv

## Claim Boundary

Local CASP17 strict-blind first-slot source-gate blocker ledger only. It merges source-gate checks, field actions, operator packet state, and first-unlock evidence review state into one closure ledger. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

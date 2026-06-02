# native_authority_ref Source Gate Blocker

- ledger_rank: `7`
- status: `blocked_source_gate_field`
- priority_class: `05_native_authority`
- affected_check_ids: `native_authority_ref_present`
- gate_blockers: `native_authority_ref_missing`
- review_first_blocker: `template_operator_value_missing`
- file_status: `file_not_required`
- evidence_stub_md: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/native_authority_ref.md`
- next_action: fill operator_value for native_authority_ref in operator_evidence_template.csv

## Claim Boundary

Local CASP17 strict-blind first-slot source-gate blocker ledger only. It merges source-gate checks, field actions, operator packet state, and first-unlock evidence review state into one closure ledger. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

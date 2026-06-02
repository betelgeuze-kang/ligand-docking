# native_release_date Source Gate Blocker

- ledger_rank: `4`
- status: `blocked_source_gate_field`
- priority_class: `04_chronology`
- affected_check_ids: `native_release_date_present`
- gate_blockers: `native_release_date_missing_or_invalid`
- review_first_blocker: `template_operator_value_missing`
- file_status: `file_not_required`
- evidence_stub_md: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/native_release_date.md`
- next_action: fill operator_value for native_release_date in operator_evidence_template.csv

## Claim Boundary

Local CASP17 strict-blind first-slot source-gate blocker ledger only. It merges source-gate checks, field actions, operator packet state, and first-unlock evidence review state into one closure ledger. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

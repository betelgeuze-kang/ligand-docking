# CASP17 Strict-Blind First Unlock Evidence Action

- status: `awaiting_first_unlock_evidence_collection`
- request/target: `source_request_001` `HIST_BBA5`
- fields ready/open/total: `0/11/11`
- first open field: `source_id` `operator_value_missing`
- next action: collect evidence in casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/source_id.md, then fill operator_value and operator_evidence_ref for source_id
- operator evidence template: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/operator_evidence_template.csv`
- dropzone manifest: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/dropzone_manifest.csv`

## Claim Boundary

Local CASP17 strict-blind first-unlock evidence packet only. It creates operator-facing evidence stubs and templates for the first source-request handoff. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

# Evidence Stub: creation_evidence_ref

- field: `creation_evidence_ref`
- evidence kind: `prediction_timestamp_evidence`
- status: `awaiting_operator_evidence`
- blocker: `operator_value_missing`
- required format: `artifact path or URI for independent prediction timestamp evidence`
- accepted evidence examples: immutable run manifest; lab notebook; archived CI/job metadata
- rejected sources: mtime only; generated markdown after the fact; operator memory only
- destination: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- next action: collect evidence in casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/creation_evidence_ref.md, then fill operator_value and operator_evidence_ref for creation_evidence_ref

## Operator Evidence

- operator_value:
- operator_evidence_ref:
- operator_clearance:
- operator_id:

## Claim Boundary

Local CASP17 strict-blind first-unlock evidence packet only. It creates operator-facing evidence stubs and templates for the first source-request handoff. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

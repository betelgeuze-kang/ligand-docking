# Evidence Stub: prediction_created_at

- field: `prediction_created_at`
- evidence kind: `authoritative_prediction_creation_date`
- status: `awaiting_operator_evidence`
- blocker: `operator_value_missing`
- required format: `YYYY-MM-DD prediction creation date`
- accepted evidence examples: immutable job ledger; archived run manifest; signed lab notebook entry
- rejected sources: current file mtime only; copied folder date; after-native date
- destination: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- next action: collect evidence in casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_created_at.md, then fill operator_value and operator_evidence_ref for prediction_created_at

## Operator Evidence

- operator_value:
- operator_evidence_ref:
- operator_clearance:
- operator_id:

## Claim Boundary

Local CASP17 strict-blind first-unlock evidence packet only. It creates operator-facing evidence stubs and templates for the first source-request handoff. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

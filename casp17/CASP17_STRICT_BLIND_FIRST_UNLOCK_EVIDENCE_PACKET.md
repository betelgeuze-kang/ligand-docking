# CASP17 Strict-Blind First Unlock Evidence Packet

- generated: `2026-06-01T21:07:17+09:00`
- status: `awaiting_first_unlock_evidence_collection`
- request/target: `source_request_001` `HIST_BBA5`
- fields ready/open/total: `0/11/11`
- file fields: `2`
- first open field: `source_id` `operator_value_missing`
- next action: collect evidence in casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/source_id.md, then fill operator_value and operator_evidence_ref for source_id
- packet folder: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5`
- operator evidence template: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/operator_evidence_template.csv`
- dropzone manifest: `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/dropzone_manifest.csv`

## Fields

| order | field | evidence kind | status | blocker | stub |
| ---: | --- | --- | --- | --- | --- |
| 1 | `source_id` | `internal_source_identifier` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/source_id.md` |
| 2 | `prediction_pdb` | `pre_native_prediction_pdb` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_pdb.md` |
| 3 | `prediction_pdb_dropzone` | `verified_prediction_dropzone_copy` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_pdb_dropzone.md` |
| 4 | `prediction_created_at` | `authoritative_prediction_creation_date` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_created_at.md` |
| 5 | `native_release_date` | `authoritative_native_release_date` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/native_release_date.md` |
| 6 | `prediction_created_at/native_release_date` | `chronology_comparison` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/prediction_created_at_native_release_date.md` |
| 7 | `native_authority_ref` | `native_authority_reference` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/native_authority_ref.md` |
| 8 | `creation_evidence_ref` | `prediction_timestamp_evidence` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/creation_evidence_ref.md` |
| 9 | `no_leak_evidence_ref` | `no_leak_provenance_evidence` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/no_leak_evidence_ref.md` |
| 10 | `method_summary` | `method_source_summary` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/method_summary.md` |
| 11 | `operator_clearance` | `operator_signoff` | `awaiting_operator_evidence` | `operator_value_missing` | `casp17/strict_blind_first_unlock_evidence_packet/source_request_001_hist_bba5/field_evidence/operator_clearance.md` |

## Claim Boundary

Local CASP17 strict-blind first-unlock evidence packet only. It creates operator-facing evidence stubs and templates for the first source-request handoff. It does not fill operator values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

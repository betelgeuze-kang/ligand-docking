# source_request_008 Strict-Blind Source Request Fill

- target: `HIST_UBIQUITIN_MINI`
- scope: `monomer`
- request kind: `pre_native_prediction_source_required`
- fields ready/blocked/total: `0/11/11`
- missing value/evidence: `11/9`
- first field: `source_id` `operator_value_missing`

## Fields

| field | status | value | evidence | source template |
| --- | --- | --- | --- | --- |
| `source_id` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `prediction_pdb` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `prediction_pdb_dropzone` | `awaiting_operator_value` | `operator_value_missing` | `evidence_not_required` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `prediction_created_at` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `native_release_date` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `prediction_created_at/native_release_date` | `awaiting_operator_value` | `operator_value_missing` | `evidence_not_required` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `native_authority_ref` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `creation_evidence_ref` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `no_leak_evidence_ref` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `method_summary` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |
| `operator_clearance` | `awaiting_operator_value` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_008/operator_source_values_template.csv` |

## Claim Boundary

Local CASP17 strict-blind source-request operator-fill batch kit only. It consolidates the existing source-request operator-fill worklist into one batch intake CSV plus request packets. It does not mutate source templates, fill values, approve no-leak provenance, copy coordinates, compute CASP metrics, mark competitive proof, serialize a CASP author code, push remotes, or submit to CASP.

# source_request_011 Strict-Blind Source Request Fill

- target: `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005`
- scope: `complex`
- request kind: `candidate_replacement_required`
- fields ready/blocked/total: `0/11/11`
- missing value/evidence: `11/9`
- first field: `source_id` `candidate_replacement_required`

## Fields

| field | status | value | evidence | source template |
| --- | --- | --- | --- | --- |
| `source_id` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `prediction_pdb` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `prediction_pdb_dropzone` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_not_required` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `prediction_created_at` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `native_release_date` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `prediction_created_at/native_release_date` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_not_required` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `native_authority_ref` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `creation_evidence_ref` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `no_leak_evidence_ref` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `method_summary` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |
| `operator_clearance` | `blocked_candidate_replacement_required` | `operator_value_missing` | `evidence_required_missing` | `casp17/strict_blind_source_gate_source_request_packet/source_request_011/operator_source_values_template.csv` |

## Claim Boundary

Local CASP17 strict-blind source-request operator-fill batch kit only. It consolidates the existing source-request operator-fill worklist into one batch intake CSV plus request packets. It does not mutate source templates, fill values, approve no-leak provenance, copy coordinates, compute CASP metrics, mark competitive proof, serialize a CASP author code, push remotes, or submit to CASP.

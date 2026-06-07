# CASP17 Strict-Blind First Unlock Evidence Review Gate

- generated: `2026-06-01T21:14:02+09:00`
- status: `awaiting_first_unlock_evidence_review`
- request/target: `source_request_001` `HIST_BBA5`
- fields ready/blocked/total: `0/11/11`
- template value/evidence/clearance/id missing: `11/0/11/11`
- stubs present/evidence-missing: `11/11`
- policy pass/blocked: `0/11`
- file ready/blocked: `0/2`
- first blocked: `source_id` `template_operator_value_missing`
- next action: fill operator_value for source_id in operator_evidence_template.csv

## Fields

| order | field | status | blocker | policy | file | next action |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `source_id` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for source_id in operator_evidence_template.csv |
| 2 | `prediction_pdb` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_path_missing` | fill operator_value for prediction_pdb in operator_evidence_template.csv |
| 3 | `prediction_pdb_dropzone` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_path_missing` | fill operator_value for prediction_pdb_dropzone in operator_evidence_template.csv |
| 4 | `prediction_created_at` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for prediction_created_at in operator_evidence_template.csv |
| 5 | `native_release_date` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for native_release_date in operator_evidence_template.csv |
| 6 | `prediction_created_at/native_release_date` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for prediction_created_at/native_release_date in operator_evidence_template.csv |
| 7 | `native_authority_ref` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for native_authority_ref in operator_evidence_template.csv |
| 8 | `creation_evidence_ref` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for creation_evidence_ref in operator_evidence_template.csv |
| 9 | `no_leak_evidence_ref` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for no_leak_evidence_ref in operator_evidence_template.csv |
| 10 | `method_summary` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for method_summary in operator_evidence_template.csv |
| 11 | `operator_clearance` | `awaiting_operator_evidence` | `template_operator_value_missing` | `policy_not_checked_value_missing` | `file_not_required` | fill operator_value for operator_clearance in operator_evidence_template.csv |

## Claim Boundary

Local CASP17 strict-blind first-unlock evidence review gate only. It validates whether the first-unlock evidence packet template and field stubs contain evidence-shaped operator values for source-gate review. It does not copy values into manifests, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

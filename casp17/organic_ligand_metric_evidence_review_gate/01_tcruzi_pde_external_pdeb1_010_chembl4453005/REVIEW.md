# Organic Ligand Metric Evidence Review - organic_ligand_slot_candidate_001

- target_id: `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005`
- ligand_id: `tcruzi_pde_external_pdeb1_010_chembl4453005`
- fields ready/blocked/total: `0/5/5`

| field | status | first blocker | next action |
| --- | --- | --- | --- |
| `direct_native_or_source_authority` | `blocked` | `template_operator_value_missing` | fill operator_value for direct_native_or_source_authority in operator_evidence_template.csv |
| `no_leak_provenance` | `blocked` | `template_operator_value_missing` | fill operator_value for no_leak_provenance in operator_evidence_template.csv |
| `prediction_chronology` | `blocked` | `template_operator_value_missing` | fill operator_value for prediction_chronology in operator_evidence_template.csv |
| `ligand_pose_reference` | `blocked` | `template_operator_value_missing` | fill operator_value for ligand_pose_reference in operator_evidence_template.csv |
| `strict_blind_slot_mapping` | `blocked` | `template_operator_value_missing` | fill operator_value for strict_blind_slot_mapping in operator_evidence_template.csv |

## Claim Boundary

Local CASP17 organic ligand metric evidence review gate only. It validates whether generated operator templates and evidence stubs contain evidence-shaped values for organic ligand metric review. It does not fill operator values, approve no-leak provenance, compute LDDT-PLI or BiSyRMSD, mark competitive proof, serialize a CASP author code, or submit to CASP.

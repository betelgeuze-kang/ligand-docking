# organic_ligand_slot_candidate_004 Promotion Actions

- target_id: `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930`
- ligand_id: `tcruzi_pde_external_pdeb1_032_chembl4445930`
- action_count: `9`

| action | status | blocks | next |
| --- | --- | --- | --- |
| `reference_file_preflight` | `reference_files_present_review_only` | `candidate_core_files` | `local reference/prediction/ligand files are present, but proof authority is still blocked` |
| `direct_native_or_source_authority` | `open_operator_evidence_required` | `strict_blind_promotion,competitive_proof` | `attach direct non-homolog native/source authority or explicitly replace this candidate` |
| `no_leak_provenance` | `open_operator_evidence_required` | `strict_blind_promotion,metric_surface` | `attach independent no-leak evidence and operator clearance for this ligand candidate` |
| `prediction_chronology` | `open_operator_evidence_required` | `strict_blind_promotion,competitive_proof` | `prove prediction chronology is before native/source release or keep candidate retrospective-only` |
| `ligand_pose_reference` | `open_operator_evidence_required` | `LDDT-PLI,BiSyRMSD` | `attach a metric-valid ligand pose reference, including receptor/ligand chain and residue mapping` |
| `affinity_numeric_label` | `open_numeric_value_required` | `Kendall_tau_affinity` | `attach numeric Ki/IC50/Kd value, units, assay reference, censoring flag, and transform rule` |
| `lddt_pli_metric_inputs` | `open_metric_input_required` | `LDDT-PLI` | `prepare LDDT-PLI input JSON after direct authority and no-leak evidence clear` |
| `bisyrmsd_metric_inputs` | `open_metric_input_required` | `BiSyRMSD` | `prepare BiSyRMSD input JSON after ligand pose reference is approved` |
| `strict_blind_slot_mapping` | `open_slot_mapping_required` | `metric_surface_contract,competitive_floor` | `map only cleared candidates into organic ligand strict-blind slots; do not use homolog-only candidates` |

## Claim Boundary

Organic ligand strict-blind promotion action board only. It decomposes evidence needed to promote review candidates into CASP17 ligand slots, but it does not supply operator authority evidence, does not clear no-leak chronology, does not compute LDDT-PLI or BiSyRMSD, and does not mark any candidate as competitive proof.

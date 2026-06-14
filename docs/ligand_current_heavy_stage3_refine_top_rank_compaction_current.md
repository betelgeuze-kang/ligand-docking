# Ligand Current Heavy Top-Rank Compaction

- status: `ligand_current_heavy_top_rank_compaction_deleted_top_rank_retained`
- requested_host_label: `ubuntu-1`
- observed_hostname: `betelgeuze-X570S-AORUS-ELITE`
- candidate_count: `7`
- candidate_size_human: `122.17 MiB`
- top_rank_retention_ready_count: `7`
- top_rows_retained_count: `350`
- skipped_large_count: `11`
- execute_requested: `True`
- approval_token_valid: `True`
- deleted_count: `7`
- deleted_size_human: `122.17 MiB`
- failed_count: `0`
- external_state_mutated: `False`

## Compacted Payloads

| path | rows | score | top rows | size | delete |
| --- | ---: | --- | ---: | ---: | --- |
| `runs/external_validation_2026-05-11_ligand_speedpack_ab_v3_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage3_refine_scores.csv` | `10000` | `binding_score_composite_v7` | `50` | `16.01 MiB` | `deleted` |
| `runs/external_validation_2026-05-11_ligand_speedpack_ab_v3_set2_expanded_ood_ion_trpv1_chembl50_full_p0_n10000_r1_stage3_refine_scores.csv` | `10000` | `binding_score_composite_v7` | `50` | `16.00 MiB` | `deleted` |
| `runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage3_refine_scores.csv` | `10000` | `binding_score_composite_v7` | `50` | `15.96 MiB` | `deleted` |
| `runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set2_expanded_ood_ion_trpv1_chembl50_full_p0_n10000_r1_stage3_refine_scores.csv` | `10000` | `binding_score_composite_v7` | `50` | `15.95 MiB` | `deleted` |
| `runs/external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set1_core_blind_ion_trpv1_chembl20_full_p0_n1000000_r1_stage3_refine_scores.csv` | `10000` | `binding_score_composite_v7` | `50` | `15.09 MiB` | `deleted` |
| `runs/external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set1_core_blind_kinase_core_full_p0_n1000000_r1_stage3_refine_scores.csv` | `20000` | `binding_score_composite_v7` | `50` | `28.56 MiB` | `deleted` |
| `runs/external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set2_expanded_ood_gpcr_chembl50_full_p0_n1000000_r1_stage3_refine_scores.csv` | `10000` | `binding_score_composite_v7` | `50` | `14.58 MiB` | `deleted` |

## Skipped Large Files

| path | size | reason |
| --- | ---: | --- |
| `runs/casp17_molecular_viewer_model_selected_current.html` | `12.32 MiB` | `skipped_non_csv_payload` |
| `runs/casp17_molecular_viewer_model_selected_normalized_current.html` | `12.33 MiB` | `skipped_non_csv_payload` |
| `runs/casp17_molecular_viewer_model_selected_shape_guarded_current.html` | `12.35 MiB` | `skipped_non_csv_payload` |
| `runs/hard_decoy_relax_cache.json` | `26.04 MiB` | `skipped_non_csv_payload` |
| `runs/hnrn_vhbond_parity_2026-03-18_v1.pt` | `10.22 MiB` | `skipped_non_csv_payload` |
| `runs/hnrn_vhbond_parity_2026-03-18_v2.pt` | `10.22 MiB` | `skipped_non_csv_payload` |
| `runs/ligand_smiles_bead_cache_blind_gpcr_adrb2_v1.json` | `44.91 MiB` | `skipped_non_csv_payload` |
| `runs/runs_artifact_inventory_current.csv` | `82.04 MiB` | `skipped_non_run_input_or_inventory_payload` |
| `runs/storage_essential_evidence_register_current.json` | `19.54 MiB` | `skipped_non_csv_payload` |
| `runs/wetlab_broad_screen_compound_universe_current.csv` | `57.10 MiB` | `skipped_non_run_input_or_inventory_payload` |
| `runs/wetlab_broad_screen_compound_universe_current.json` | `97.63 MiB` | `skipped_non_run_input_or_inventory_payload` |

## Claim Boundary

Ligand current-heavy top-rank compaction only keeps compact top-ranking rows and path/size receipts before optionally deleting local generated CSV payloads. It does not run docking, change scores, approve claim promotion, delete input libraries, delete source files, mutate git history, or touch external state.

## Next Step

- Rerun the ligand-heavy cleanup manifest and readiness checks after compaction.

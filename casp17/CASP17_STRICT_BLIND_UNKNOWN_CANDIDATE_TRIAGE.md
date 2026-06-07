# CASP17 Strict-Blind Unknown Candidate Triage

- generated: `2026-06-02T03:32:13+09:00`
- triage_status: `strict_blind_unknown_triage_internal_like_review_required`
- unknown total: `4551`
- promotion-ready: `0`
- internal-like review: `166`
- public/run/archive/data-other/tmp/other: `3962/406/16/0/1/0`
- source gate: `awaiting_internal_prediction_source_gate_fields` `internal_source_id_missing_or_external`
- first internal-like sample: `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_bba5_sample000_step00020.pdb`

## Triage Buckets

| category | files | atom-like | priority | promotion-ready | proof use | first sample |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `internal_structure_archive_unverified` | 166 | 166 | 1 | 0 | operator_review_only_until_source_chronology_no_leak_clearance | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_bba5_sample000_step00020.pdb` |
| `public_structure_archive_not_internal` | 3962 | 1686 | 2 | 0 | blocked_public_structure_not_internal_prediction | `data/public_structures/2026-02-15/bba5_pdb_1T8J.pdb` |
| `wetlab_ligand_or_allatom_review_only` | 103 | 103 | 2 | 0 | blocked_wetlab_ligand_or_repair_context_not_blind_prediction | `runs/wetlab_allatom_refinement/cathepsin_k/19_of_20/top_8/allatom_delivery/jobs/Cathepsin_K__rep0177__cathepsin_k_19_of_20_090178/backmapped_Cathepsin_K__rep0177__cathepsin_k_19_of_20_090178.pdb` |
| `gpcr_repair_or_profile_review_only` | 268 | 257 | 2 | 0 | blocked_gpcr_repair_context_not_casp_historical_prediction | `runs/gpcr_drd2_6cm4_chimerax_sidechain_rebuilt_probe.pdb` |
| `selected_visual_or_name_index_review_only` | 31 | 28 | 2 | 0 | blocked_visual_bundle_or_name_index_not_source_evidence | `runs/_by_name/99_other/chimerax_drd2_6cm4_res35_swap_probe.pdb` |
| `archival_smoke_or_delivery_review_only` | 16 | 16 | 2 | 0 | blocked_smoke_delivery_archive_not_blind_source | `archives/smoke_cleanup_2026-02-22/ligand_htvs_pipeline_smoke_2026-02-22_stage3_delivery/jobs/Chignolin__rep0000__aspirin/backmapped_Chignolin__rep0000__aspirin.pdb` |
| `runs_other_unverified` | 4 | 3 | 2 | 0 | operator_review_only_unclassified_run_artifact | `runs/chimerax_drd2_6cm4_res35_swap_probe.pdb` |
| `data_other_unverified` | 0 | 0 | 2 | 0 | operator_review_only_unclassified_data_artifact | `-` |
| `tmp_or_misc_unverified` | 1 | 1 | 2 | 0 | blocked_temporary_or_misc_artifact | `tmp/render_inputs/tcruzi_pde_chain_B_openmm_ca_md_multistate.pdb` |
| `other_unclassified` | 0 | 0 | 2 | 0 | operator_review_only_unclassified_artifact | `-` |

## Claim Boundary

CASP17 strict-blind unknown candidate triage only. It narrows the filesystem sweep's unknown files into path-provenance buckets for operator review. It does not infer pre-native chronology from mtime, does not approve no-leak evidence, and does not promote any unknown file into strict-blind proof.

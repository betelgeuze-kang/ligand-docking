# CASP17 Strict-Blind Internal Candidate Filesystem Sweep

- generated: `2026-06-02T03:12:57+09:00`
- sweep_status: `strict_blind_filesystem_sweep_operator_review_required`
- scan_root: `.`
- scanned structure files: `9975`
- atom-like files: `6422`
- verified pre-native internal candidates: `0`
- unverified possible internal review: `4551`
- current/MassiveFold/official/native/top5/dropzone: `1810/2895/387/257/75/0`
- source gate: `awaiting_internal_prediction_source_gate_fields` `internal_source_id_missing_or_external`

## Categories

| category | files | atom-like | verified | allowed | proof use | first sample |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `current_casp17_or_review_only` | 1810 | 1810 | 0 | `false` | blocked_current_casp17_not_historical | `casp17/runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` |
| `massivefold_external_baseline_only` | 2895 | 1663 | 0 | `false` | blocked_external_model_pool | `casp17/massivefold_external_pool_intake/h1311_t327/extracted_models/H1311_all_pdbs/Model_100_af3_woPaired_af3_seed_763060_sample_4_pred_79.cif` |
| `official_archive_baseline_only` | 387 | 385 | 0 | `false` | baseline_only_not_internal_prediction | `casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/native/9B0L.pdb` |
| `native_or_reference_not_prediction` | 257 | 229 | 0 | `false` | native_authority_only_not_prediction | `casp17/historical_seed_native_replacement_candidates/01_hist_bba5/native_candidate_1T8J.pdb` |
| `historical_seed_top5_post_native_review_only` | 75 | 75 | 0 | `false` | retrospective_only_prediction_not_before_native_unproven | `casp17/historical_seed_top5_candidate_pools/01_hist_bba5/model_1_selected_prediction_copy.pdb` |
| `strict_blind_dropzone_unverified` | 0 | 0 | 0 | `false` | operator_gate_required_before_proof | `-` |
| `unknown_possible_internal_review` | 4551 | 2260 | 0 | `false` | unverified_possible_internal_not_proof | `archives/smoke_cleanup_2026-02-22/ligand_htvs_pipeline_smoke_2026-02-22_stage3_delivery/jobs/Chignolin__rep0000__aspirin/backmapped_Chignolin__rep0000__aspirin.pdb` |

## Claim Boundary

CASP17 strict-blind internal candidate filesystem sweep only. It classifies local structure files by path provenance and proof boundary. It does not promote any file into strict-blind proof, does not infer pre-native chronology from filename or mtime, does not approve no-leak evidence, and does not import official, MassiveFold, current CASP17, native, or review-only files as internal predictions.

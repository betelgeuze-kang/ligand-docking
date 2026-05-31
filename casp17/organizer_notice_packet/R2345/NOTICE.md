# R2345 Organizer Notice

## Guardrails

- model_pool_policy: `external_rerank_accuracy_estimation_pool`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- submission_policy: `rule_check_required_before_any_human_submission_use`
- large_download_policy: `tarballs_not_downloaded_by_notice_packet`

## Notices

| notice_id | type | status | action |
| - | - | - | - |
| `organizer_notice_001` | `sequence_request_quarantine` | `ignored_invalid_dna_t_in_rna_sequence` | `do_not_use_first_request_for_modeling_or_scoring` |
| `organizer_notice_002` | `sequence_request_replacement` | `accepted_second_request_only` | `treat_second_request_as_r2345_active_modeling_request` |
| `organizer_notice_004` | `massivefold_r2345_set_observed` | `massivefold_external_model_set_available` | `track_external_set_separately_from_internal_prediction_lane` |

## MassiveFold Model Sets

| model_set | bundle | size_bytes | url |
| - | - | - | - |
| `R2345` | `cif_bundle` | `245903877` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz` |

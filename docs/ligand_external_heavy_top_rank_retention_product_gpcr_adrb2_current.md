# Ligand External Heavy Top-Rank Retention Receipt

- status: `ligand_external_heavy_payload_deleted_top_rank_retained`
- run_name: `product_gpcr_adrb2_after_approval`
- heavy_payload_path: `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/product_gpcr_adrb2_after_approval/stage2_trajectory_frames`
- pre_delete_size_human: `95.47 GiB`
- pre_delete_file_count: `19997`
- observed_payload_exists: `False`
- ranking_pass: `True`
- retained_top_rows: `50`
- external_state_mutated: `False`

## Ranking Evidence

- summary_json: `runs/product_gpcr_adrb2_after_approval_stage5_ranking_summary.json`
- top_rows_source: `runs/product_gpcr_adrb2_after_approval_stage5_ranking_unique.csv`
- rows_eval: `200`
- eval_unique_keys: `200`
- roc_auc: `0.9836427939876216`
- pr_auc: `0.9157321921917204`
- ef1: `7.692307692307692`

## Top-K

| k | hit_rate | enrichment_factor | hits |
| ---: | ---: | ---: | ---: |
| `10` | `1.0` | `7.692307692307692` | `10` |
| `20` | `0.9` | `6.923076923076923` | `18` |
| `50` | `0.52` | `4.0` | `26` |

## Cleanup

- dry_run_json: `runs/product_gpcr_adrb2_after_approval_external_heavy_cleanup_dry_run_current.json`
- dry_run_status: `dry_run`
- dry_run_planned_delete_count: `1`
- deletion_status: `deleted_or_absent_after_compaction`

## Retained Artifacts

- `runs/product_gpcr_adrb2_after_approval_stage5_ranking_summary.json` (`7.11 KiB`, sha256 `7a33ff43aa06`)
- `runs/product_gpcr_adrb2_after_approval_stage5_ranking_topk.csv` (`105.00 B`, sha256 `14555beaa874`)
- `runs/product_gpcr_adrb2_after_approval_stage5_ranking_unique.csv` (`16.60 KiB`, sha256 `2681a8a91a54`)
- `runs/product_gpcr_adrb2_after_approval_stage3_refine_scores_shortlist.json` (`978.85 KiB`, sha256 `e20818319da1`)

## Claim Boundary

External ligand-heavy top-rank retention only records compact ranking evidence before deleting local heavy trajectory payloads. It does not run docking, change ranking scores, approve commercial promotion, or claim wet-lab validation.

## Next Step

- No heavy payload action remains for this run; keep tracked config/docs receipt with top-rank evidence.

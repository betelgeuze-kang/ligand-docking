# R9 Candidate Support Diagnostic

- status: `refine_tier_public_benchmark_candidate_support_diagnostic_ready`
- combined_pair_count: `25`
- combined_spearman: `0.5315384615384615`
- bootstrap_p05/p50/p95: `0.23053846153846155/0.5492307692307692/0.7739230769230769`
- best_single_pair_removal: `3f3e` p05=`0.354695652174`
- best_single_pair_removal_claim_grade_p05_ready: `False`
- top_rank_residual: `3f3e` rank_abs_error=`18`
- diagnostic_policy: `leave_one_out_is_sensitivity_only_do_not_drop_pairs_without_independent_scientific_review`

## Top Leave-One-Out Rows

| target | pose | source | split | p05 without pair | p05 delta | claim-grade p05 |
| --- | --- | --- | --- | ---: | ---: | --- |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `holdout` | `0.354695652174` | `0.124157190635` | `False` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `fit` | `0.312217391304` | `0.0816789297659` | `False` |
| `4k77` | `4k77_167` | `candidate_fill_preview` | `fit` | `0.245217391304` | `0.0146789297659` | `False` |
| `1r5y` | `1r5y_167` | `existing_materialized` | `fit` | `0.237086956522` | `0.00654849498328` | `False` |
| `4e5w` | `4e5w_121` | `existing_materialized` | `fit` | `0.201608695652` | `-0.0289297658863` | `False` |
| `4j28` | `4j28_123` | `candidate_fill_preview` | `holdout` | `0.19847826087` | `-0.0320602006689` | `False` |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `fit` | `0.194652173913` | `-0.0358862876254` | `False` |
| `3udh` | `3udh_359` | `existing_materialized` | `fit` | `0.18952173913` | `-0.041016722408` | `False` |
| `3rr4` | `3rr4_369` | `candidate_fill_preview` | `fit` | `0.17547826087` | `-0.0550602006689` | `False` |
| `3n7a` | `3n7a_955` | `candidate_fill_preview` | `holdout` | `0.17252173913` | `-0.058016722408` | `False` |

## Top Rank Residual Rows

| target | pose | source | proxy rank | reference rank | rank abs error |
| --- | --- | --- | ---: | ---: | ---: |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `24` | `6` | `18` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `25` | `9` | `16` |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `3` | `16` | `13` |
| `3rr4` | `3rr4_369` | `candidate_fill_preview` | `13` | `22` | `9` |
| `1syi` | `1syi_353` | `existing_materialized` | `11` | `18` | `7` |
| `3uo4` | `3uo4_374` | `candidate_fill_preview` | `4` | `11` | `7` |
| `3g0w` | `3g0w_281` | `candidate_fill_preview` | `8` | `2` | `6` |
| `4ivb` | `4ivb_253` | `candidate_fill_preview` | `10` | `4` | `6` |
| `4ivc` | `4ivc_20` | `candidate_fill_preview` | `7` | `1` | `6` |
| `1gpk` | `1gpk_364` | `candidate_fill_preview` | `14` | `19` | `5` |

## Claim Boundary

R9 candidate support diagnostic only; it reads the local candidate-fill preview and existing materialization rows to identify rank sensitivity and outlier candidates. It does not drop rows, rewrite metric values, write reviewed payloads, approve receipts, promote canonical intake, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Do not promote or cherry-pick rows from this diagnostic. Prioritize score/model improvements for the largest rank-residual pairs, then rerun candidate fill and require bootstrap p05 >= 0.5 plus operator-reviewed metric payload receipts.

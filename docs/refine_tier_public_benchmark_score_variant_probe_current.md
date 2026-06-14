# R9 Score Variant Probe

- status: `refine_tier_public_benchmark_score_variant_probe_ready`
- combined_pair_count: `25`
- feature_complete_pair_count: `25`
- candidate_detail_from_rows_pair_count: `17`
- baseline_spearman: `0.5315384615384615`
- baseline_bootstrap_p05: `0.23053846153846155`
- top_p05_variant_id: `sqrt_contact_density_only`
- top_p05_variant_spearman: `0.6369230769230769`
- top_p05_variant_bootstrap_p05: `0.36630769230769233`
- best_variant_id: `sqrt_contact_density_only`
- best_variant_spearman: `0.6369230769230769`
- best_variant_bootstrap_p05: `0.36630769230769233`
- best_variant_bootstrap_p05_delta: `0.13576923076923078`
- best_variant_claim_grade_p05_ready: `False`
- selection_policy: `diagnostic_grid_requires_combined_spearman_not_below_baseline_and_independent_validation_before_score_use`

## Top Variants

| variant | family | alpha | beta | spearman | p05 | holdout spearman | claim-grade p05 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `sqrt_contact_density_only` | `sqrt_contact_density_only` | `0` | `0` | `0.636923076923` | `0.366307692308` | `0.619047619048` | `False` |
| `small_ligand_rescue_a0.08` | `small_ligand_rescue` | `0.08` | `0` | `0.618461538462` | `0.354730769231` | `0.714285714286` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b0` | `small_ligand_rescue_size_regularized` | `0.06` | `0` | `0.616153846154` | `0.340576923077` | `0.619047619048` | `False` |
| `small_ligand_rescue_a0.06` | `small_ligand_rescue` | `0.06` | `0` | `0.616153846154` | `0.340576923077` | `0.619047619048` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b0.05` | `small_ligand_rescue_size_regularized` | `0.06` | `0.05` | `0.611538461538` | `0.339692307692` | `0.714285714286` | `False` |
| `small_ligand_rescue_size_regularized_a0.04_b0.1` | `small_ligand_rescue_size_regularized` | `0.04` | `0.1` | `0.575384615385` | `0.3295` | `0.52380952381` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b-0.05` | `small_ligand_rescue_size_regularized` | `0.06` | `-0.05` | `0.608461538462` | `0.312923076923` | `0.619047619048` | `False` |
| `small_ligand_rescue_size_regularized_a0.04_b0.05` | `small_ligand_rescue_size_regularized` | `0.04` | `0.05` | `0.598461538462` | `0.312192307692` | `0.619047619048` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b0.1` | `small_ligand_rescue_size_regularized` | `0.06` | `0.1` | `0.576153846154` | `0.309730769231` | `0.619047619048` | `False` |
| `small_ligand_rescue_size_regularized_a0.04_b0` | `small_ligand_rescue_size_regularized` | `0.04` | `0` | `0.594615384615` | `0.307461538462` | `0.547619047619` | `False` |
| `small_ligand_rescue_a0.04` | `small_ligand_rescue` | `0.04` | `0` | `0.594615384615` | `0.307461538462` | `0.547619047619` | `False` |
| `small_ligand_rescue_a0.03` | `small_ligand_rescue` | `0.03` | `0` | `0.586923076923` | `0.2995` | `0.52380952381` | `False` |

## Best Variant Rank Residuals

| target | pose | source | split | variant rank | reference rank | rank abs error |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `fit` | `1` | `16` | `15` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `fit` | `22` | `9` | `13` |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `holdout` | `19` | `6` | `13` |
| `1gpk` | `1gpk_364` | `candidate_fill_preview` | `fit` | `9` | `19` | `10` |
| `4j28` | `4j28_123` | `candidate_fill_preview` | `holdout` | `24` | `15` | `9` |
| `1syi` | `1syi_353` | `existing_materialized` | `holdout` | `10` | `18` | `8` |
| `3n7a` | `3n7a_955` | `candidate_fill_preview` | `holdout` | `15` | `23` | `8` |
| `3rr4` | `3rr4_369` | `candidate_fill_preview` | `fit` | `18` | `22` | `4` |
| `4ivb` | `4ivb_253` | `candidate_fill_preview` | `fit` | `8` | `4` | `4` |
| `4ivc` | `4ivc_20` | `candidate_fill_preview` | `holdout` | `5` | `1` | `4` |

## Claim Boundary

R9 score-variant probe only; it reads local existing/candidate-fill metric details and evaluates predeclared scoring variants against the current public-benchmark preview. It does not rewrite candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical intake, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

If a variant materially improves bootstrap p05, validate it on an independent R9 holdout or operator-reviewed metric-source payloads before touching candidate-fill values. Keep public benchmark claim promotion blocked until reviewed payload receipts and p05 >= 0.5 are both true.

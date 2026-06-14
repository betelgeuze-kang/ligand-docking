# R9 Fit/Holdout Calibration Probe

- status: `refine_tier_public_benchmark_fit_holdout_calibration_probe_ready`
- combined_pair_count: `25`
- fit_pair_count: `17`
- holdout_pair_count: `8`
- feature_complete_pair_count: `25`
- baseline_fit/holdout/combined: `0.5343137254901961/0.6428571428571429/0.5315384615384615`
- baseline_bootstrap_p05: `0.23053846153846155`
- fit_selected_variant_id: `sqrt_contact_density_only`
- fit_selected_fit/holdout/combined: `0.6642156862745098/0.6190476190476191/0.6369230769230769`
- fit_selected_bootstrap_p05: `0.36630769230769233`
- fit_selected_holdout_non_degradation_ready: `False`
- holdout_guarded_variant_id: `small_ligand_rescue_a0.08`
- holdout_guarded_fit/holdout/combined: `0.6127450980392157/0.7142857142857143/0.6184615384615385`
- holdout_guarded_bootstrap_p05: `0.3547307692307693`
- holdout_guarded_claim_grade_p05_ready: `False`
- calibration_generalization_ready: `False`

## Top Fit-Selected Candidates

| variant | family | fit | holdout | combined | p05 | holdout guarded | claim-grade p05 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `sqrt_contact_density_only` | `sqrt_contact_density_only` | `0.664215686275` | `0.619047619048` | `0.636923076923` | `0.366307692308` | `False` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b0` | `small_ligand_rescue_size_regularized` | `0.622549019608` | `0.619047619048` | `0.616153846154` | `0.340576923077` | `False` | `False` |
| `small_ligand_rescue_a0.06` | `small_ligand_rescue` | `0.622549019608` | `0.619047619048` | `0.616153846154` | `0.340576923077` | `False` | `False` |
| `small_ligand_rescue_a0.08` | `small_ligand_rescue` | `0.612745098039` | `0.714285714286` | `0.618461538462` | `0.354730769231` | `True` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b-0.05` | `small_ligand_rescue_size_regularized` | `0.605392156863` | `0.619047619048` | `0.608461538462` | `0.312923076923` | `False` | `False` |
| `small_ligand_rescue_size_regularized_a0.04_b0.05` | `small_ligand_rescue_size_regularized` | `0.600490196078` | `0.619047619048` | `0.598461538462` | `0.312192307692` | `False` | `False` |
| `small_ligand_rescue_size_regularized_a0.04_b0` | `small_ligand_rescue_size_regularized` | `0.600490196078` | `0.547619047619` | `0.594615384615` | `0.307461538462` | `False` | `False` |
| `small_ligand_rescue_a0.04` | `small_ligand_rescue` | `0.600490196078` | `0.547619047619` | `0.594615384615` | `0.307461538462` | `False` | `False` |
| `small_ligand_rescue_a0.03` | `small_ligand_rescue` | `0.600490196078` | `0.52380952381` | `0.586923076923` | `0.2995` | `False` | `False` |
| `small_ligand_rescue_size_regularized_a0.04_b-0.05` | `small_ligand_rescue_size_regularized` | `0.600490196078` | `0.52380952381` | `0.585384615385` | `0.299423076923` | `False` | `False` |
| `small_ligand_rescue_size_regularized_a0.02_b0.05` | `small_ligand_rescue_size_regularized` | `0.600490196078` | `0.52380952381` | `0.574615384615` | `0.283884615385` | `False` | `False` |
| `small_ligand_rescue_size_regularized_a0.06_b0.05` | `small_ligand_rescue_size_regularized` | `0.598039215686` | `0.714285714286` | `0.611538461538` | `0.339692307692` | `True` | `False` |

## Holdout-Guarded Residuals

| target | pose | source | split | variant rank | reference rank | rank abs error |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `3n86` | `3n86_99` | `candidate_fill_preview` | `fit` | `2` | `16` | `14` |
| `2j7h` | `2j7h_48` | `existing_materialized` | `fit` | `22` | `9` | `13` |
| `1syi` | `1syi_353` | `existing_materialized` | `holdout` | `8` | `18` | `10` |
| `3f3e` | `3f3e_197` | `candidate_fill_preview` | `holdout` | `16` | `6` | `10` |
| `3rr4` | `3rr4_369` | `candidate_fill_preview` | `fit` | `14` | `22` | `8` |
| `4j28` | `4j28_123` | `candidate_fill_preview` | `holdout` | `23` | `15` | `8` |
| `4k77` | `4k77_167` | `candidate_fill_preview` | `fit` | `18` | `10` | `8` |
| `1gpk` | `1gpk_364` | `candidate_fill_preview` | `fit` | `12` | `19` | `7` |
| `3n7a` | `3n7a_955` | `candidate_fill_preview` | `holdout` | `17` | `23` | `6` |
| `4ivb` | `4ivb_253` | `candidate_fill_preview` | `fit` | `10` | `4` | `6` |

## Claim Boundary

R9 fit/holdout calibration probe only; it reuses local public-benchmark preview features, selects scoring hypotheses from the fit split, and reports holdout-guarded diagnostics. It does not rewrite candidate-fill values, write reviewed metric payloads, approve operator receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Use the holdout-guarded variant only as a scoring hypothesis. Validate descriptor calibration on independent/operator-reviewed R9 metric-source payloads and reduce the largest rank residuals before any canonical intake, payload write, or claim promotion.

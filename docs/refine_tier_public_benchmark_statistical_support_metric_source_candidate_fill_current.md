# R9 Statistical-Support Metric Candidate Fill

- status: `refine_tier_public_benchmark_statistical_support_metric_candidates_ready`
- candidate rows: `51/51`
- metric values computed: `51`
- candidate pairs: `17`
- combined public benchmark pairs: `25`
- combined fit/holdout pairs: `17/8`
- combined Spearman: `0.5315384615384615`
- bootstrap Spearman p05/p50/p95: `0.23349188084975714/0.5508308100108106/0.7754054054054054`
- claim-grade statistical support ready: `False`
- claim-grade blockers: `['claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum']`
- expected metric source artifacts touched: `0`
- expected metric source artifacts already present: `0`
- compact JSON size: `161.66 KiB`

## Candidate Pairs

| work_order_id | target | pose | split | dG candidate | dG experimental | dockq | lddt_pli | status |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `refine_tier_public_benchmark_stat_support_expansion_001` | `4ivc` | `4ivc_20` | `holdout` | `-7.158980` | `-13.6425` | `0.728921` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_002` | `3g0w` | `3g0w_281` | `holdout` | `-6.709551` | `-12.9916` | `0.731997` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_003` | `4j28` | `4j28_123` | `holdout` | `-3.853712` | `-7.7748` | `0.732979` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_004` | `3n7a` | `3n7a_955` | `holdout` | `-3.302813` | `-5.04631` | `0.719352` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_005` | `3f3e` | `3f3e_197` | `holdout` | `-2.392981` | `-10.5033` | `0.733726` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_006` | `3fv1` | `3fv1_115` | `fit` | `-9.316900` | `-12.6889` | `0.733143` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_007` | `4k77` | `4k77_167` | `fit` | `-4.215750` | `-9.0435` | `0.731980` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_008` | `4ivb` | `4ivb_253` | `fit` | `-6.401457` | `-11.8979` | `0.732935` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_009` | `3n86` | `3n86_99` | `fit` | `-8.336393` | `-7.692` | `0.733667` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_010` | `3rr4` | `3rr4_369` | `fit` | `-5.174766` | `-6.21014` | `0.734431` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_011` | `3bgz` | `3bgz_97` | `fit` | `-5.774185` | `-8.53969` | `0.723214` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_012` | `4de1` | `4de1_190` | `fit` | `-6.456997` | `-8.12901` | `0.733469` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_013` | `2xb8` | `2xb8_268` | `fit` | `-7.545382` | `-10.3478` | `0.734087` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_014` | `3b27` | `3b27_307` | `fit` | `-3.278713` | `-7.04108` | `0.732851` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_015` | `2cbv` | `2cbv_90` | `fit` | `-3.153874` | `-7.4781` | `0.731915` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_016` | `1gpk` | `1gpk_364` | `fit` | `-4.650096` | `-7.32127` | `0.735113` | `1.000000` | `pass` |
| `refine_tier_public_benchmark_stat_support_expansion_017` | `3uo4` | `3uo4_374` | `fit` | `-7.621207` | `-8.9008` | `0.734780` | `1.000000` | `pass` |

## Claim Boundary

R9 statistical-support metric candidate fill only; computes deterministic local proxy values from already-local ligand pose, native/reference ligand, and coordinate-validated receptor/complex artifacts. It does not write the expected metric source payload paths, approve operator receipts, write canonical intake, promote claims, run docking or MD, download, upload, email, delete, commit, push, or mutate external state.

# CASP17 Historical Seed Top-5 Candidate Pools

- generated: `2026-05-28T03:59:02+09:00`
- top5_candidate_pool_status: `top5_candidate_pool_ready_for_review`
- seed rows/pools/models: `15/15/75`
- complete/gap/source-present/source-blocked: `15/0/15/0`
- generated perturbations: `60`
- first open: `HIST_BBA5`
- next action: feed candidate pool into calibration ledger, then attach native oracle metrics and internal scores

## Seed Rows

| rank | target | scope | status | candidates | top5 | perturbations | pool | blockers |
| ---: | --- | --- | --- | ---: | --- | ---: | --- | --- |
| 1 | `HIST_BBA5` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/01_hist_bba5/candidate_pool.csv` | `-` |
| 2 | `HIST_CHIGNOLIN` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/02_hist_chignolin/candidate_pool.csv` | `-` |
| 3 | `HIST_CRAMBIN` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/03_hist_crambin/candidate_pool.csv` | `-` |
| 4 | `HIST_FSD_1` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/04_hist_fsd_1/candidate_pool.csv` | `-` |
| 5 | `HIST_GB1_MINI` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/05_hist_gb1_mini/candidate_pool.csv` | `-` |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/06_hist_protein_a_bdomain/candidate_pool.csv` | `-` |
| 7 | `HIST_TRP_CAGE` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/07_hist_trp_cage/candidate_pool.csv` | `-` |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/08_hist_ubiquitin_mini/candidate_pool.csv` | `-` |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/09_hist_villin_hp35/candidate_pool.csv` | `-` |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/10_hist_ww_domain_fip35/candidate_pool.csv` | `-` |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/11_hist_complex_01_tcruzi_pde_external_pdeb1_010_chembl4453005/candidate_pool.csv` | `-` |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/12_hist_complex_02_tcruzi_pde_external_pdeb1_043_chembl2171451/candidate_pool.csv` | `-` |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/13_hist_complex_03_tcruzi_pde_external_pdeb1_025_chembl4441871/candidate_pool.csv` | `-` |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/14_hist_complex_04_tcruzi_pde_external_pdeb1_032_chembl4445930/candidate_pool.csv` | `-` |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `top5_candidate_pool_ready_for_review` | 5 | `True` | 4 | `casp17/historical_seed_top5_candidate_pools/15_hist_complex_05_tcruzi_pde_external_pdeb1_007_chembl3764370/candidate_pool.csv` | `-` |

## Claim Boundary

Local CASP17 historical seed top-5 candidate-pool scaffolding only. Perturbation candidates are deterministic review decoys derived from already-local historical selected predictions. They are not independent predictor outputs, do not compute native accuracy, do not clear leakage provenance, do not fetch native structures, and do not submit to CASP.

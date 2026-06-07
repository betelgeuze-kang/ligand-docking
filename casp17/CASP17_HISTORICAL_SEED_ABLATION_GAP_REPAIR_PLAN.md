# CASP17 Historical Seed Ablation Gap Repair Plan

- generated: `2026-05-31T14:46:57+09:00`
- ablation_gap_repair_status: `ablation_gap_repair_required`
- seed rows/repair csvs: `15/15`
- real/missing-real/top5-decoy/top5-copy: `1/19/60/15`
- ready/gap/core-blocked: `1/14/0`
- first open: `HIST_BBA5`
- next action: generate or attach true same-run/pre-minimization ablation layers; keep top5 decoys as review-only context

## Seed Rows

| rank | target | scope | status | real | missing real | decoys | copy | csv | blockers |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `HIST_BBA5` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/01_hist_bba5/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 2 | `HIST_CHIGNOLIN` | `monomer` | `ablation_reference_candidate_ready_for_operator_review` | 1 | 1 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/02_hist_chignolin/ablation_gap_repair_candidates.csv` | `top5_decoys_not_clearance_evidence` |
| 3 | `HIST_CRAMBIN` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/03_hist_crambin/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 4 | `HIST_FSD_1` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/04_hist_fsd_1/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 5 | `HIST_GB1_MINI` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/05_hist_gb1_mini/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/06_hist_protein_a_bdomain/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 7 | `HIST_TRP_CAGE` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/07_hist_trp_cage/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/08_hist_ubiquitin_mini/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/09_hist_villin_hp35/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `ablation_gap_repair_required` | 0 | 2 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/10_hist_ww_domain_fip35/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `ablation_gap_repair_required` | 0 | 0 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/11_hist_complex_01_tcruzi_pde_external_pdeb1_010_chembl4453005/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `ablation_gap_repair_required` | 0 | 0 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/12_hist_complex_02_tcruzi_pde_external_pdeb1_043_chembl2171451/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `ablation_gap_repair_required` | 0 | 0 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/13_hist_complex_03_tcruzi_pde_external_pdeb1_025_chembl4441871/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `ablation_gap_repair_required` | 0 | 0 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/14_hist_complex_04_tcruzi_pde_external_pdeb1_032_chembl4445930/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `ablation_gap_repair_required` | 0 | 0 | 4 | 1 | `casp17/historical_seed_ablation_gap_repair_plan/15_hist_complex_05_tcruzi_pde_external_pdeb1_007_chembl3764370/ablation_gap_repair_candidates.csv` | `real_ablation_layer_candidate_missing,top5_decoys_not_clearance_evidence` |

## Claim Boundary

Local CASP17 historical seed ablation gap repair plan only. It distinguishes real same-run/pre-minimization ablation-layer candidates from top-5 review decoys. Top-5 deterministic perturbations are listed as review context only and are not treated as operator-approved ablation evidence. This packet does not mutate operator CSVs, clear no-leak provenance, approve ablation coverage, run predictors, fetch structures, or submit to CASP.

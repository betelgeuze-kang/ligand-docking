# CASP17 Historical Seed Clearance Execution Board

- generated: `2026-05-31T14:47:19+09:00`
- status: `first_row_operator_no_leak_only`
- seed rows: `15`
- operator no-leak-only rows: `1`
- ablation-repair rows: `14`
- operator no-leak fields: `150`
- proposed fields: `91`
- calibration/ablation candidates: `90/1`
- blocked ablation fields: `14`
- first execution target: `HIST_CHIGNOLIN` `operator_no_leak_only`
- next action: fill operator no-leak evidence fields, then apply prepared calibration and ablation candidates

## Execution Rows

| rank | target | scope | status | no-leak fields | proposed | ablation blocked | folder | next action |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `HIST_CHIGNOLIN` | `monomer` | `operator_no_leak_only` | 10 | 7 | 0 | `casp17/historical_seed_clearance_execution_board/02_hist_chignolin` | fill operator no-leak evidence fields, then apply prepared calibration and ablation candidates |
| 2 | `HIST_BBA5` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/01_hist_bba5` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 3 | `HIST_CRAMBIN` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/03_hist_crambin` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 4 | `HIST_FSD_1` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/04_hist_fsd_1` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 5 | `HIST_GB1_MINI` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/05_hist_gb1_mini` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/06_hist_protein_a_bdomain` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 7 | `HIST_TRP_CAGE` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/07_hist_trp_cage` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/08_hist_ubiquitin_mini` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/09_hist_villin_hp35` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/10_hist_ww_domain_fip35` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/11_hist_complex_01_tcruzi_pde_external_pdeb1_010_chembl4453005` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/12_hist_complex_02_tcruzi_pde_external_pdeb1_043_chembl2171451` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/13_hist_complex_03_tcruzi_pde_external_pdeb1_025_chembl4441871` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/14_hist_complex_04_tcruzi_pde_external_pdeb1_032_chembl4445930` | repair real ablation layer evidence, then fill operator no-leak evidence fields |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `ablation_repair_then_operator_no_leak` | 10 | 6 | 1 | `casp17/historical_seed_clearance_execution_board/15_hist_complex_05_tcruzi_pde_external_pdeb1_007_chembl3764370` | repair real ablation layer evidence, then fill operator no-leak evidence fields |

## Claim Boundary

Local CASP17 historical seed clearance execution board only. It ranks existing fill candidates by shortest local path to a cleared historical benchmark row. It does not mutate operator CSVs, clear no-leak provenance, approve ablation evidence, compute official CASP metrics, or submit to CASP.

# CASP17 Historical Identity Seed Clearance Field Board

- generated: `2026-05-28T03:10:52+09:00`
- field_board_status: `operator_field_fill_required`
- seed rows: `15`
- core files pass/blocked: `15/0`
- rows operator-fill/ready: `15/0`
- open fields no-leak/calibration/ablation/total: `150/90/15/255`
- first open: `HIST_BBA5` `no_leak_evidence_ref`
- next action: fill no-leak evidence, chronology, leakage controls, and operator clearance first

## Field Rows

| slot | target | scope | status | core | atoms pred/native | open no-leak/calibration/ablation | first open | next action |
| ---: | --- | --- | --- | --- | ---: | --- | --- | --- |
| 1 | `HIST_BBA5` | `monomer` | `operator_field_fill_required` | `pass` | 92/23 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 2 | `HIST_CHIGNOLIN` | `monomer` | `operator_field_fill_required` | `pass` | 40/10 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 3 | `HIST_CRAMBIN` | `monomer` | `operator_field_fill_required` | `pass` | 184/46 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 4 | `HIST_FSD_1` | `monomer` | `operator_field_fill_required` | `pass` | 112/28 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 5 | `HIST_GB1_MINI` | `monomer` | `operator_field_fill_required` | `pass` | 224/56 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `operator_field_fill_required` | `pass` | 240/60 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 7 | `HIST_TRP_CAGE` | `monomer` | `operator_field_fill_required` | `pass` | 80/20 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `operator_field_fill_required` | `pass` | 304/76 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `operator_field_fill_required` | `pass` | 140/35 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `operator_field_fill_required` | `pass` | 140/35 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `operator_field_fill_required` | `pass` | 5230/2676 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `operator_field_fill_required` | `pass` | 5219/2665 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `operator_field_fill_required` | `pass` | 5225/2671 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `operator_field_fill_required` | `pass` | 5207/2653 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `operator_field_fill_required` | `pass` | 5223/2669 | 10/6/1 | `no_leak_evidence_ref` | fill no-leak evidence, chronology, leakage controls, and operator clearance first |

## Claim Boundary

Local CASP17 historical seed-clearance field board only. It audits local seed prediction/native files and operator-fill fields needed before the cleared seed manifest can be emitted. It does not clear no-leak provenance, infer chronology, fetch native structures, score native accuracy, mutate operator CSVs, mutate competitive-floor identity intake, run predictors, or submit to CASP.

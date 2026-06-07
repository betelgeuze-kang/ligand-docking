# CASP17 Historical Seed Lane Decision Packet

- generated: `2026-05-31T15:14:19+09:00`
- status: `strict_blind_replacement_required`
- seed rows: `17`
- strict-blind / retrospective / authority-required: `0/10/7`
- competitive-proof / identity-intake / sidechain-benchmark allowed: `0/0/0`
- strict-blind replacement required: `17`
- first blocked: `HIST_BBA5`
- next action: keep this row outside competitive proof unless operator supplies a pre-native blind prediction artifact; otherwise use only for retrospective no-template calibration review

## Seed Rows

| rank | target | scope | lane | strict blind | retrospective | competitive proof | blockers |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `HIST_BBA5` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 2 | `HIST_CHIGNOLIN` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 3 | `HIST_CRAMBIN` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 4 | `HIST_FSD_1` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 5 | `HIST_GB1_MINI` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 7 | `HIST_TRP_CAGE` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `retrospective_no_template_review_only` | `False` | `True` | `False` | `prediction_not_before_authoritative_native_date` |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 16 | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing,prediction_date_candidate_missing` |
| 17 | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `complex` | `strict_blind_replacement_or_authority_required` | `False` | `False` | `False` | `native_authority_not_pass,authoritative_native_date_missing,prediction_date_candidate_missing` |

## Claim Boundary

Local CASP17 historical seed lane decision packet only. It prevents post-native or authority-incomplete seed rows from being promoted into strict blind competitive proof. Retrospective rows may remain useful for calibration or engineering review only after separate no-template/no-leak evidence. The packet does not clear provenance, mutate manifest/operator CSVs, compute official CASP metrics, or submit to CASP.

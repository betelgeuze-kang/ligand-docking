# CASP17 Historical Seed Authoritative Chronology Audit

- generated: `2026-05-31T15:07:30+09:00`
- status: `post_native_prediction_chronology_blocked`
- seed rows: `17`
- native authority dates / prediction date candidates: `10/15`
- before-native / post-native-blocked / evidence-required: `0/10/7`
- native authority not-pass / missing native date / missing prediction date: `7/7/2`
- first blocked: `HIST_BBA5`
- next action: replace with a pre-native blind prediction artifact, or keep this row in a separate post-native retrospective lane with explicit no-template evidence

## Seed Rows

| rank | target | scope | status | prediction | native authority date | after native | blockers |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `HIST_BBA5` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `2004-05-13` | `True` | `prediction_not_before_authoritative_native_date` |
| 2 | `HIST_CHIGNOLIN` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `2003-03-13` | `True` | `prediction_not_before_authoritative_native_date` |
| 3 | `HIST_CRAMBIN` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `1981-04-30` | `True` | `prediction_not_before_authoritative_native_date` |
| 4 | `HIST_FSD_1` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `1997-06-09` | `True` | `prediction_not_before_authoritative_native_date` |
| 5 | `HIST_GB1_MINI` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `1991-05-15` | `True` | `prediction_not_before_authoritative_native_date` |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `1996-06-28` | `True` | `prediction_not_before_authoritative_native_date` |
| 7 | `HIST_TRP_CAGE` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `2002-02-25` | `True` | `prediction_not_before_authoritative_native_date` |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `1987-01-02` | `True` | `prediction_not_before_authoritative_native_date` |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `2005-02-03` | `True` | `prediction_not_before_authoritative_native_date` |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `post_native_prediction_chronology_blocked` | `2026-02-19` | `2005-11-15` | `True` | `prediction_not_before_authoritative_native_date` |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `operator_authoritative_chronology_evidence_required` | `2026-05-17` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `operator_authoritative_chronology_evidence_required` | `2026-05-17` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `operator_authoritative_chronology_evidence_required` | `2026-05-17` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `operator_authoritative_chronology_evidence_required` | `2026-05-17` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `operator_authoritative_chronology_evidence_required` | `2026-05-17` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing` |
| 16 | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `complex` | `operator_authoritative_chronology_evidence_required` | `-` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing,prediction_date_candidate_missing` |
| 17 | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `complex` | `operator_authoritative_chronology_evidence_required` | `-` | `-` | `False` | `native_authority_not_pass,authoritative_native_date_missing,prediction_date_candidate_missing` |

## Claim Boundary

Local CASP17 historical seed authoritative chronology audit only. It compares local/internal prediction-date candidates with native-authority dates parsed from already-audited native evidence. It does not clear no-leak provenance, certify a prediction was blind, approve use of public native structures/templates, mutate operator clearance CSVs, compute official CASP metrics, or submit to CASP.

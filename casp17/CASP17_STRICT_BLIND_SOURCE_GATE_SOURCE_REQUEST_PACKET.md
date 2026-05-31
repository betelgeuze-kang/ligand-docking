# CASP17 Strict-Blind Source Gate Source Request Packet

- generated: `2026-06-01T03:36:07+09:00`
- status: `awaiting_pre_native_source_or_candidate_replacement`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- route/operator status: `first_slot_requires_pre_native_monomer_source_or_replacement` `awaiting_source_gate_operator_values`
- requests pre-native/replacement/operator-repair/total: `10/7/0/17`
- operator templates ready/awaiting: `0/17` fields filled/missing/total `0/187/187`
- monomer/complex requests: `10/7`
- first request: `source_request_001` `HIST_BBA5` `pre_native_prediction_source_required` `prediction_not_before_native` missing `source_id`

## Requests

| request | target | scope | kind | blocker | operator fields | dates | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `source_request_001` | `HIST_BBA5` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/2004-05-13` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_002` | `HIST_CHIGNOLIN` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/2003-03-13` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_003` | `HIST_CRAMBIN` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/1981-04-30` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_004` | `HIST_FSD_1` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/1997-06-09` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_005` | `HIST_GB1_MINI` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/1991-05-15` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_006` | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/1996-06-28` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_007` | `HIST_TRP_CAGE` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/2002-02-25` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_008` | `HIST_UBIQUITIN_MINI` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/1987-01-02` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_009` | `HIST_VILLIN_HP35` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/2005-02-03` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_010` | `HIST_WW_DOMAIN_FIP35` | `monomer` | `pre_native_prediction_source_required` | `prediction_not_before_native` | `0/11/11` | `2026-02-19/2005-11-15` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `source_request_011` | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `2026-05-17/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |
| `source_request_012` | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `2026-05-17/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |
| `source_request_013` | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `2026-05-17/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |
| `source_request_014` | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `2026-05-17/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |
| `source_request_015` | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `2026-05-17/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |
| `source_request_016` | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `-/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |
| `source_request_017` | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `complex` | `candidate_replacement_required` | `native_authority_missing` | `0/11/11` | `-/-` | replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane |

Local CASP17 strict-blind source-gate source request packet only. It converts fail-closed first-slot source routes into operator source-acquisition request folders. It does not fetch external archives, create prediction/native files, approve provenance, mutate source manifests, compute CASP metrics, push remotes, or submit to CASP.

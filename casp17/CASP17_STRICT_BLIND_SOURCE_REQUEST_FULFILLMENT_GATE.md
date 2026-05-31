# CASP17 Strict-Blind Source Request Fulfillment Gate

- generated: `2026-06-01T03:45:35+09:00`
- status: `awaiting_source_request_operator_values`
- source request/operator packet: `awaiting_pre_native_source_or_candidate_replacement` `awaiting_source_gate_operator_values`
- requests ready/blocked/total: `0/17/17`
- operator fields filled/missing/total: `0/187/187`
- evidence refs present/missing: `0/153`
- validation pass counts pdb/chronology/internal-source: `0/0/0`
- first blocker: `source_request_001` `HIST_BBA5` `source_id_missing`
- next action: fill operator_value for source_id

## Requests

| request | target | kind | status | fields | evidence | pdb atoms | chronology | source | first blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `source_request_001` | `HIST_BBA5` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_002` | `HIST_CHIGNOLIN` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_003` | `HIST_CRAMBIN` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_004` | `HIST_FSD_1` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_005` | `HIST_GB1_MINI` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_006` | `HIST_PROTEIN_A_BDOMAIN` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_007` | `HIST_TRP_CAGE` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_008` | `HIST_UBIQUITIN_MINI` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_009` | `HIST_VILLIN_HP35` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_010` | `HIST_WW_DOMAIN_FIP35` | `pre_native_prediction_source_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `source_id_missing` |
| `source_request_011` | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |
| `source_request_012` | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |
| `source_request_013` | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |
| `source_request_014` | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |
| `source_request_015` | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |
| `source_request_016` | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |
| `source_request_017` | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `candidate_replacement_required` | `blocked_on_source_request_fulfillment` | `0/11/11` | `0/9` | `0` | `date_missing_or_invalid` | `source_id_missing` | `candidate_replacement_required` |

Local CASP17 strict-blind source-request fulfillment gate only. It validates operator-filled source request templates for field completeness, evidence references, internal-source labeling, PDB atom records, and pre-native chronology. It does not apply values to the source-gate operator packet, copy files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.

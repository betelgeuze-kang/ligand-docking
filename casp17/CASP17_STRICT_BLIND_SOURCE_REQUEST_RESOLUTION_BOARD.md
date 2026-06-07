# CASP17 Strict-Blind Source Request Resolution Board

- generated: `2026-06-02T03:41:22+09:00`
- status: `source_request_resolution_all_current_candidates_blocked`
- requests ready/blocked/total: `0/17/17`
- monomer/complex: `10/7`
- all-post-native monomer/replacement/pre-native-review/missing-review: `10/7/0/0`
- internal-like candidates post/pre: `166/0`
- first blocker: `source_request_001` `HIST_BBA5` `all_internal_like_candidates_post_native`

## Resolution Rows

| request | target | scope | resolution | internal-like | blockers | next action |
| --- | --- | --- | --- | ---: | --- | --- |
| `source_request_001` | `HIST_BBA5` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_002` | `HIST_CHIGNOLIN` | `monomer` | `requires_new_pre_native_internal_source` | 22/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_003` | `HIST_CRAMBIN` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_004` | `HIST_FSD_1` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_005` | `HIST_GB1_MINI` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_006` | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_007` | `HIST_TRP_CAGE` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_008` | `HIST_UBIQUITIN_MINI` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_009` | `HIST_VILLIN_HP35` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_010` | `HIST_WW_DOMAIN_FIP35` | `monomer` | `requires_new_pre_native_internal_source` | 16/0 | `all_internal_like_candidates_post_native,prediction_not_before_native` | replace this source request with a different internal prediction artifact created before native release |
| `source_request_011` | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |
| `source_request_012` | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |
| `source_request_013` | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |
| `source_request_014` | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |
| `source_request_015` | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |
| `source_request_016` | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |
| `source_request_017` | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `complex` | `requires_authoritative_native_or_replacement_candidate` | 0/0 | `native_authority_missing` | move this row to a strict ligand/complex authority repair or replace it with an in-scope pre-native source |

## Claim Boundary

CASP17 strict-blind source request resolution board only. It propagates internal-like chronology review results into source-request resolution classes so post-native local artifacts are not accidentally treated as strict-blind evidence. It does not fill operator values, approve no-leak evidence, copy files, compute CASP metrics, push remotes, or submit to CASP.

# CASP17 Historical Seed Strict-Blind Replacement First Slot Source Route Board

- generated: `2026-05-31T17:35:08+09:00`
- status: `first_slot_requires_pre_native_monomer_source_or_replacement`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- routes in-scope/out-of-scope/total: `10/7/17`
- allowed for first slot: `0`
- in-scope external targets/actions: `10/20`
- out-of-scope source/date repair targets: `7/7`
- first external target: `HIST_BBA5` prediction/native `2026-02-19` `2004-05-13`
- next action: source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate

## Routes

| route | target | scope | status | allowed | prediction | native | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `first_slot_source_route_001` | `HIST_BBA5` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `2004-05-13` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_002` | `HIST_CHIGNOLIN` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `2003-03-13` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_003` | `HIST_CRAMBIN` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `1981-04-30` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_004` | `HIST_FSD_1` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `1997-06-09` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_005` | `HIST_GB1_MINI` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `1991-05-15` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_006` | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `1996-06-28` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_007` | `HIST_TRP_CAGE` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `2002-02-25` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_008` | `HIST_UBIQUITIN_MINI` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `1987-01-02` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_009` | `HIST_VILLIN_HP35` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `2005-02-03` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_010` | `HIST_WW_DOMAIN_FIP35` | `monomer` | `in_scope_current_candidate_disqualified_post_native` | `False` | `2026-02-19` | `2005-11-15` | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `first_slot_source_route_011` | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `2026-05-17` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |
| `first_slot_source_route_012` | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `2026-05-17` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |
| `first_slot_source_route_013` | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `2026-05-17` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |
| `first_slot_source_route_014` | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `2026-05-17` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |
| `first_slot_source_route_015` | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `2026-05-17` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |
| `first_slot_source_route_016` | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `-` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |
| `first_slot_source_route_017` | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `complex` | `out_of_scope_context_only_for_first_slot` | `False` | `-` | `-` | do not promote to this monomer slot; keep as complex-lane context after source authority is repaired |

## Claim Boundary

Local CASP17 first-slot source-route board only. It decides whether local candidates can be routed toward the first required strict-blind monomer slot, or must be replaced/sourced from an external pre-native prediction archive. It does not fetch sources, create evidence, approve candidates, compute metrics, or submit to CASP.

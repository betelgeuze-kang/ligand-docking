# CASP17 RNA/Hybrid MassiveFold Priority Queue

- generated: `2026-05-31T19:15:39+09:00`
- status: `rna_hybrid_massivefold_priority_queue_ready`
- queue rows ready/blocked/total: `6/0/6`
- first priority: `R2341` `organizer_notice_first_rna_massivefold_set_available`
- R2341 rank/present: `1`/`True`
- R2345 rank/present: `2`/`True`
- R2345 invalid/active/guard: `ignored_invalid_dna_t_in_rna_sequence`/`accepted_second_request_only`/`ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only`
- proof/internal-blocked: `0/6`
- total declared size bytes: `6378670010`
- next action: start with R2341 for rule-checked external-pool acquisition and reranking; keep the R2345 09:30 Pacific DNA-T request quarantined and validate only the 11:30 Pacific RNA request before use

## Queue

| rank | target | model_set | status | reason | size_bytes | action |
| --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2341` | `R2341` | `ready_for_rule_checked_external_pool_acquisition` | `organizer_notice_first_rna_massivefold_set_available` | `667779936` | `casp17/rna_hybrid_massivefold_priority_queue/01_r2341/PRIORITY_ACTION.md` |
| `2` | `R2345` | `R2345` | `ready_for_rule_checked_external_pool_acquisition` | `corrected_1130_pacific_request_only_with_0930_invalid_dna_t_request_quarantined` | `245903877` | `casp17/rna_hybrid_massivefold_priority_queue/02_r2345/PRIORITY_ACTION.md` |
| `3` | `R2350` | `R2350` | `ready_for_rule_checked_external_pool_acquisition` | `rna_hybrid_massivefold_pool_from_organizer_ftp_listing` | `1362175616` | `casp17/rna_hybrid_massivefold_priority_queue/03_r2350/PRIORITY_ACTION.md` |
| `4` | `R2351` | `R2351` | `ready_for_rule_checked_external_pool_acquisition` | `rna_hybrid_massivefold_pool_from_organizer_ftp_listing` | `1361443421` | `casp17/rna_hybrid_massivefold_priority_queue/04_r2351/PRIORITY_ACTION.md` |
| `5` | `R2352` | `R2352` | `ready_for_rule_checked_external_pool_acquisition` | `rna_hybrid_massivefold_pool_from_organizer_ftp_listing` | `1362404890` | `casp17/rna_hybrid_massivefold_priority_queue/05_r2352/PRIORITY_ACTION.md` |
| `6` | `R2353` | `R2353` | `ready_for_rule_checked_external_pool_acquisition` | `rna_hybrid_massivefold_pool_from_organizer_ftp_listing` | `1378962270` | `casp17/rna_hybrid_massivefold_priority_queue/06_r2353/PRIORITY_ACTION.md` |

## Claim Boundary

RNA/hybrid MassiveFold priority queue only. These rows are organizer-provided external model pools for rule-checked reranking and accuracy-estimation work. They are not internal predictions, not CASP submissions, and not competitive-proof evidence.

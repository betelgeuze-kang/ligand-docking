# CASP17 MassiveFold Model1 Probe Outcome

- generated: `2026-06-01T23:05:35+09:00`
- status: `massivefold_model1_probe_outcome_ready_external_only`
- outcomes ready/blocked/total: `4/0/4`
- pass/fail/freeze-ready: `3/1/3`
- probes top5/lightweight: `2/2`
- RNA/protein-complex: `3/1`
- first outcome: `R2350` `rna_hybrid` `probe_pass_model1_retained` margin `0.64247` recommendation `conditional_model1_freeze_ready_external_only`
- scoring_rule_id: `no_native_probe_rescore_v1`
- next action: feed probe outcomes into the model1 freeze decision packet while preserving no-native boundaries

## Outcomes

| rank | target | group | probe | model1 score | top score | margin | result | freeze recommendation | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2350` | `rna_hybrid` | `top5_rerank_consistency_probe` | `83.16028` | `83.16028` | `0.64247` | `probe_pass_model1_retained` | `conditional_model1_freeze_ready_external_only` | `casp17/massivefold_model1_probe_outcomes/01_rna_hybrid_r2350/PROBE_OUTCOME.md` |
| `2` | `R2353` | `rna_hybrid` | `top5_rerank_consistency_probe` | `80.27838` | `80.27838` | `0.78355` | `probe_pass_model1_retained` | `conditional_model1_freeze_ready_external_only` | `casp17/massivefold_model1_probe_outcomes/02_rna_hybrid_r2353/PROBE_OUTCOME.md` |
| `3` | `H2312` | `protein_complex` | `lightweight_rescore_probe` | `100.91509` | `100.91509` | `0.10755` | `probe_pass_model1_retained` | `watch_model1_freeze_ready_after_probe` | `casp17/massivefold_model1_probe_outcomes/03_protein_complex_h2312/PROBE_OUTCOME.md` |
| `4` | `R2352` | `rna_hybrid` | `lightweight_rescore_probe` | `82.33483` | `82.5707` | `-0.23587` | `probe_fail_model1_displaced` | `keep_model1_freeze_blocked_and_escalate_manual_review` | `casp17/massivefold_model1_probe_outcomes/04_rna_hybrid_r2352/PROBE_OUTCOME.md` |

## Claim Boundary

CASP17 MassiveFold model1 probe outcome packet only. Outcomes are no-native model-selection consistency checks from external self-assessment features. They are not native accuracy, internal prediction proof, or CASP submission evidence.

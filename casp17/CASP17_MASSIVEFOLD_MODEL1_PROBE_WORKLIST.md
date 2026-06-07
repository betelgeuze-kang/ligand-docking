# CASP17 MassiveFold Model1 Probe Worklist

- generated: `2026-06-01T22:55:14+09:00`
- status: `massivefold_model1_probe_worklist_ready_external_only`
- workitems ready/blocked/total: `4/0/4`
- probes top5/lightweight: `2/2`
- priority 1/2: `2/2`
- RNA/protein-complex: `3/1`
- first workitem: `R2350` `rna_hybrid` `64.686` `top5_rerank_consistency_probe`
- freeze_unlock_policy: `freeze_after_probe_allowed_only_if_exit_criterion_passes`
- next action: execute priority-1 no-native probes and write outcomes into the model1 freeze decision lane

## Workitems

| rank | priority | target | group | score | probe | status | features | exit criterion | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `1` | `R2350` | `rna_hybrid` | `64.686` | `top5_rerank_consistency_probe` | `probe_ready` | `confidence_gap,top5_spread,diversity_to_model1,geometry_outlier,low_confidence_fraction` | model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore | `casp17/massivefold_model1_probe_worklist/01_rna_hybrid_r2350/PROBE_WORKITEM.md` |
| `2` | `1` | `R2353` | `rna_hybrid` | `58.24` | `top5_rerank_consistency_probe` | `probe_ready` | `confidence_gap,top5_spread,diversity_to_model1,geometry_outlier,low_confidence_fraction` | model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore | `casp17/massivefold_model1_probe_worklist/02_rna_hybrid_r2353/PROBE_WORKITEM.md` |
| `3` | `2` | `H2312` | `protein_complex` | `48.165` | `lightweight_rescore_probe` | `probe_ready` | `confidence_gap,top5_spread,nearest_top5_distance,geometry_outlier` | no new high-risk flag appears after targeted no-native rescore | `casp17/massivefold_model1_probe_worklist/03_protein_complex_h2312/PROBE_WORKITEM.md` |
| `4` | `2` | `R2352` | `rna_hybrid` | `30.586` | `lightweight_rescore_probe` | `probe_ready` | `confidence_gap,top5_spread,nearest_top5_distance,geometry_outlier` | no new high-risk flag appears after targeted no-native rescore | `casp17/massivefold_model1_probe_worklist/04_rna_hybrid_r2352/PROBE_WORKITEM.md` |

## Claim Boundary

CASP17 MassiveFold model1 probe worklist only. It turns external no-native calibration gates into executable probe workitems for model1 selection. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.

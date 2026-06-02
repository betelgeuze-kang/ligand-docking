# CASP17 MassiveFold Critical Rerank Experiment

- generated: `2026-06-01T22:34:40+09:00`
- status: `massivefold_critical_rerank_experiment_ready_external_only`
- experiments ready/blocked/total: `4/0/4`
- RNA/protein-complex experiments: `3/1`
- high-diversity/geometry/low-confidence reviews: `2/2/1`
- first experiment: `R2350` `rna_hybrid` `0.02292` `top5_diversity_then_geometry_then_model1_gap`
- rerank_formula_id: `gap_plus_geometry_plus_diversity_penalty_v1`
- calibration_probe_id: `model1_top5_near_tie_no_native_probe_v1`
- next action: run the critical no-native rerank probes, then promote calibrated model1 selection rules back into the accuracy-estimation lane

## Experiments

| rank | queue | group | target | gap | severity | diversity | geometry | low-conf | order | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `1` | `rna_hybrid` | `R2350` | `0.02292` | `0.7708` | `high_diversity_review` | `geometry_watch` | `low_confidence_watch` | `top5_diversity_then_geometry_then_model1_gap` | `casp17/massivefold_critical_rerank_experiments/01_rna_hybrid_r2350/EXPERIMENT.md` |
| `2` | `2` | `rna_hybrid` | `R2352` | `0.07092` | `0.2908` | `moderate_diversity_review` | `geometry_watch` | `low_confidence_watch` | `model1_gap_then_geometry_then_top5_diversity` | `casp17/massivefold_critical_rerank_experiments/02_rna_hybrid_r2352/EXPERIMENT.md` |
| `3` | `3` | `protein_complex` | `H2312` | `0.0813` | `0.187` | `compact_top5_review` | `geometry_outlier_review` | `low_confidence_watch` | `interface_geometry_then_model1_gap_then_top5_diversity` | `casp17/massivefold_critical_rerank_experiments/03_protein_complex_h2312/EXPERIMENT.md` |
| `4` | `4` | `rna_hybrid` | `R2353` | `0.0928` | `0.072` | `high_diversity_review` | `geometry_outlier_review` | `low_confidence_atom_review` | `top5_diversity_then_geometry_then_model1_gap` | `casp17/massivefold_critical_rerank_experiments/04_rna_hybrid_r2353/EXPERIMENT.md` |

## Claim Boundary

CASP17 MassiveFold critical rerank experiment packet only. It converts external no-native model1 risk rows into rerank and calibration work items for accuracy estimation. It does not copy coordinates, use native structures, create internal competitive-proof evidence, or submit models.

# R2350 Critical Rerank Experiment

- experiment_rank: `1`
- queue_rank: `1`
- status: `ready_external_no_native_rerank_experiment`
- target_group: `rna_hybrid`
- risk_tier/gap/severity: `critical_model1_margin/0.02292/0.7708`
- model1: `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` `woPaired`
- spread/diversity/nearest: `0.19336/48.47025/25.783`
- geometry/low_confidence: `1.704/0.02703`
- review_flags: `high_diversity_review` `geometry_watch` `low_confidence_watch`
- recommended_review_order: `top5_diversity_then_geometry_then_model1_gap`
- rerank_formula_id: `gap_plus_geometry_plus_diversity_penalty_v1`
- calibration_probe_id: `model1_top5_near_tie_no_native_probe_v1`
- source_risk_action_md: `casp17/massivefold_model1_risk_queue/01_rna_hybrid_r2350/RISK_ACTION.md`

## Experiment Contract

Use model1/top5 self-assessment features only: confidence gap, top5 spread, diversity to model1, nearest top5 RMSD, geometry outlier score, and low-confidence atom fraction. Keep all native, submission, and internal-proof lanes closed.

## Claim Boundary

CASP17 MassiveFold critical rerank experiment packet only. It converts external no-native model1 risk rows into rerank and calibration work items for accuracy estimation. It does not copy coordinates, use native structures, create internal competitive-proof evidence, or submit models.

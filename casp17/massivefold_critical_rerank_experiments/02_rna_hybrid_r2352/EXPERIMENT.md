# R2352 Critical Rerank Experiment

- experiment_rank: `2`
- queue_rank: `2`
- status: `ready_external_no_native_rerank_experiment`
- target_group: `rna_hybrid`
- risk_tier/gap/severity: `critical_model1_margin/0.07092/0.2908`
- model1: `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` `woUnpaired`
- spread/diversity/nearest: `0.14128/29.4805/11.101`
- geometry/low_confidence: `2.326/0.02654`
- review_flags: `moderate_diversity_review` `geometry_watch` `low_confidence_watch`
- recommended_review_order: `model1_gap_then_geometry_then_top5_diversity`
- rerank_formula_id: `gap_plus_geometry_plus_diversity_penalty_v1`
- calibration_probe_id: `model1_top5_near_tie_no_native_probe_v1`
- source_risk_action_md: `casp17/massivefold_model1_risk_queue/02_rna_hybrid_r2352/RISK_ACTION.md`

## Experiment Contract

Use model1/top5 self-assessment features only: confidence gap, top5 spread, diversity to model1, nearest top5 RMSD, geometry outlier score, and low-confidence atom fraction. Keep all native, submission, and internal-proof lanes closed.

## Claim Boundary

CASP17 MassiveFold critical rerank experiment packet only. It converts external no-native model1 risk rows into rerank and calibration work items for accuracy estimation. It does not copy coordinates, use native structures, create internal competitive-proof evidence, or submit models.

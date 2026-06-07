# H2312 Critical Rerank Experiment

- experiment_rank: `3`
- queue_rank: `3`
- status: `ready_external_no_native_rerank_experiment`
- target_group: `protein_complex`
- risk_tier/gap/severity: `critical_model1_margin/0.0813/0.187`
- model1: `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` `afm_basic_v1`
- spread/diversity/nearest: `1.18232/18.18725/2.787`
- geometry/low_confidence: `3.127/0.00739`
- review_flags: `compact_top5_review` `geometry_outlier_review` `low_confidence_watch`
- recommended_review_order: `interface_geometry_then_model1_gap_then_top5_diversity`
- rerank_formula_id: `gap_plus_geometry_plus_diversity_penalty_v1`
- calibration_probe_id: `model1_top5_near_tie_no_native_probe_v1`
- source_risk_action_md: `casp17/massivefold_model1_risk_queue/03_protein_complex_h2312/RISK_ACTION.md`

## Experiment Contract

Use model1/top5 self-assessment features only: confidence gap, top5 spread, diversity to model1, nearest top5 RMSD, geometry outlier score, and low-confidence atom fraction. Keep all native, submission, and internal-proof lanes closed.

## Claim Boundary

CASP17 MassiveFold critical rerank experiment packet only. It converts external no-native model1 risk rows into rerank and calibration work items for accuracy estimation. It does not copy coordinates, use native structures, create internal competitive-proof evidence, or submit models.

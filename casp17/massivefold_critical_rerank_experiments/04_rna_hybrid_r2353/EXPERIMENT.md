# R2353 Critical Rerank Experiment

- experiment_rank: `4`
- queue_rank: `4`
- status: `ready_external_no_native_rerank_experiment`
- target_group: `rna_hybrid`
- risk_tier/gap/severity: `critical_model1_margin/0.0928/0.072`
- model1: `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` `woPaired`
- spread/diversity/nearest: `0.41312/53.534/23.011`
- geometry/low_confidence: `3.41/0.04459`
- review_flags: `high_diversity_review` `geometry_outlier_review` `low_confidence_atom_review`
- recommended_review_order: `top5_diversity_then_geometry_then_model1_gap`
- rerank_formula_id: `gap_plus_geometry_plus_diversity_penalty_v1`
- calibration_probe_id: `model1_top5_near_tie_no_native_probe_v1`
- source_risk_action_md: `casp17/massivefold_model1_risk_queue/04_rna_hybrid_r2353/RISK_ACTION.md`

## Experiment Contract

Use model1/top5 self-assessment features only: confidence gap, top5 spread, diversity to model1, nearest top5 RMSD, geometry outlier score, and low-confidence atom fraction. Keep all native, submission, and internal-proof lanes closed.

## Claim Boundary

CASP17 MassiveFold critical rerank experiment packet only. It converts external no-native model1 risk rows into rerank and calibration work items for accuracy estimation. It does not copy coordinates, use native structures, create internal competitive-proof evidence, or submit models.

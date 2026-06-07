# R2350 Model1 Probe Workitem

- workitem_rank: `1`
- gate_rank: `1`
- status: `ready_external_no_native_probe`
- risk_score: `64.686`
- model1_freeze_decision: `hold_model1_freeze_probe_required`
- probe_type/priority/status: `top5_rerank_consistency_probe/1/probe_ready`
- execution_mode: `no_native_external_self_assessment_rescore`
- required_inputs: `model1,top5,self_assessment_row,score_ledger_row,calibration_gate_row`
- scoring_features: `confidence_gap,top5_spread,diversity_to_model1,geometry_outlier,low_confidence_fraction`
- probe_exit_criterion: model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore
- freeze_after_probe_allowed: `true_if_exit_criterion_passes`
- source_calibration_gate_md: `casp17/massivefold_model1_selection_calibration_gate/01_rna_hybrid_r2350/CALIBRATION_GATE.md`

## Claim Boundary

CASP17 MassiveFold model1 probe worklist only. It turns external no-native calibration gates into executable probe workitems for model1 selection. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.

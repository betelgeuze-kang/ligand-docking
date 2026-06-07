# H2312 Model1 Probe Workitem

- workitem_rank: `3`
- gate_rank: `3`
- status: `ready_external_no_native_probe`
- risk_score: `48.165`
- model1_freeze_decision: `conditional_watch_probe_before_final_model1`
- probe_type/priority/status: `lightweight_rescore_probe/2/probe_ready`
- execution_mode: `no_native_external_self_assessment_rescore`
- required_inputs: `model1,top5,self_assessment_row,score_ledger_row,calibration_gate_row`
- scoring_features: `confidence_gap,top5_spread,nearest_top5_distance,geometry_outlier`
- probe_exit_criterion: no new high-risk flag appears after targeted no-native rescore
- freeze_after_probe_allowed: `true_if_exit_criterion_passes`
- source_calibration_gate_md: `casp17/massivefold_model1_selection_calibration_gate/03_protein_complex_h2312/CALIBRATION_GATE.md`

## Claim Boundary

CASP17 MassiveFold model1 probe worklist only. It turns external no-native calibration gates into executable probe workitems for model1 selection. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.

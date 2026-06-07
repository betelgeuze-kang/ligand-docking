# R2352 Model1 Selection Calibration Gate

- gate_rank: `4`
- ledger_rank: `4`
- risk_score/band: `30.586/critical_watch_with_targeted_probe`
- model1_freeze_decision: `conditional_watch_probe_before_final_model1`
- model1_freeze_blocker: `critical_watch_requires_rescore`
- probe_type: `lightweight_rescore_probe`
- probe_exit_criterion: no new high-risk flag appears after targeted no-native rescore
- selection_rule_id: `no_native_model1_selection_gate_v1`
- model1: `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` `woUnpaired`
- source_score_ledger_md: `casp17/massivefold_critical_rerank_score_ledger/04_rna_hybrid_r2352/SCORE_LEDGER.md`

## Claim Boundary

CASP17 MassiveFold model1 selection calibration gate only. It converts external no-native rerank score ledger rows into model1 freeze, hold, and probe decisions for accuracy-estimation workflow. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.

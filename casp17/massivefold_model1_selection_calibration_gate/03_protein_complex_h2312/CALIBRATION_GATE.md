# H2312 Model1 Selection Calibration Gate

- gate_rank: `3`
- ledger_rank: `3`
- risk_score/band: `48.165/critical_watch_with_targeted_probe`
- model1_freeze_decision: `conditional_watch_probe_before_final_model1`
- model1_freeze_blocker: `critical_watch_requires_rescore`
- probe_type: `lightweight_rescore_probe`
- probe_exit_criterion: no new high-risk flag appears after targeted no-native rescore
- selection_rule_id: `no_native_model1_selection_gate_v1`
- model1: `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` `afm_basic_v1`
- source_score_ledger_md: `casp17/massivefold_critical_rerank_score_ledger/03_protein_complex_h2312/SCORE_LEDGER.md`

## Claim Boundary

CASP17 MassiveFold model1 selection calibration gate only. It converts external no-native rerank score ledger rows into model1 freeze, hold, and probe decisions for accuracy-estimation workflow. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.

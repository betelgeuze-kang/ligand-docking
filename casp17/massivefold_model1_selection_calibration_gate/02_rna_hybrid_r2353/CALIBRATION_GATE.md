# R2353 Model1 Selection Calibration Gate

- gate_rank: `2`
- ledger_rank: `2`
- risk_score/band: `58.24/calibrate_before_model1_freeze`
- model1_freeze_decision: `hold_model1_freeze_probe_required`
- model1_freeze_blocker: `calibration_required_before_freeze`
- probe_type: `top5_rerank_consistency_probe`
- probe_exit_criterion: model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore
- selection_rule_id: `no_native_model1_selection_gate_v1`
- model1: `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` `woPaired`
- source_score_ledger_md: `casp17/massivefold_critical_rerank_score_ledger/02_rna_hybrid_r2353/SCORE_LEDGER.md`

## Claim Boundary

CASP17 MassiveFold model1 selection calibration gate only. It converts external no-native rerank score ledger rows into model1 freeze, hold, and probe decisions for accuracy-estimation workflow. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.

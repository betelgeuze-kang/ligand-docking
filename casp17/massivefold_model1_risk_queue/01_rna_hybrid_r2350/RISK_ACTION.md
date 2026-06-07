# R2350 Model1 Risk Action

- queue_rank: `1`
- target_group: `rna_hybrid`
- target_family: `rna_hybrid`
- risk_tier: `critical_model1_margin`
- confidence_gap/threshold: `0.02292/1`
- model1: `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` `woPaired`
- top5 mean/spread: `83.235968/0.19336`
- diversity/nearest: `48.47025/25.783`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

# R2352 Model1 Risk Action

- queue_rank: `2`
- target_group: `rna_hybrid`
- target_family: `rna_hybrid`
- risk_tier: `critical_model1_margin`
- confidence_gap/threshold: `0.07092/1`
- model1: `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` `woUnpaired`
- top5 mean/spread: `82.610732/0.14128`
- diversity/nearest: `29.4805/11.101`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

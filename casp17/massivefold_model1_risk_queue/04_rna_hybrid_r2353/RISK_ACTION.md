# R2353 Model1 Risk Action

- queue_rank: `4`
- target_group: `rna_hybrid`
- target_family: `rna_hybrid`
- risk_tier: `critical_model1_margin`
- confidence_gap/threshold: `0.0928/1`
- model1: `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` `woPaired`
- top5 mean/spread: `80.324588/0.41312`
- diversity/nearest: `53.534/23.011`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

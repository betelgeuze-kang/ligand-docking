# R2341 Model1 Risk Action

- queue_rank: `5`
- target_group: `rna_hybrid`
- target_family: `rna_hybrid`
- risk_tier: `high_model1_margin`
- confidence_gap/threshold: `0.10906/1`
- model1: `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` `basic`
- top5 mean/spread: `52.548/1.07352`
- diversity/nearest: `53.2865/24.18`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

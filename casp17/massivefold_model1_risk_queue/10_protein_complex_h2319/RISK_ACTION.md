# H2319 Model1 Risk Action

- queue_rank: `10`
- target_group: `protein_complex`
- target_family: `heteromer_or_immune_complex`
- risk_tier: `high_model1_margin`
- confidence_gap/threshold: `0.56512/2`
- model1: `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` `afm_basic_v3`
- top5 mean/spread: `103.882788/4.04092`
- diversity/nearest: `43.949/23.482`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

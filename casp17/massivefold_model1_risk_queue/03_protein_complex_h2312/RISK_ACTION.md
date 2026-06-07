# H2312 Model1 Risk Action

- queue_rank: `3`
- target_group: `protein_complex`
- target_family: `heteromer_or_immune_complex`
- risk_tier: `critical_model1_margin`
- confidence_gap/threshold: `0.0813/2`
- model1: `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` `afm_basic_v1`
- top5 mean/spread: `101.033084/1.18232`
- diversity/nearest: `18.18725/2.787`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

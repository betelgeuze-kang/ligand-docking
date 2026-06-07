# H1311 Model1 Risk Action

- queue_rank: `8`
- target_group: `protein_complex`
- target_family: `heteromer_or_immune_complex`
- risk_tier: `high_model1_margin`
- confidence_gap/threshold: `0.3313/2`
- model1: `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` `afm_basic_v3`
- top5 mean/spread: `102.85846/2.55002`
- diversity/nearest: `31.10125/2.431`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

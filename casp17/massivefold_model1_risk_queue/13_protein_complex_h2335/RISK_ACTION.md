# H2335 Model1 Risk Action

- queue_rank: `13`
- target_group: `protein_complex`
- target_family: `heteromer_or_immune_complex`
- risk_tier: `high_model1_margin`
- confidence_gap/threshold: `1.11502/2`
- model1: `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` `afm_basic_v1`
- top5 mean/spread: `93.073392/1.6303`
- diversity/nearest: `57.9835/21.59`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

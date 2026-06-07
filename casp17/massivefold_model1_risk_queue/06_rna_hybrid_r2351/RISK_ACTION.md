# R2351 Model1 Risk Action

- queue_rank: `6`
- target_group: `rna_hybrid`
- target_family: `rna_hybrid`
- risk_tier: `high_model1_margin`
- confidence_gap/threshold: `0.131/1`
- model1: `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` `woTemplates`
- top5 mean/spread: `83.709572/0.25478`
- diversity/nearest: `57.00825/41.318`
- sequence_guard: `-`
- next_action: manually review model1 versus top5 diversity and geometry, then add a rerank/calibration experiment before treating model1 as stable

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

# T2313 Model1 Risk Action

- queue_rank: `15`
- target_group: `protein_complex`
- target_family: `protein_monomer_or_homomer_pool`
- risk_tier: `watch_model1_margin`
- confidence_gap/threshold: `2.56834/2`
- model1: `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` `afm_woTemplates_v3`
- top5 mean/spread: `79.995/5.2837`
- diversity/nearest: `53.82425/17.703`
- sequence_guard: `-`
- next_action: keep as lower-priority external model1 watch item and revisit after low-margin targets

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

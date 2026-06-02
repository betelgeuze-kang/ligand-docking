# R2352 Watch/Manual Action

- status: `watch_manual_action_ready_external_only`
- action class: `manual_alternate_review`
- priority: `1`
- decision class: `manual_block`
- final selector decision: `external_model1_freeze_blocked_manual_review`
- selected model: `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif`
- alternate model: `Model_7_af3_woPaired_woTemplates_af3_seed_26386_sample_2_pred_237.cif`
- probe result/margin: `probe_fail_model1_displaced` `-0.23587`
- viewer: `casp17/massivefold_representative_viewers/r2352/selection_034_woUnpaired_model_15/viewer.html`
- top5 manifest: `casp17/massivefold_representative_rerank/r2352/top5_manifest.csv`
- source decision: `casp17/massivefold_post_probe_selector_decision_packet/01_manual_block_r2352/SELECTOR_DECISION.md`
- blockers: `-`

## Review Question

Should the alternate/top candidate replace model1, or should this target remain blocked?

## Exit Criterion

operator records manual decision; do not freeze model1 until alternate/model1 choice is approved

## Claim Boundary

CASP17 MassiveFold watch/manual action packet only. It turns external no-native post-probe selector holds into review actions for low-margin, interface, and manual-block cases. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

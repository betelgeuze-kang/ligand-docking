# H1311 Watch/Manual Action

- status: `watch_manual_action_ready_external_only`
- action class: `low_margin_top5_review`
- priority: `2`
- decision class: `watch_low_margin_after_probe`
- final selector decision: `external_model1_watch_low_margin_after_targeted_probe`
- selected model: `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb`
- alternate model: `-`
- probe result/margin: `probe_watch_model1_retained_low_margin` `0.31936`
- viewer: `casp17/massivefold_representative_viewers/h1311/selection_024_afm_basic_v3_model_5/viewer.html`
- top5 manifest: `casp17/massivefold_representative_rerank/h1311/top5_manifest.csv`
- source decision: `casp17/massivefold_post_probe_selector_decision_packet/03_watch_low_margin_after_probe_h1311/SELECTOR_DECISION.md`
- blockers: `-`

## Review Question

Does model1 remain acceptable after inspecting the nearest top5 competitor and margin?

## Exit Criterion

operator accepts low-margin model1 or reranks the top5 before any freeze

## Claim Boundary

CASP17 MassiveFold watch/manual action packet only. It turns external no-native post-probe selector holds into review actions for low-margin, interface, and manual-block cases. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

# H2324 Watch/Manual Action

- status: `watch_manual_action_ready_external_only`
- action class: `low_margin_top5_review`
- priority: `2`
- decision class: `watch_low_margin_after_probe`
- final selector decision: `external_model1_watch_low_margin_after_targeted_probe`
- selected model: `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb`
- alternate model: `-`
- probe result/margin: `probe_watch_model1_retained_low_margin` `0.35564`
- viewer: `casp17/massivefold_representative_viewers/h2324/selection_115_afm_basic_v1_model_4760/viewer.html`
- top5 manifest: `casp17/massivefold_representative_rerank/h2324/top5_manifest.csv`
- source decision: `casp17/massivefold_post_probe_selector_decision_packet/06_watch_low_margin_after_probe_h2324/SELECTOR_DECISION.md`
- blockers: `-`

## Review Question

Does model1 remain acceptable after inspecting the nearest top5 competitor and margin?

## Exit Criterion

operator accepts low-margin model1 or reranks the top5 before any freeze

## Claim Boundary

CASP17 MassiveFold watch/manual action packet only. It turns external no-native post-probe selector holds into review actions for low-margin, interface, and manual-block cases. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

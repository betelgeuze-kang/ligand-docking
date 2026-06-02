# H2312 Watch/Manual Action

- status: `watch_manual_action_ready_external_only`
- action class: `interface_geometry_review`
- priority: `1`
- decision class: `interface_hold`
- final selector decision: `external_model1_interface_hold_before_freeze`
- selected model: `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb`
- alternate model: `-`
- probe result/margin: `probe_pass_model1_retained` `0.10755`
- viewer: `casp17/massivefold_representative_viewers/h2312/selection_122_afm_basic_v1_model_7550/viewer.html`
- top5 manifest: `casp17/massivefold_representative_rerank/h2312/top5_manifest.csv`
- source decision: `casp17/massivefold_post_probe_selector_decision_packet/02_interface_hold_h2312/SELECTOR_DECISION.md`
- blockers: `-`

## Review Question

Does the model1 interface/assembly clear chain geometry, clash, and stoichiometry review?

## Exit Criterion

interface review clears chain geometry and no new high-risk assembly flag remains

## Claim Boundary

CASP17 MassiveFold watch/manual action packet only. It turns external no-native post-probe selector holds into review actions for low-margin, interface, and manual-block cases. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

# CASP17 MassiveFold Watch/Manual Action Packet

- generated: `2026-06-02T02:06:08+09:00`
- status: `massivefold_watch_manual_action_packet_ready_external_only`
- actions ready/blocked/total: `5/0/5`
- classes manual/interface/low-margin: `1/1/3`
- priority 1/2: `2/3`
- RNA/protein-complex: `2/3`
- model/viewer/projection/top5/alternate: `5/5/5/5/1`
- first action: `R2352` `manual_alternate_review` priority `1`
- proof eligible: `False` policy `do_not_mark_as_internal_prediction`
- next action: operator resolves the five watch/manual/interface actions before any CASP rule-checked formatting

## Actions

| rank | target | class | priority | margin | question | viewer | action | blockers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2352` | `manual_alternate_review` | `1` | `-0.23587` | Should the alternate/top candidate replace model1, or should this target remain blocked? | `casp17/massivefold_representative_viewers/r2352/selection_034_woUnpaired_model_15/viewer.html` | `casp17/massivefold_watch_manual_action_packet/01_manual_alternate_review_r2352/WATCH_MANUAL_ACTION.md` | `-` |
| `2` | `H2312` | `interface_geometry_review` | `1` | `0.10755` | Does the model1 interface/assembly clear chain geometry, clash, and stoichiometry review? | `casp17/massivefold_representative_viewers/h2312/selection_122_afm_basic_v1_model_7550/viewer.html` | `casp17/massivefold_watch_manual_action_packet/02_interface_geometry_review_h2312/WATCH_MANUAL_ACTION.md` | `-` |
| `3` | `H1311` | `low_margin_top5_review` | `2` | `0.31936` | Does model1 remain acceptable after inspecting the nearest top5 competitor and margin? | `casp17/massivefold_representative_viewers/h1311/selection_024_afm_basic_v3_model_5/viewer.html` | `casp17/massivefold_watch_manual_action_packet/03_low_margin_top5_review_h1311/WATCH_MANUAL_ACTION.md` | `-` |
| `4` | `H2324` | `low_margin_top5_review` | `2` | `0.35564` | Does model1 remain acceptable after inspecting the nearest top5 competitor and margin? | `casp17/massivefold_representative_viewers/h2324/selection_115_afm_basic_v1_model_4760/viewer.html` | `casp17/massivefold_watch_manual_action_packet/04_low_margin_top5_review_h2324/WATCH_MANUAL_ACTION.md` | `-` |
| `5` | `R2351` | `low_margin_top5_review` | `2` | `0.29014` | Does model1 remain acceptable after inspecting the nearest top5 competitor and margin? | `casp17/massivefold_representative_viewers/r2351/selection_026_woTemplates_model_18/viewer.html` | `casp17/massivefold_watch_manual_action_packet/05_low_margin_top5_review_r2351/WATCH_MANUAL_ACTION.md` | `-` |

## Claim Boundary

CASP17 MassiveFold watch/manual action packet only. It turns external no-native post-probe selector holds into review actions for low-margin, interface, and manual-block cases. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

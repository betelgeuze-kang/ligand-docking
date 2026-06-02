# H1311 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_watch_model1_retained_low_margin`
- recommendation: `external_model1_watch_low_margin_after_probe`
- primary model: `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb`
- model1/top/margin: `103.92292/103.92292/0.31936`
- top candidate: `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `103.92292` | `104.19842` | `1.102` | `-` | `-` | `casp17/massivefold_representative_viewers/h1311/selection_024_afm_basic_v3_model_5/viewer.html` |
| `2` | `competitor` | `Model_16_afm_dropout_full_model_4_multimer_v3_pred_36.pdb` | `103.60356` | `103.86712` | `0.957` | `-` | `2.431` | `casp17/massivefold_representative_viewers/h1311/selection_085_afm_dropout_full_v3_model_16/viewer.html` |
| `3` | `competitor` | `Model_5030_afm_dropout_full_model_5_multimer_v1_pred_14.pdb` | `101.96962` | `102.47614` | `0.499` | `0.01194` | `35.789` | `casp17/massivefold_representative_viewers/h1311/selection_015_afm_dropout_full_v1_model_5030/viewer.html` |
| `4` | `competitor` | `Model_402_afm_basic_model_2_multimer_v2_pred_0.pdb` | `100.74058` | `101.6484` | `2.575` | `0.01527` | `23.353` | `casp17/massivefold_representative_viewers/h1311/selection_082_afm_basic_v2_model_402/viewer.html` |
| `5` | `competitor` | `Model_4160_afm_basic_model_1_multimer_v1_pred_46.pdb` | `100.56225` | `102.10222` | `3.597` | `0.0062` | `62.832` | `casp17/massivefold_representative_viewers/h1311/selection_122_afm_basic_v1_model_4160/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

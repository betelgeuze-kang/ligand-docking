# H2321 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb`
- model1/top/margin: `101.20392/101.20392/0.85011`
- top candidate: `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `101.20392` | `102.10998` | `3.608` | `0.00203` | `-` | `casp17/massivefold_representative_viewers/h2321/selection_086_afm_dropout_full_v3_model_3/viewer.html` |
| `2` | `competitor` | `Model_14_afm_basic_model_1_multimer_v2_pred_43.pdb` | `100.35381` | `101.4412` | `3.04` | `0.00292` | `32.155` | `casp17/massivefold_representative_viewers/h2321/selection_053_afm_basic_v2_model_14/viewer.html` |
| `3` | `competitor` | `Model_5_afm_dropout_full_model_2_multimer_v2_pred_42.pdb` | `100.09869` | `101.13708` | `2.483` | `0.00178` | `41.408` | `casp17/massivefold_representative_viewers/h2321/selection_093_afm_dropout_full_v2_model_5/viewer.html` |
| `4` | `competitor` | `Model_70_afm_basic_model_4_multimer_v3_pred_64.pdb` | `99.80476` | `100.98888` | `3.153` | `0.00203` | `39.181` | `casp17/massivefold_representative_viewers/h2321/selection_125_afm_basic_v3_model_70/viewer.html` |
| `5` | `competitor` | `Model_8_afm_dropout_noSM_woTemplates_model_3_multimer_v3_pred_1.pdb` | `97.61714` | `98.5448` | `1.75` | `0.01623` | `45.77` | `casp17/massivefold_representative_viewers/h2321/selection_077_afm_dropout_noSM_woTemplates_v3_model_8/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

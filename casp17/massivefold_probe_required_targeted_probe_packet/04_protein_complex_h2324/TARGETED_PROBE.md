# H2324 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_watch_model1_retained_low_margin`
- recommendation: `external_model1_watch_low_margin_after_probe`
- primary model: `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb`
- model1/top/margin: `99.50531/99.50531/0.35564`
- top candidate: `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `99.50531` | `99.93822` | `1.437` | `0.03683` | `-` | `casp17/massivefold_representative_viewers/h2324/selection_115_afm_basic_v1_model_4760/viewer.html` |
| `2` | `competitor` | `Model_6_afm_woTemplates_model_2_multimer_v3_pred_24.pdb` | `99.14967` | `99.75348` | `0.338` | `0.02941` | `46.049` | `casp17/massivefold_representative_viewers/h2324/selection_038_afm_woTemplates_v3_model_6/viewer.html` |
| `3` | `competitor` | `Model_75_afm_woTemplates_model_1_multimer_v1_pred_19.pdb` | `98.66325` | `99.7622` | `1.66` | `0.03348` | `61.699` | `casp17/massivefold_representative_viewers/h2324/selection_043_afm_woTemplates_v1_model_75/viewer.html` |
| `4` | `competitor` | `Model_44_cf_woTemplates_model_4_multimer_v3_pred_19.pdb` | `98.60597` | `99.66466` | `1.561` | `0.03028` | `60.788` | `casp17/massivefold_representative_viewers/h2324/selection_082_cf_woTemplates_v3_model_44/viewer.html` |
| `5` | `competitor` | `Model_4_afm_dropout_noSM_woTemplates_model_4_multimer_v3_pred_25.pdb` | `98.52942` | `99.36256` | `0.596` | `0.03086` | `62.242` | `casp17/massivefold_representative_viewers/h2324/selection_040_afm_dropout_noSM_woTemplates_v3_model_4/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

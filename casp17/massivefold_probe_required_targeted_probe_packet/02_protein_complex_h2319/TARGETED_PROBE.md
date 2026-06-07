# H2319 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb`
- model1/top/margin: `105.17261/105.17261/1.19016`
- top candidate: `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `105.17261` | `105.48786` | `1.261` | `-` | `-` | `casp17/massivefold_representative_viewers/h2319/selection_125_afm_basic_v3_model_1/viewer.html` |
| `2` | `competitor` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_65.pdb` | `103.98245` | `104.92274` | `1.664` | `-` | `52.429` | `casp17/massivefold_representative_viewers/h2319/selection_001_afm_dropout_full_v3_model_2/viewer.html` |
| `3` | `competitor` | `Model_10_afm_dropout_full_model_1_multimer_v2_pred_30.pdb` | `103.27026` | `103.75186` | `0.351` | `-` | `39.385` | `casp17/massivefold_representative_viewers/h2319/selection_051_afm_dropout_full_v2_model_10/viewer.html` |
| `4` | `competitor` | `Model_12_afm_basic_model_1_multimer_v2_pred_64.pdb` | `102.90832` | `103.80454` | `1.399` | `-` | `54.647` | `casp17/massivefold_representative_viewers/h2319/selection_087_afm_basic_v2_model_12/viewer.html` |
| `5` | `competitor` | `Model_6_cf_woTemplates_model_4_multimer_v3_pred_24.pdb` | `100.48452` | `101.44694` | `2.569` | `0.01341` | `29.335` | `casp17/massivefold_representative_viewers/h2319/selection_044_cf_woTemplates_v3_model_6/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

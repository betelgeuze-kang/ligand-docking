# T2313 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb`
- model1/top/margin: `82.64596/82.64596/3.20754`
- top candidate: `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `82.64596` | `83.5072` | `2.36` | `0.13562` | `-` | `casp17/massivefold_representative_viewers/t2313/selection_085_afm_woTemplates_v3_model_5/viewer.html` |
| `2` | `competitor` | `Model_10_afm_dropout_noSM_woTemplates_model_5_multimer_v3_pred_11.pdb` | `79.43842` | `80.93886` | `2.751` | `0.14552` | `52.165` | `casp17/massivefold_representative_viewers/t2313/selection_125_afm_dropout_noSM_woTemplates_v3_model_10/viewer.html` |
| `3` | `competitor` | `Model_63_af3_basic_af3_seed_704032_sample_0_pred_520.cif` | `77.43172` | `78.90796` | `2.731` | `0.09953` | `59.443` | `casp17/massivefold_representative_viewers/t2313/selection_050_basic_model_63/viewer.html` |
| `4` | `competitor` | `Model_69_af3_woPaired_af3_seed_880568_sample_2_pred_47.cif` | `77.06541` | `78.39748` | `2.463` | `0.10057` | `51.518` | `casp17/massivefold_representative_viewers/t2313/selection_051_woPaired_model_69/viewer.html` |
| `5` | `competitor` | `Model_4_afm_dropout_full_model_4_multimer_v3_pred_44.pdb` | `76.20928` | `78.2235` | `4.555` | `0.17688` | `52.171` | `casp17/massivefold_representative_viewers/t2313/selection_091_afm_dropout_full_v3_model_4/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

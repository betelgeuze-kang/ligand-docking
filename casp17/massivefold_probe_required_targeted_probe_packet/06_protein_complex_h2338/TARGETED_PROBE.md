# H2338 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb`
- model1/top/margin: `103.70431/103.70431/0.86919`
- top candidate: `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `103.70431` | `103.87838` | `0.653` | `0.00541` | `-` | `casp17/massivefold_representative_viewers/h2338/selection_029_afm_dropout_full_v3_model_2/viewer.html` |
| `2` | `competitor` | `Model_4_afm_basic_model_4_multimer_v3_pred_63.pdb` | `102.83512` | `103.42614` | `0.809` | `0.00934` | `37.009` | `casp17/massivefold_representative_viewers/h2338/selection_096_afm_basic_v3_model_4/viewer.html` |
| `3` | `competitor` | `Model_29_afm_basic_model_4_multimer_v2_pred_25.pdb` | `102.29163` | `102.95262` | `1.967` | `0.00934` | `15.056` | `casp17/massivefold_representative_viewers/h2338/selection_054_afm_basic_v2_model_29/viewer.html` |
| `4` | `competitor` | `Model_1755_cf_woTemplates_model_5_multimer_v1_pred_12.pdb` | `100.71836` | `102.09926` | `2.486` | `0.01094` | `73.752` | `casp17/massivefold_representative_viewers/h2338/selection_129_cf_woTemplates_v1_model_1755/viewer.html` |
| `5` | `competitor` | `Model_508_afm_basic_model_5_multimer_v1_pred_28.pdb` | `99.51296` | `102.41998` | `9.003` | `0.00676` | `64.275` | `casp17/massivefold_representative_viewers/h2338/selection_016_afm_basic_v1_model_508/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

# H2312 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` `afm_basic_v1`
- model1/runner-up/gap: `101.58484/101.50354/0.0813`
- top5 score mean/spread: `101.033084/1.18232`
- diversity/nearest: `18.18725/2.787`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `afm_basic_v1` | `101.58484` | `0` | `2.787` | `2.679` | `0.00141` | `0.96902` |
| `2` | `top5_decoy` | `Model_6050_cf_woTemplates_model_5_multimer_v1_pred_26.pdb` | `cf_woTemplates_v1` | `101.50354` | `56.614` | `55.791` | `2.784` | `0.00739` | `0.96577` |
| `3` | `top5_decoy` | `Model_8659_afm_woTemplates_model_5_multimer_v1_pred_61.pdb` | `afm_woTemplates_v1` | `100.90322` | `7.065` | `7.065` | `3.127` | `0.0029` | `0.96093` |
| `4` | `top5_decoy` | `Model_7811_afm_dropout_full_model_5_multimer_v1_pred_66.pdb` | `afm_dropout_full_v1` | `100.7713` | `2.787` | `2.787` | `2.65` | `0.00202` | `0.96647` |
| `5` | `top5_decoy` | `Model_8060_afm_dropout_noSM_woTemplates_model_5_multimer_v1_pred_55.pdb` | `afm_dropout_noSM_woTemplates_v1` | `100.40252` | `6.283` | `6.283` | `1.932` | `0.00299` | `0.96586` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

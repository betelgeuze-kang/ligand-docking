# H2338 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` `afm_dropout_full_v3`
- model1/runner-up/gap: `103.87838/103.42614/0.45224`
- top5 score mean/spread: `102.955276/1.77912`
- diversity/nearest: `47.523/15.056`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `afm_dropout_full_v3` | `103.87838` | `0` | `15.056` | `0.653` | `0.00541` | `0.97147` |
| `2` | `top5_decoy` | `Model_4_afm_basic_model_4_multimer_v3_pred_63.pdb` | `afm_basic_v3` | `103.42614` | `37.009` | `35.093` | `0.809` | `0.00934` | `0.97233` |
| `3` | `top5_decoy` | `Model_29_afm_basic_model_4_multimer_v2_pred_25.pdb` | `afm_basic_v2` | `102.95262` | `15.056` | `15.056` | `1.967` | `0.00934` | `0.97111` |
| `4` | `top5_decoy` | `Model_508_afm_basic_model_5_multimer_v1_pred_28.pdb` | `afm_basic_v1` | `102.41998` | `64.275` | `30.789` | `9.003` | `0.00676` | `0.97713` |
| `5` | `top5_decoy` | `Model_1755_cf_woTemplates_model_5_multimer_v1_pred_12.pdb` | `cf_woTemplates_v1` | `102.09926` | `73.752` | `30.789` | `2.486` | `0.01094` | `0.97455` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

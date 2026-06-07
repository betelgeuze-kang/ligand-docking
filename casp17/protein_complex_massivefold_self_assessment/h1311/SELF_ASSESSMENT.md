# H1311 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` `afm_basic_v3`
- model1/runner-up/gap: `104.19842/103.86712/0.3313`
- top5 score mean/spread: `102.85846/2.55002`
- diversity/nearest: `31.10125/2.431`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `afm_basic_v3` | `104.19842` | `0` | `2.431` | `1.102` | `0` | `0.98745` |
| `2` | `top5_decoy` | `Model_16_afm_dropout_full_model_4_multimer_v3_pred_36.pdb` | `afm_dropout_full_v3` | `103.86712` | `2.431` | `2.431` | `0.957` | `0` | `0.98624` |
| `3` | `top5_decoy` | `Model_5030_afm_dropout_full_model_5_multimer_v1_pred_14.pdb` | `afm_dropout_full_v1` | `102.47614` | `35.789` | `34.085` | `0.499` | `0.01194` | `0.97959` |
| `4` | `top5_decoy` | `Model_4160_afm_basic_model_1_multimer_v1_pred_46.pdb` | `afm_basic_v1` | `102.10222` | `62.832` | `61.746` | `3.597` | `0.0062` | `0.97581` |
| `5` | `top5_decoy` | `Model_402_afm_basic_model_2_multimer_v2_pred_0.pdb` | `afm_basic_v2` | `101.6484` | `23.353` | `23.353` | `2.575` | `0.01527` | `0.97838` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

# H2335 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` `afm_basic_v1`
- model1/runner-up/gap: `94.11582/93.0008/1.11502`
- top5 score mean/spread: `93.073392/1.6303`
- diversity/nearest: `57.9835/21.59`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `afm_basic_v1` | `94.11582` | `0` | `21.59` | `6.857` | `0.04696` | `0.90013` |
| `2` | `top5_decoy` | `Model_12_afm_basic_model_4_multimer_v3_pred_12.pdb` | `afm_basic_v3` | `93.0008` | `78.846` | `40.056` | `3.27` | `0.06836` | `0.87838` |
| `3` | `top5_decoy` | `Model_7964_afm_dropout_full_model_5_multimer_v1_pred_41.pdb` | `afm_dropout_full_v1` | `92.90986` | `21.59` | `21.59` | `6.446` | `0.05624` | `0.89515` |
| `4` | `top5_decoy` | `Model_7659_cf_woTemplates_model_5_multimer_v1_pred_18.pdb` | `cf_woTemplates_v1` | `92.85496` | `52.585` | `52.585` | `5.241` | `0.04619` | `0.87354` |
| `5` | `top5_decoy` | `Model_40_afm_dropout_full_model_4_multimer_v3_pred_48.pdb` | `afm_dropout_full_v3` | `92.48552` | `78.913` | `40.056` | `2.322` | `0.07161` | `0.87236` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

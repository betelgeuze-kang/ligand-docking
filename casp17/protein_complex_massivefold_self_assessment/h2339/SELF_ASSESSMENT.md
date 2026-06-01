# H2339 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` `afm_basic_v1`
- model1/runner-up/gap: `102.90764/102.1607/0.74694`
- top5 score mean/spread: `101.466988/2.39072`
- diversity/nearest: `52.00175/36.62`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `afm_basic_v1` | `102.90764` | `0` | `36.62` | `1.589` | `0.00308` | `0.97288` |
| `2` | `top5_decoy` | `Model_174_afm_dropout_full_model_5_multimer_v1_pred_22.pdb` | `afm_dropout_full_v1` | `102.1607` | `36.62` | `36.62` | `0.475` | `0.00308` | `0.96893` |
| `3` | `top5_decoy` | `Model_1_afm_basic_model_4_multimer_v2_pred_44.pdb` | `afm_basic_v2` | `100.96566` | `58.971` | `39.506` | `3.881` | `0.00986` | `0.95821` |
| `4` | `top5_decoy` | `Model_444_afm_woTemplates_model_4_multimer_v1_pred_50.pdb` | `afm_woTemplates_v1` | `100.78402` | `56.944` | `39.506` | `0.597` | `0.01196` | `0.96881` |
| `5` | `top5_decoy` | `Model_974_cf_woTemplates_model_5_multimer_v1_pred_18.pdb` | `cf_woTemplates_v1` | `100.51692` | `55.472` | `46.738` | `1.842` | `0.01196` | `0.96598` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

# H2324 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` `afm_basic_v1`
- model1/runner-up/gap: `99.93822/99.7622/0.17602`
- top5 score mean/spread: `99.696224/0.57566`
- diversity/nearest: `57.6945/33.417`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `afm_basic_v1` | `99.93822` | `0` | `46.049` | `1.437` | `0.03683` | `0.94293` |
| `2` | `top5_decoy` | `Model_75_afm_woTemplates_model_1_multimer_v1_pred_19.pdb` | `afm_woTemplates_v1` | `99.7622` | `61.699` | `33.417` | `1.66` | `0.03348` | `0.94482` |
| `3` | `top5_decoy` | `Model_6_afm_woTemplates_model_2_multimer_v3_pred_24.pdb` | `afm_woTemplates_v3` | `99.75348` | `46.049` | `46.049` | `0.338` | `0.02941` | `0.94322` |
| `4` | `top5_decoy` | `Model_44_cf_woTemplates_model_4_multimer_v3_pred_19.pdb` | `cf_woTemplates_v3` | `99.66466` | `60.788` | `33.517` | `1.561` | `0.03028` | `0.95007` |
| `5` | `top5_decoy` | `Model_4_afm_dropout_noSM_woTemplates_model_4_multimer_v3_pred_25.pdb` | `afm_dropout_noSM_woTemplates_v3` | `99.36256` | `62.242` | `33.417` | `0.596` | `0.03086` | `0.94846` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

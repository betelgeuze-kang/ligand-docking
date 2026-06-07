# H2319 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` `afm_basic_v3`
- model1/runner-up/gap: `105.48786/104.92274/0.56512`
- top5 score mean/spread: `103.882788/4.04092`
- diversity/nearest: `43.949/23.482`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `afm_basic_v3` | `105.48786` | `0` | `29.335` | `1.261` | `0` | `0.99433` |
| `2` | `top5_decoy` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_65.pdb` | `afm_dropout_full_v3` | `104.92274` | `52.429` | `23.482` | `1.664` | `0` | `0.99433` |
| `3` | `top5_decoy` | `Model_12_afm_basic_model_1_multimer_v2_pred_64.pdb` | `afm_basic_v2` | `103.80454` | `54.647` | `23.482` | `1.399` | `0` | `0.98375` |
| `4` | `top5_decoy` | `Model_10_afm_dropout_full_model_1_multimer_v2_pred_30.pdb` | `afm_dropout_full_v2` | `103.75186` | `39.385` | `27.973` | `0.351` | `0` | `0.98169` |
| `5` | `top5_decoy` | `Model_6_cf_woTemplates_model_4_multimer_v3_pred_24.pdb` | `cf_woTemplates_v3` | `101.44694` | `29.335` | `27.973` | `2.569` | `0.01341` | `0.95899` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

# H2321 Protein/Complex MassiveFold Self-Assessment

- family: `heteromer_or_immune_complex`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` `afm_dropout_full_v3`
- model1/runner-up/gap: `102.10998/101.4412/0.66878`
- top5 score mean/spread: `100.844388/3.56518`
- diversity/nearest: `39.6285/30.788`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `afm_dropout_full_v3` | `102.10998` | `0` | `32.155` | `3.608` | `0.00203` | `0.96779` |
| `2` | `top5_decoy` | `Model_14_afm_basic_model_1_multimer_v2_pred_43.pdb` | `afm_basic_v2` | `101.4412` | `32.155` | `32.155` | `3.04` | `0.00292` | `0.96602` |
| `3` | `top5_decoy` | `Model_5_afm_dropout_full_model_2_multimer_v2_pred_42.pdb` | `afm_dropout_full_v2` | `101.13708` | `41.408` | `41.408` | `2.483` | `0.00178` | `0.9617` |
| `4` | `top5_decoy` | `Model_70_afm_basic_model_4_multimer_v3_pred_64.pdb` | `afm_basic_v3` | `100.98888` | `39.181` | `30.788` | `3.153` | `0.00203` | `0.95866` |
| `5` | `top5_decoy` | `Model_8_afm_dropout_noSM_woTemplates_model_3_multimer_v3_pred_1.pdb` | `afm_dropout_noSM_woTemplates_v3` | `98.5448` | `45.77` | `30.788` | `1.75` | `0.01623` | `0.94484` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

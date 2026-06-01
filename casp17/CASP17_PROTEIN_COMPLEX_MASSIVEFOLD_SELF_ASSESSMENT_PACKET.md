# CASP17 Protein/Complex MassiveFold Self-Assessment Packet

- generated: `2026-06-01T22:08:40+09:00`
- status: `protein_complex_massivefold_self_assessment_ready_external_only`
- targets ready/blocked/total: `9/0/9`
- heteromer/immune targets: `8`
- model1/top5/candidates: `9/45/45`
- low-margin targets: `8` below `2.0`
- next action: use external-only protein/complex self-assessment features to stress-test model1 selection, interface triage, and confidence calibration without native or submission claims

## Targets

| target | family | status | model1 | score gap | top5 mean/spread | diversity/nearest | blockers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `H1311` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `0.3313` | `102.85846/2.55002` | `31.10125/2.431` | `-` |
| `H2324` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `0.17602` | `99.696224/0.57566` | `57.6945/33.417` | `-` |
| `H2312` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `0.0813` | `101.033084/1.18232` | `18.18725/2.787` | `-` |
| `T2313` | `protein_monomer_or_homomer_pool` | `ready_external_complex_self_assessment_input` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `2.56834` | `79.995/5.2837` | `53.82425/17.703` | `-` |
| `H2338` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `0.45224` | `102.955276/1.77912` | `47.523/15.056` | `-` |
| `H2339` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `0.74694` | `101.466988/2.39072` | `52.00175/36.62` | `-` |
| `H2319` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `0.56512` | `103.882788/4.04092` | `43.949/23.482` | `-` |
| `H2321` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `0.66878` | `100.844388/3.56518` | `39.6285/30.788` | `-` |
| `H2335` | `heteromer_or_immune_complex` | `ready_external_complex_self_assessment_input` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `1.11502` | `93.073392/1.6303` | `57.9835/21.59` | `-` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

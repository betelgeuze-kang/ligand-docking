# T2313 Protein/Complex MassiveFold Self-Assessment

- family: `protein_monomer_or_homomer_pool`
- status: `ready_external_complex_self_assessment_input`
- model1: `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` `afm_woTemplates_v3`
- model1/runner-up/gap: `83.5072/80.93886/2.56834`
- top5 score mean/spread: `79.995/5.2837`
- diversity/nearest: `53.82425/17.703`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf | high-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `afm_woTemplates_v3` | `83.5072` | `0` | `51.518` | `2.36` | `0.13562` | `0.7766` |
| `2` | `top5_decoy` | `Model_10_afm_dropout_noSM_woTemplates_model_5_multimer_v3_pred_11.pdb` | `afm_dropout_noSM_woTemplates_v3` | `80.93886` | `52.165` | `17.703` | `2.751` | `0.14552` | `0.74663` |
| `3` | `top5_decoy` | `Model_63_af3_basic_af3_seed_704032_sample_0_pred_520.cif` | `basic` | `78.90796` | `59.443` | `53.463` | `2.731` | `0.09953` | `0.69408` |
| `4` | `top5_decoy` | `Model_69_af3_woPaired_af3_seed_880568_sample_2_pred_47.cif` | `woPaired` | `78.39748` | `51.518` | `33.97` | `2.463` | `0.10057` | `0.67594` |
| `5` | `top5_decoy` | `Model_4_afm_dropout_full_model_4_multimer_v3_pred_44.pdb` | `afm_dropout_full_v3` | `78.2235` | `52.171` | `17.703` | `4.555` | `0.17688` | `0.70543` |

## Claim Boundary

CASP17 protein/complex MassiveFold self-assessment packet only. It converts organizer-provided external protein, immune, and complex model1/top5 pointers into no-native confidence, diversity, and geometry review features for conformation triage and model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.

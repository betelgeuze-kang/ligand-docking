# R2341 MassiveFold RNA Model-Selection Input

- status: `ready_external_model_selection_input`
- model1/top5 inputs: `1/5`
- missing artifacts: `0`
- sequence guard: `-`
- manifest: `casp17/massivefold_rna_model_selection_inputs/r2341/input_manifest.csv`

## Inputs

| rank | role | file | protocol | score | viewer |
| --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `basic` | `53.0992` | `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/viewer.html` |
| `2` | `top5_decoy` | `Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_210550_sample_3_pred_718.cif` | `woUnpaired_woPaired_woTemplates` | `52.99014` | `casp17/massivefold_representative_viewers/r2341/selection_001_woUnpaired_woPaired_woTemplates_model_1/viewer.html` |
| `3` | `top5_decoy` | `Model_32_af3_woPaired_woTemplates_af3_seed_446958_sample_2_pred_942.cif` | `woPaired_woTemplates` | `52.36314` | `casp17/massivefold_representative_viewers/r2341/selection_028_woPaired_woTemplates_model_32/viewer.html` |
| `4` | `top5_decoy` | `Model_9_af3_woUnpaired_woTemplates_af3_seed_120091_sample_0_pred_340.cif` | `woUnpaired_woTemplates` | `52.26184` | `casp17/massivefold_representative_viewers/r2341/selection_029_woUnpaired_woTemplates_model_9/viewer.html` |
| `5` | `top5_decoy` | `Model_7_af3_woUnpaired_af3_seed_914475_sample_4_pred_209.cif` | `woUnpaired` | `52.02568` | `casp17/massivefold_representative_viewers/r2341/selection_021_woUnpaired_model_7/viewer.html` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.

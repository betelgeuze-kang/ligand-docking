# R2352 MassiveFold RNA Model-Selection Input

- status: `ready_external_model_selection_input`
- model1/top5 inputs: `1/5`
- missing artifacts: `0`
- sequence guard: `-`
- manifest: `casp17/massivefold_rna_model_selection_inputs/r2352/input_manifest.csv`

## Inputs

| rank | role | file | protocol | score | viewer |
| --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` | `woUnpaired` | `82.69558` | `casp17/massivefold_representative_viewers/r2352/selection_034_woUnpaired_model_15/viewer.html` |
| `2` | `top5_decoy` | `Model_19_af3_woPaired_af3_seed_986684_sample_4_pred_279.cif` | `woPaired` | `82.62466` | `casp17/massivefold_representative_viewers/r2352/selection_023_woPaired_model_19/viewer.html` |
| `3` | `top5_decoy` | `Model_7_af3_woPaired_woTemplates_af3_seed_26386_sample_2_pred_237.cif` | `woPaired_woTemplates` | `82.6207` | `casp17/massivefold_representative_viewers/r2352/selection_027_woPaired_woTemplates_model_7/viewer.html` |
| `4` | `top5_decoy` | `Model_31_af3_woUnpaired_woPaired_woTemplates_af3_seed_91556_sample_0_pred_695.cif` | `woUnpaired_woPaired_woTemplates` | `82.55842` | `casp17/massivefold_representative_viewers/r2352/selection_024_woUnpaired_woPaired_woTemplates_model_31/viewer.html` |
| `5` | `top5_decoy` | `Model_18_af3_basic_af3_seed_674916_sample_2_pred_917.cif` | `basic` | `82.5543` | `casp17/massivefold_representative_viewers/r2352/selection_032_basic_model_18/viewer.html` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.

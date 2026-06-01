# R2351 MassiveFold RNA Model-Selection Input

- status: `ready_external_model_selection_input`
- model1/top5 inputs: `1/5`
- missing artifacts: `0`
- sequence guard: `-`
- manifest: `casp17/massivefold_rna_model_selection_inputs/r2351/input_manifest.csv`

## Inputs

| rank | role | file | protocol | score | viewer |
| --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `woTemplates` | `83.86274` | `casp17/massivefold_representative_viewers/r2351/selection_026_woTemplates_model_18/viewer.html` |
| `2` | `top5_decoy` | `Model_21_af3_basic_af3_seed_571067_sample_0_pred_415.cif` | `basic` | `83.73174` | `casp17/massivefold_representative_viewers/r2351/selection_038_basic_model_21/viewer.html` |
| `3` | `top5_decoy` | `Model_6_af3_woUnpaired_af3_seed_447781_sample_3_pred_923.cif` | `woUnpaired` | `83.7126` | `casp17/massivefold_representative_viewers/r2351/selection_018_woUnpaired_model_6/viewer.html` |
| `4` | `top5_decoy` | `Model_1_af3_woPaired_af3_seed_783356_sample_0_pred_395.cif` | `woPaired` | `83.63282` | `casp17/massivefold_representative_viewers/r2351/selection_007_woPaired_model_1/viewer.html` |
| `5` | `top5_decoy` | `Model_10_af3_woUnpaired_woPaired_af3_seed_456016_sample_2_pred_222.cif` | `woUnpaired_woPaired` | `83.60796` | `casp17/massivefold_representative_viewers/r2351/selection_020_woUnpaired_woPaired_model_10/viewer.html` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.

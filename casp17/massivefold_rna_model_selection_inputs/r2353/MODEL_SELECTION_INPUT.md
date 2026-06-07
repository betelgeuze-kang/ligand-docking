# R2353 MassiveFold RNA Model-Selection Input

- status: `ready_external_model_selection_input`
- model1/top5 inputs: `1/5`
- missing artifacts: `0`
- sequence guard: `-`
- manifest: `casp17/massivefold_rna_model_selection_inputs/r2353/input_manifest.csv`

## Inputs

| rank | role | file | protocol | score | viewer |
| --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `woPaired` | `80.52762` | `casp17/massivefold_representative_viewers/r2353/selection_021_woPaired_model_7/viewer.html` |
| `2` | `top5_decoy` | `Model_1_af3_woUnpaired_woPaired_af3_seed_3136_sample_2_pred_617.cif` | `woUnpaired_woPaired` | `80.43482` | `casp17/massivefold_representative_viewers/r2353/selection_032_woUnpaired_woPaired_model_1/viewer.html` |
| `3` | `top5_decoy` | `Model_5_af3_woUnpaired_woPaired_woTemplates_af3_seed_813694_sample_1_pred_871.cif` | `woUnpaired_woPaired_woTemplates` | `80.4287` | `casp17/massivefold_representative_viewers/r2353/selection_036_woUnpaired_woPaired_woTemplates_model_5/viewer.html` |
| `4` | `top5_decoy` | `Model_35_af3_woUnpaired_woTemplates_af3_seed_639646_sample_3_pred_853.cif` | `woUnpaired_woTemplates` | `80.1173` | `casp17/massivefold_representative_viewers/r2353/selection_017_woUnpaired_woTemplates_model_35/viewer.html` |
| `5` | `top5_decoy` | `Model_26_af3_woUnpaired_af3_seed_166439_sample_4_pred_334.cif` | `woUnpaired` | `80.1145` | `casp17/massivefold_representative_viewers/r2353/selection_020_woUnpaired_model_26/viewer.html` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.

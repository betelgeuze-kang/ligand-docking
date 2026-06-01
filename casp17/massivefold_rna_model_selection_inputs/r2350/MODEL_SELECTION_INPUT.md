# R2350 MassiveFold RNA Model-Selection Input

- status: `ready_external_model_selection_input`
- model1/top5 inputs: `1/5`
- missing artifacts: `0`
- sequence guard: `-`
- manifest: `casp17/massivefold_rna_model_selection_inputs/r2350/input_manifest.csv`

## Inputs

| rank | role | file | protocol | score | viewer |
| --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `woPaired` | `83.34166` | `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/viewer.html` |
| `2` | `top5_decoy` | `Model_5_af3_woUnpaired_woTemplates_af3_seed_100687_sample_3_pred_398.cif` | `woUnpaired_woTemplates` | `83.31874` | `casp17/massivefold_representative_viewers/r2350/selection_018_woUnpaired_woTemplates_model_5/viewer.html` |
| `3` | `top5_decoy` | `Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_811587_sample_2_pred_367.cif` | `woUnpaired_woPaired_woTemplates` | `83.20776` | `casp17/massivefold_representative_viewers/r2350/selection_037_woUnpaired_woPaired_woTemplates_model_1/viewer.html` |
| `4` | `top5_decoy` | `Model_13_af3_woUnpaired_woPaired_af3_seed_94539_sample_0_pred_25.cif` | `woUnpaired_woPaired` | `83.16338` | `casp17/massivefold_representative_viewers/r2350/selection_004_woUnpaired_woPaired_model_13/viewer.html` |
| `5` | `top5_decoy` | `Model_2_af3_woUnpaired_af3_seed_160939_sample_4_pred_359.cif` | `woUnpaired` | `83.1483` | `casp17/massivefold_representative_viewers/r2350/selection_008_woUnpaired_model_2/viewer.html` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.

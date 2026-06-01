# R2345 MassiveFold RNA Model-Selection Input

- status: `ready_external_model_selection_input`
- model1/top5 inputs: `1/5`
- missing artifacts: `0`
- sequence guard: `ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only`
- manifest: `casp17/massivefold_rna_model_selection_inputs/r2345/input_manifest.csv`

## Inputs

| rank | role | file | protocol | score | viewer |
| --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `woUnpaired` | `57.89694` | `casp17/massivefold_representative_viewers/r2345/selection_013_woUnpaired_model_4/viewer.html` |
| `2` | `top5_decoy` | `Model_5_af3_woPaired_woTemplates_af3_seed_239697_sample_2_pred_712.cif` | `woPaired_woTemplates` | `56.25632` | `casp17/massivefold_representative_viewers/r2345/selection_016_woPaired_woTemplates_model_5/viewer.html` |
| `3` | `top5_decoy` | `Model_7_af3_woUnpaired_woPaired_af3_seed_567474_sample_4_pred_449.cif` | `woUnpaired_woPaired` | `54.92012` | `casp17/massivefold_representative_viewers/r2345/selection_007_woUnpaired_woPaired_model_7/viewer.html` |
| `4` | `top5_decoy` | `Model_41_af3_woUnpaired_woTemplates_af3_seed_552323_sample_0_pred_155.cif` | `woUnpaired_woTemplates` | `53.92886` | `casp17/massivefold_representative_viewers/r2345/selection_036_woUnpaired_woTemplates_model_41/viewer.html` |
| `5` | `top5_decoy` | `Model_42_af3_woUnpaired_woPaired_woTemplates_af3_seed_513300_sample_2_pred_592.cif` | `woUnpaired_woPaired_woTemplates` | `53.51738` | `casp17/massivefold_representative_viewers/r2345/selection_021_woUnpaired_woPaired_woTemplates_model_42/viewer.html` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.

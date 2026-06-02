# R2351 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_watch_model1_retained_low_margin`
- recommendation: `external_model1_watch_low_margin_after_probe`
- primary model: `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif`
- model1/top/margin: `83.30344/83.30344/0.29014`
- top candidate: `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `83.30344` | `83.86274` | `2.044` | `0.02415` | `-` | `casp17/massivefold_representative_viewers/r2351/selection_026_woTemplates_model_18/viewer.html` |
| `2` | `competitor` | `Model_21_af3_basic_af3_seed_571067_sample_0_pred_415.cif` | `83.0133` | `83.73174` | `0.504` | `0.02259` | `54.726` | `casp17/massivefold_representative_viewers/r2351/selection_038_basic_model_21/viewer.html` |
| `3` | `competitor` | `Model_6_af3_woUnpaired_af3_seed_447781_sample_3_pred_923.cif` | `82.4939` | `83.7126` | `2.485` | `0.02451` | `54.843` | `casp17/massivefold_representative_viewers/r2351/selection_018_woUnpaired_model_6/viewer.html` |
| `4` | `competitor` | `Model_10_af3_woUnpaired_woPaired_af3_seed_456016_sample_2_pred_222.cif` | `82.23715` | `83.60796` | `2.701` | `0.0221` | `65.136` | `casp17/massivefold_representative_viewers/r2351/selection_020_woUnpaired_woPaired_model_10/viewer.html` |
| `5` | `competitor` | `Model_1_af3_woPaired_af3_seed_783356_sample_0_pred_395.cif` | `82.18503` | `83.63282` | `3.487` | `0.02138` | `53.328` | `casp17/massivefold_representative_viewers/r2351/selection_007_woPaired_model_1/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

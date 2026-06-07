# R2345 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif`
- model1/top/margin: `57.4808/57.4808/2.30976`
- top candidate: `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `57.4808` | `57.89694` | `1.104` | `0.07007` | `-` | `casp17/massivefold_representative_viewers/r2345/selection_013_woUnpaired_model_4/viewer.html` |
| `2` | `competitor` | `Model_5_af3_woPaired_woTemplates_af3_seed_239697_sample_2_pred_712.cif` | `55.17104` | `56.25632` | `1.752` | `0.12555` | `39.618` | `casp17/massivefold_representative_viewers/r2345/selection_016_woPaired_woTemplates_model_5/viewer.html` |
| `3` | `competitor` | `Model_7_af3_woUnpaired_woPaired_af3_seed_567474_sample_4_pred_449.cif` | `54.1595` | `54.92012` | `0.807` | `0.12993` | `29.901` | `casp17/massivefold_representative_viewers/r2345/selection_007_woUnpaired_woPaired_model_7/viewer.html` |
| `4` | `competitor` | `Model_41_af3_woUnpaired_woTemplates_af3_seed_552323_sample_0_pred_155.cif` | `53.03804` | `53.92886` | `0.761` | `0.14891` | `40.275` | `casp17/massivefold_representative_viewers/r2345/selection_036_woUnpaired_woTemplates_model_41/viewer.html` |
| `5` | `competitor` | `Model_42_af3_woUnpaired_woPaired_woTemplates_af3_seed_513300_sample_2_pred_592.cif` | `52.7694` | `53.51738` | `0.993` | `0.14891` | `20.191` | `casp17/massivefold_representative_viewers/r2345/selection_021_woUnpaired_woPaired_woTemplates_model_42/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

# R2341 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif`
- model1/top/margin: `51.74741/51.74741/0.86527`
- top candidate: `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `51.74741` | `53.0992` | `2.265` | `0.39277` | `-` | `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/viewer.html` |
| `2` | `competitor` | `Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_210550_sample_3_pred_718.cif` | `50.88214` | `52.99014` | `3.069` | `0.40281` | `53.513` | `casp17/massivefold_representative_viewers/r2341/selection_001_woUnpaired_woPaired_woTemplates_model_1/viewer.html` |
| `3` | `competitor` | `Model_7_af3_woUnpaired_af3_seed_914475_sample_4_pred_209.cif` | `50.3913` | `52.02568` | `0.933` | `0.42441` | `55.231` | `casp17/massivefold_representative_viewers/r2341/selection_021_woUnpaired_model_7/viewer.html` |
| `4` | `competitor` | `Model_9_af3_woUnpaired_woTemplates_af3_seed_120091_sample_0_pred_340.cif` | `49.18782` | `52.26184` | `6.659` | `0.40784` | `59.359` | `casp17/massivefold_representative_viewers/r2341/selection_029_woUnpaired_woTemplates_model_9/viewer.html` |
| `5` | `competitor` | `Model_32_af3_woPaired_woTemplates_af3_seed_446958_sample_2_pred_942.cif` | `49.15947` | `52.36314` | `7.694` | `0.41487` | `45.043` | `casp17/massivefold_representative_viewers/r2341/selection_028_woPaired_woTemplates_model_32/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

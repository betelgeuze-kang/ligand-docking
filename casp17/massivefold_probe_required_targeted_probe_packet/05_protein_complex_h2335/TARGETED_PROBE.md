# H2335 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb`
- model1/top/margin: `92.30765/92.30765/1.04953`
- top candidate: `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `92.30765` | `94.11582` | `6.857` | `0.04696` | `-` | `casp17/massivefold_representative_viewers/h2335/selection_030_afm_basic_v1_model_7830/viewer.html` |
| `2` | `competitor` | `Model_12_afm_basic_model_4_multimer_v3_pred_12.pdb` | `91.25812` | `93.0008` | `3.27` | `0.06836` | `78.846` | `casp17/massivefold_representative_viewers/h2335/selection_032_afm_basic_v3_model_12/viewer.html` |
| `3` | `competitor` | `Model_40_afm_dropout_full_model_4_multimer_v3_pred_48.pdb` | `90.97267` | `92.48552` | `2.322` | `0.07161` | `78.913` | `casp17/massivefold_representative_viewers/h2335/selection_035_afm_dropout_full_v3_model_40/viewer.html` |
| `4` | `competitor` | `Model_7964_afm_dropout_full_model_5_multimer_v1_pred_41.pdb` | `90.96998` | `92.90986` | `6.446` | `0.05624` | `21.59` | `casp17/massivefold_representative_viewers/h2335/selection_067_afm_dropout_full_v1_model_7964/viewer.html` |
| `5` | `competitor` | `Model_7659_cf_woTemplates_model_5_multimer_v1_pred_18.pdb` | `90.92648` | `92.85496` | `5.241` | `0.04619` | `52.585` | `casp17/massivefold_representative_viewers/h2335/selection_117_cf_woTemplates_v1_model_7659/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

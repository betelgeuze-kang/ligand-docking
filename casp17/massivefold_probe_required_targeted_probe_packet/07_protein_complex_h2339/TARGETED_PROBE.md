# H2339 Probe-Required Targeted Probe

- status: `targeted_probe_ready_external_only`
- result: `probe_pass_model1_retained_clear`
- recommendation: `external_model1_freeze_candidate_after_probe`
- primary model: `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb`
- model1/top/margin: `102.50423/102.50423/0.83464`
- top candidate: `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` `model1`
- scoring rule: `probe_required_targeted_no_native_rescore_v1`
- blockers: `-`

## Top5 No-Native Rescore

| rank | role | filename | score | confidence | geometry | low-conf | diversity | viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `102.50423` | `102.90764` | `1.589` | `0.00308` | `-` | `casp17/massivefold_representative_viewers/h2339/selection_111_afm_basic_v1_model_135/viewer.html` |
| `2` | `competitor` | `Model_174_afm_dropout_full_model_5_multimer_v1_pred_22.pdb` | `101.66959` | `102.1607` | `0.475` | `0.00308` | `36.62` | `casp17/massivefold_representative_viewers/h2339/selection_121_afm_dropout_full_v1_model_174/viewer.html` |
| `3` | `competitor` | `Model_444_afm_woTemplates_model_4_multimer_v1_pred_50.pdb` | `100.04141` | `100.78402` | `0.597` | `0.01196` | `56.944` | `casp17/massivefold_representative_viewers/h2339/selection_060_afm_woTemplates_v1_model_444/viewer.html` |
| `4` | `competitor` | `Model_974_cf_woTemplates_model_5_multimer_v1_pred_18.pdb` | `99.47778` | `100.51692` | `1.842` | `0.01196` | `55.472` | `casp17/massivefold_representative_viewers/h2339/selection_099_cf_woTemplates_v1_model_974/viewer.html` |
| `5` | `competitor` | `Model_1_afm_basic_model_4_multimer_v2_pred_44.pdb` | `99.38598` | `100.96566` | `3.881` | `0.00986` | `58.971` | `casp17/massivefold_representative_viewers/h2339/selection_067_afm_basic_v2_model_1/viewer.html` |

## Claim Boundary

CASP17 MassiveFold probe-required targeted probe packet only. It re-scores external MassiveFold top5 review candidates with no-native confidence, geometry, low-confidence, and diversity features. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

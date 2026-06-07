# CASP17 MassiveFold Hold/Probe Review Packet

- generated: `2026-06-02T01:39:01+09:00`
- status: `massivefold_hold_probe_review_packet_ready_external_only`
- reviews ready/blocked/total: `13/0/13`
- classes manual/interface/probe/weak/watch/unknown: `1/1/11/0/0/0`
- model/viewer/projection/top5/alternate present: `13/13/13/13/1`
- top5 candidate total: `65`
- first review: `R2352` `manual_blocked_review` `do_not_freeze_model1_external_only`
- proof eligible: `False` policy `do_not_mark_as_internal_prediction`
- next action: operator reviews manual block, interface hold, and probe-required viewers before any model1 freeze

## Review Targets

| rank | target | class | action | primary model | alternate | score | gap | margin | viewer | review | blockers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2352` | `manual_blocked_review` | `do_not_freeze_model1_external_only` | `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` | `Model_7_af3_woPaired_woTemplates_af3_seed_26386_sample_2_pred_237.cif` | `82.69558` | `0.07092` | `-0.23587` | `casp17/massivefold_representative_viewers/r2352/selection_034_woUnpaired_model_15/viewer.html` | `casp17/massivefold_hold_probe_review_packet/01_manual_blocked_review_r2352/HOLD_PROBE_REVIEW.md` | `-` |
| `2` | `H2312` | `interface_hold_review` | `keep_model1_hold_until_interface_review` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `-` | `101.58484` | `0.0813` | `0.10755` | `casp17/massivefold_representative_viewers/h2312/selection_122_afm_basic_v1_model_7550/viewer.html` | `casp17/massivefold_hold_probe_review_packet/02_interface_hold_review_h2312/HOLD_PROBE_REVIEW.md` | `-` |
| `3` | `H1311` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `-` | `104.19842` | `0.3313` | `-` | `casp17/massivefold_representative_viewers/h1311/selection_024_afm_basic_v3_model_5/viewer.html` | `casp17/massivefold_hold_probe_review_packet/03_probe_required_review_h1311/HOLD_PROBE_REVIEW.md` | `-` |
| `4` | `H2319` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `-` | `105.48786` | `0.56512` | `-` | `casp17/massivefold_representative_viewers/h2319/selection_125_afm_basic_v3_model_1/viewer.html` | `casp17/massivefold_hold_probe_review_packet/04_probe_required_review_h2319/HOLD_PROBE_REVIEW.md` | `-` |
| `5` | `H2321` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `-` | `102.10998` | `0.66878` | `-` | `casp17/massivefold_representative_viewers/h2321/selection_086_afm_dropout_full_v3_model_3/viewer.html` | `casp17/massivefold_hold_probe_review_packet/05_probe_required_review_h2321/HOLD_PROBE_REVIEW.md` | `-` |
| `6` | `H2324` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `-` | `99.93822` | `0.17602` | `-` | `casp17/massivefold_representative_viewers/h2324/selection_115_afm_basic_v1_model_4760/viewer.html` | `casp17/massivefold_hold_probe_review_packet/06_probe_required_review_h2324/HOLD_PROBE_REVIEW.md` | `-` |
| `7` | `H2335` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `-` | `94.11582` | `1.11502` | `-` | `casp17/massivefold_representative_viewers/h2335/selection_030_afm_basic_v1_model_7830/viewer.html` | `casp17/massivefold_hold_probe_review_packet/07_probe_required_review_h2335/HOLD_PROBE_REVIEW.md` | `-` |
| `8` | `H2338` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `-` | `103.87838` | `0.45224` | `-` | `casp17/massivefold_representative_viewers/h2338/selection_029_afm_dropout_full_v3_model_2/viewer.html` | `casp17/massivefold_hold_probe_review_packet/08_probe_required_review_h2338/HOLD_PROBE_REVIEW.md` | `-` |
| `9` | `H2339` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `-` | `102.90764` | `0.74694` | `-` | `casp17/massivefold_representative_viewers/h2339/selection_111_afm_basic_v1_model_135/viewer.html` | `casp17/massivefold_hold_probe_review_packet/09_probe_required_review_h2339/HOLD_PROBE_REVIEW.md` | `-` |
| `10` | `R2341` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `-` | `53.0992` | `0.10906` | `-` | `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/viewer.html` | `casp17/massivefold_hold_probe_review_packet/10_probe_required_review_r2341/HOLD_PROBE_REVIEW.md` | `-` |
| `11` | `R2345` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `-` | `57.89694` | `1.64062` | `-` | `casp17/massivefold_representative_viewers/r2345/selection_013_woUnpaired_model_4/viewer.html` | `casp17/massivefold_hold_probe_review_packet/11_probe_required_review_r2345/HOLD_PROBE_REVIEW.md` | `-` |
| `12` | `R2351` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `-` | `83.86274` | `0.131` | `-` | `casp17/massivefold_representative_viewers/r2351/selection_026_woTemplates_model_18/viewer.html` | `casp17/massivefold_hold_probe_review_packet/12_probe_required_review_r2351/HOLD_PROBE_REVIEW.md` | `-` |
| `13` | `T2313` | `probe_required_review` | `run_targeted_no_native_probe_before_freeze` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `-` | `83.5072` | `2.56834` | `-` | `casp17/massivefold_representative_viewers/t2313/selection_085_afm_woTemplates_v3_model_5/viewer.html` | `casp17/massivefold_hold_probe_review_packet/13_probe_required_review_t2313/HOLD_PROBE_REVIEW.md` | `-` |

## Claim Boundary

CASP17 MassiveFold hold/probe review packet only. It links external MassiveFold model1/top5 review artifacts for selector-held or probe-required targets. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit without operator approval.

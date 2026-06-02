# CASP17 Official Archive First Baseline Model1 Gap Triage

- generated: `2026-06-02T00:27:06+09:00`
- status: `official_archive_first_baseline_model1_gap_triage_ready_baseline_only`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- groups ready/blocked/total: `73/1/74`
- model1-best/top5-improved rates: `21/73` `0.288` / `52/73` `0.712`
- gap bands small/medium/large/catastrophic: `27/11/9/5`
- critical calibration cases: `14`
- first triage: group `163` `catastrophic_model1_selection_gap` delta `78.380`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: use high-gap baseline-only cases to calibrate no-native model1 selection features; keep strict-blind competitive proof blocked until internal evidence is supplied

## Top Gap Worklist

| rank | group | band | model1 | best top5 | delta | action |
| --- | --- | --- | --- | --- | --- | --- |
| `1` | `163` | `catastrophic_model1_selection_gap` | `T1212TS163_1` `0.268` | `T1212TS163_4` `78.648` | `78.380` | `critical_model1_failure_case_for_accuracy_estimation_training` |
| `2` | `304` | `catastrophic_model1_selection_gap` | `T1212TS304_1` `3.004` | `T1212TS304_3` `74.142` | `71.138` | `critical_model1_failure_case_for_accuracy_estimation_training` |
| `3` | `286` | `catastrophic_model1_selection_gap` | `T1212TS286_1` `0.751` | `T1212TS286_2` `62.393` | `61.642` | `critical_model1_failure_case_for_accuracy_estimation_training` |
| `4` | `419` | `catastrophic_model1_selection_gap` | `T1212TS419_1` `0.751` | `T1212TS419_2` `62.393` | `61.642` | `critical_model1_failure_case_for_accuracy_estimation_training` |
| `5` | `262` | `catastrophic_model1_selection_gap` | `T1212TS262_1` `4.077` | `T1212TS262_5` `57.940` | `53.863` | `critical_model1_failure_case_for_accuracy_estimation_training` |
| `6` | `345` | `large_selection_gap` | `T1212TS345_1` `0.483` | `T1212TS345_2` `50.429` | `49.946` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `7` | `369` | `large_selection_gap` | `T1212TS369_1` `7.457` | `T1212TS369_5` `48.283` | `40.826` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `8` | `269` | `large_selection_gap` | `T1212TS269_1` `0.697` | `T1212TS269_4` `40.182` | `39.485` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `9` | `221` | `large_selection_gap` | `T1212TS221_1` `0.000` | `T1212TS221_4` `38.895` | `38.895` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `10` | `015` | `large_selection_gap` | `T1212TS015_1` `1.395` | `T1212TS015_4` `31.438` | `30.043` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `11` | `312` | `large_selection_gap` | `T1212TS312_1` `0.000` | `T1212TS312_3` `27.092` | `27.092` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `12` | `052` | `large_selection_gap` | `T1212TS052_1` `0.590` | `T1212TS052_5` `25.000` | `24.410` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `13` | `481` | `large_selection_gap` | `T1212TS481_1` `1.073` | `T1212TS481_5` `24.034` | `22.961` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `14` | `261` | `large_selection_gap` | `T1212TS261_1` `22.264` | `T1212TS261_4` `45.118` | `22.854` | `audit_model1_selection_rule_and_prioritize_best_of_5_rescore_features` |
| `15` | `388` | `medium_selection_gap` | `T1212TS388_1` `12.661` | `T1212TS388_2` `32.242` | `19.581` | `calibrate_confidence_geometry_and_protocol_diversity_features` |
| `16` | `425` | `medium_selection_gap` | `T1212TS425_1` `2.200` | `T1212TS425_3` `18.938` | `16.738` | `calibrate_confidence_geometry_and_protocol_diversity_features` |
| `17` | `208` | `medium_selection_gap` | `T1212TS208_1` `3.648` | `T1212TS208_5` `18.616` | `14.968` | `calibrate_confidence_geometry_and_protocol_diversity_features` |
| `18` | `139` | `medium_selection_gap` | `T1212TS139_1` `16.202` | `T1212TS139_2` `29.936` | `13.734` | `calibrate_confidence_geometry_and_protocol_diversity_features` |
| `19` | `358` | `medium_selection_gap` | `T1212TS358_1` `30.687` | `T1212TS358_4` `44.206` | `13.519` | `calibrate_confidence_geometry_and_protocol_diversity_features` |
| `20` | `311` | `medium_selection_gap` | `T1212TS311_1` `7.457` | `T1212TS311_2` `16.202` | `8.745` | `calibrate_confidence_geometry_and_protocol_diversity_features` |

## Claim Boundary

Local CASP17 official-archive first baseline model1 gap triage only. It mines a baseline-only proxy score ledger for model1-vs-best-of-5 selection failures and calibration examples. It is not an official CASP assessment, not strict-blind competitive proof, does not import official archive models as internal predictions, does not push remotes, and does not submit to CASP.

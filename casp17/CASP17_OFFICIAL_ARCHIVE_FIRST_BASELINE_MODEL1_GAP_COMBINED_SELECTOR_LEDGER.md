# CASP17 Official Archive First Baseline Model1 Gap Combined Selector Ledger

- generated: `2026-06-02T01:04:14+09:00`
- status: `official_archive_first_baseline_model1_gap_combined_selector_ledger_ready_baseline_only`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- selector ready/blocked/selected: `14/0/14`
- decisions promote/retain/hold: `7/6/1`
- baseline corrected/retained-failure/manual-hold/false-positive: `7/6/1/0`
- baseline capture/non-capture: `0.500` `0.500`
- catastrophic/large cases: `5/9`
- first selector: group `163` decision `retain_model1` selected `T1212TS163_1` result `retained_model1_failure_baseline_proxy`
- combined selector csv: `casp17/official_archive_first_baseline_model1_gap_combined_selector_ledger/combined_selector_ledger.csv`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: apply this conservative combined selector design to external CASP17 MassiveFold model1 freeze ledgers, then repeat on strict-blind eligible internal predictions before competitive claims

## Selector Worklist

| rank | group | band | delta | geometry | consensus | decision | selected | baseline result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `163` | `catastrophic_model1_selection_gap` | `78.380` | `ambiguous` | `supports_model1` | `retain_model1` | `T1212TS163_1` | `retained_model1_failure_baseline_proxy` |
| `2` | `304` | `catastrophic_model1_selection_gap` | `71.138` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS304_3` | `corrected_model1_failure_baseline_proxy` |
| `3` | `286` | `catastrophic_model1_selection_gap` | `61.642` | `ambiguous` | `supports_model1` | `retain_model1` | `T1212TS286_1` | `retained_model1_failure_baseline_proxy` |
| `4` | `419` | `catastrophic_model1_selection_gap` | `61.642` | `ambiguous` | `supports_model1` | `retain_model1` | `T1212TS419_1` | `retained_model1_failure_baseline_proxy` |
| `5` | `262` | `catastrophic_model1_selection_gap` | `53.863` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS262_5` | `corrected_model1_failure_baseline_proxy` |
| `6` | `345` | `large_selection_gap` | `49.946` | `ambiguous` | `supports_model1` | `retain_model1` | `T1212TS345_1` | `retained_model1_failure_baseline_proxy` |
| `7` | `369` | `large_selection_gap` | `40.826` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS369_5` | `corrected_model1_failure_baseline_proxy` |
| `8` | `269` | `large_selection_gap` | `39.485` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS269_4` | `corrected_model1_failure_baseline_proxy` |
| `9` | `221` | `large_selection_gap` | `38.895` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS221_4` | `corrected_model1_failure_baseline_proxy` |
| `10` | `015` | `large_selection_gap` | `30.043` | `ambiguous` | `supports_model1` | `retain_model1` | `T1212TS015_1` | `retained_model1_failure_baseline_proxy` |
| `11` | `312` | `large_selection_gap` | `27.092` | `ambiguous` | `supports_model1` | `retain_model1` | `T1212TS312_1` | `retained_model1_failure_baseline_proxy` |
| `12` | `052` | `large_selection_gap` | `24.410` | `ambiguous` | `ambiguous` | `hold_manual_review` | `-` | `manual_hold_on_model1_failure_baseline_proxy` |
| `13` | `481` | `large_selection_gap` | `22.961` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS481_5` | `corrected_model1_failure_baseline_proxy` |
| `14` | `261` | `large_selection_gap` | `22.854` | `ambiguous` | `supports_best_top5` | `promote_best_top5` | `T1212TS261_4` | `corrected_model1_failure_baseline_proxy` |

## Claim Boundary

Local CASP17 official-archive first baseline model1 gap combined selector ledger only. It combines native-free geometry and top5 consensus probe outputs from baseline-only official archive models to calibrate model1-selection decisions. It is not an official CASP assessment, not strict-blind competitive proof, does not import official archive models as internal predictions, does not push remotes, and does not submit to CASP.

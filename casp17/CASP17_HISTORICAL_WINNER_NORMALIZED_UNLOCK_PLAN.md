# CASP17 Historical Winner-Normalized Unlock Plan

- generated: `2026-06-03T00:44:00+09:00`
- status: `awaiting_historical_winner_normalized_unlocks`
- actions ready/blocked/total: `1/5/6`
- strict slots ready/total: `0/40`
- metric rows ready/total: `0/440`
- sidechain-native pass/total: `0/40`
- official archive proof: `24/0`
- winner bands top5/total: `0/5`
- first blocked: `close_first_source_request` `strict_blind_internal_prediction_source` `prediction_not_before_native`
- next action: attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence

## Actions

| order | action | gate | status | ready | blocked | total | blocker | next action |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `close_first_source_request` | `strict_blind_internal_prediction_source` | `unlock_blocked` | 0 | 13 | 13 | `prediction_not_before_native` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| 2 | `close_strict_blind_batch_slots` | `strict_blind_batch_closure_runway` | `unlock_blocked` | 0 | 40 | 40 | `internal_source_id_missing_or_external` | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool |
| 3 | `pass_sidechain_native_40` | `sidechain_native_benchmark` | `unlock_blocked` | 0 | 40 | 40 | `sidechain_native_40_pass_not_proven` | replace placeholder leakage_clearance with operator-confirmed no_leak provenance; place the cleared prediction/native PDB files for this benchmark row. |
| 4 | `generate_metric_surface_rows` | `official_like_metric_surface` | `unlock_blocked` | 0 | 440 | 440 | `metric_surface_rows_not_ready` | fill strict-blind prediction/native/no-leak evidence for 40 historical slots and add organic ligand-protein historical slots before claiming full CASP17 win-tier metric surface |
| 5 | `preserve_official_archive_as_baseline` | `official_archive_baseline_guard` | `unlock_ready` | 24 | 0 | 24 | `-` | keep official CASP archive submissions baseline-only and excluded from internal strict-blind proof |
| 6 | `score_winner_normalized_bands` | `casp15_casp16_winner_normalized_comparison` | `unlock_blocked` | 0 | 5 | 5 | `strict_blind_historical_metric_surface_missing` | score CASP15-style no-leak regular-domain replay rows and compare SUM Zscore to official top bands |

## Claim Boundary

Local CASP17 historical winner-normalized unlock plan only. It orders the local gates required before CASP15/16 winner-normalized band comparison can be treated as competitive evidence. It does not fill operator values, create or copy PDB files, compute official CASP metrics, import official archive submissions as internal predictions, push remotes, or submit to CASP.

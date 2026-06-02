# CASP17 Official Archive First Baseline Replay Comparison

- generated: `2026-06-02T00:19:41+09:00`
- status: `official_archive_first_baseline_replay_comparison_ready_baseline_only`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- direct comparison status: `not_directly_comparable_proxy_single_target_not_sum_zscore`
- bands comparable/blocked/total: `0/3/3`
- model1 best groups/rate: `21/73` `0.288`
- top5 improved groups/rate: `52/73` `0.712`
- mean model1/best5/delta GDT_TS proxy: `6.224` `17.013` `10.789`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: keep this as baseline-only model-selection calibration, then close strict-blind source evidence before any winner-normalized competitive claim

## Winner Bands

| band | winner | top3 | top5 | 90pct | comparison |
| --- | --- | --- | --- | --- | --- |
| `casp15_regular_domain` | `Yang-Server` `90.4273` | `85.7980` | `73.3653` | `81.3846` | `not_directly_comparable_proxy_single_target_not_sum_zscore` |
| `casp16_regular_domain` | `Yang-Server` `40.8978` | `36.3137` | `33.3229` | `36.8080` | `not_directly_comparable_proxy_single_target_not_sum_zscore` |
| `casp16_multimer_complex` | `KiharaLab` `15.4000` | `14.5000` | `-` | `13.8600` | `not_directly_comparable_proxy_single_target_not_sum_zscore` |

## Claim Boundary

Local CASP17 official-archive first baseline replay comparison only. It compares a single baseline-only proxy score ledger with historical CASP15/16 winner-band constants and model1 selection diagnostics. It is not an official CASP assessment, not a SUM Z-score replay, not strict-blind competitive proof, does not import official archive models as internal predictions, does not push remotes, and does not submit to CASP.

# CASP17 Historical Winner-Normalized Bands

- generated: `2026-06-01T20:41:52+09:00`
- status: `blocked_strict_blind_metrics_missing`
- bands top5/winner-proximity/blocked/total: `0/0/5/5`
- strict-blind slots ready/total: `0/40`
- metric rows ready/total: `0/440`
- official archive baseline/proof-eligible: `24/0`
- first blocked: `casp15_regular_domain` `strict_blind_historical_metric_surface_missing`
- next action: score CASP15-style no-leak regular-domain replay rows and compare SUM Zscore to official top bands

## Bands

| band | metric | current | winner | ratio | top5 | top3 | status | blocker |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `casp15_regular_domain` | `SUM Zscore` | `0.0` | `90.4273` | `0.0` | `73.0` | `85.0` | `blocked_input` | `strict_blind_historical_metric_surface_missing` |
| `casp16_regular_domain` | `SUM Zscore` | `0.0` | `40.8978` | `0.0` | `33.3` | `36.3` | `blocked_input` | `strict_blind_historical_metric_surface_missing` |
| `casp16_multimer_complex` | `complex z-score and DockQ` | `0.0` | `15.4` | `0.0` | `0.0` | `14.5` | `blocked_input` | `strict_blind_historical_metric_surface_missing` |
| `casp16_ligand_pose_affinity` | `mean LDDT-PLI` | `0.0` | `0.8` | `0.0` | `0.69` | `0.8` | `blocked_input` | `strict_blind_historical_metric_surface_missing` |
| `accuracy_estimation_model_selection` | `top1 selection accuracy` | `0.0` | `1.0` | `0.0` | `0.7` | `0.8` | `blocked_input` | `strict_blind_historical_metric_surface_missing` |

## Claim Boundary

Local CASP17 historical winner-normalized band contract only. It maps CASP15/CASP16 planning bands from CASP17_WIN_TIER_GOAL.md onto current strict-blind historical replay evidence. It does not compute official CASP scores, import official archive submissions as internal predictions, approve no-leak provenance, mutate benchmark rows, push remotes, or submit to CASP.

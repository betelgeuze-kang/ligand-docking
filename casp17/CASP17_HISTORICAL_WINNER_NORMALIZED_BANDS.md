# CASP17 Historical Winner-Normalized Bands

- generated: `2026-06-10T23:18:19+09:00`
- status: `historical_winner_normalized_bands_ready_for_review`
- bands top5/winner-proximity/blocked/total: `5/4/0/5`
- strict-blind slots ready/total: `40/40`
- metric rows ready/total: `440/440`
- official archive baseline/proof-eligible: `24/0`
- first blocked: `-` `-`
- next action: keep scoring model1 and best-of-5 under no-leak replay controls

## Bands

| band | metric | current | winner | ratio | top5 | top3 | status | blocker |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `casp15_regular_domain` | `SUM Zscore` | `100.0` | `90.4273` | `1.105861` | `73.0` | `85.0` | `top3_winner_proximity` | `-` |
| `casp16_regular_domain` | `SUM Zscore` | `45.0` | `40.8978` | `1.100304` | `33.3` | `36.3` | `top3_winner_proximity` | `-` |
| `casp16_multimer_complex` | `complex z-score and DockQ` | `15.9096` | `15.4` | `1.033091` | `0.0` | `14.5` | `top3_winner_proximity` | `-` |
| `casp16_ligand_pose_affinity` | `mean LDDT-PLI` | `0.81` | `0.8` | `1.0125` | `0.69` | `0.8` | `top3_winner_proximity` | `-` |
| `accuracy_estimation_model_selection` | `top1 selection accuracy` | `0.72` | `1.0` | `0.72` | `0.7` | `0.8` | `top5_competitive` | `-` |

## Claim Boundary

Local CASP17 historical winner-normalized band contract only. It maps CASP15/CASP16 planning bands from CASP17_WIN_TIER_GOAL.md onto current strict-blind historical replay evidence. It does not compute official CASP scores, import official archive submissions as internal predictions, approve no-leak provenance, mutate benchmark rows, push remotes, or submit to CASP.

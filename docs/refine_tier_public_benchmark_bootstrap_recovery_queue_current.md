# R9 Bootstrap Recovery Queue

- status: `refine_tier_public_benchmark_bootstrap_recovery_queue_ready`
- queue_row_count: `25`
- existing_materialized_pair_count: `8`
- candidate_fill_pair_count: `17`
- full_combined_spearman: `0.5315384615384615`
- full_bootstrap_p05: `0.23053846153846155`
- bootstrap_p05_deficit: `0.2694615384615384`
- leave_one_out_improves_p05_count: `4`
- material_bootstrap_p05_driver_count: `2`
- top_recovery_target_id: `3f3e`
- top_recovery_pose_id: `3f3e_197`
- top_recovery_review_class: `bootstrap_p05_fragility_driver`
- claim_promotion_allowed: `False`

## Top Recovery Rows

| rank | source | target | pose | split | proxy | experimental | rank err | p05 delta if removed | class | next |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `1` | `candidate_fill_preview` | `3f3e` | `3f3e_197` | `holdout` | `-2.392981` | `-10.5033` | `18` | `0.124157190635` | `bootstrap_p05_fragility_driver` | Review this pair's internal_deltaG value, metric method, input artifact hashes, pose assignment, and experimental deltaG mapping before relying on it for claim-grade bootstrap support. |
| `2` | `existing_materialized` | `2j7h` | `2j7h_48` | `fit` | `-2.153397` | `-9.80496` | `16` | `0.0816789297659` | `bootstrap_p05_fragility_driver` | Review this pair's internal_deltaG value, metric method, input artifact hashes, pose assignment, and experimental deltaG mapping before relying on it for claim-grade bootstrap support. |
| `3` | `candidate_fill_preview` | `4k77` | `4k77_167` | `fit` | `-4.21575` | `-9.0435` | `5` | `0.0146789297659` | `neutral_pair_monitor` | Keep as candidate-only evidence until operator-reviewed metric source payload receipt exists. |
| `4` | `existing_materialized` | `1r5y` | `1r5y_167` | `fit` | `-3.386403` | `-8.80749` | `5` | `0.00654849498328` | `neutral_pair_monitor` | Keep as monitored materialized evidence while higher-impact p05 drivers are reviewed. |
| `5` | `existing_materialized` | `4e5w` | `4e5w_121` | `fit` | `-7.432395` | `-10.4468` | `1` | `-0.0289297658863` | `supportive_pair_monitor` | Keep as monitored materialized evidence while higher-impact p05 drivers are reviewed. |
| `6` | `candidate_fill_preview` | `4j28` | `4j28_123` | `holdout` | `-3.853712` | `-7.7748` | `1` | `-0.0320602006689` | `supportive_pair_monitor` | Keep as candidate-only evidence until operator-reviewed metric source payload receipt exists. |
| `7` | `candidate_fill_preview` | `3n86` | `3n86_99` | `fit` | `-8.336393` | `-7.692` | `13` | `-0.0358862876254` | `rank_order_conflict_review` | Review rank-order conflict against public experimental deltaG before rerunning bootstrap gates. |
| `8` | `existing_materialized` | `3udh` | `3udh_359` | `fit` | `-2.556729` | `-3.89339` | `2` | `-0.041016722408` | `supportive_pair_monitor` | Keep as monitored materialized evidence while higher-impact p05 drivers are reviewed. |
| `9` | `candidate_fill_preview` | `3rr4` | `3rr4_369` | `fit` | `-5.174766` | `-6.21014` | `9` | `-0.0550602006689` | `rank_order_conflict_review` | Review rank-order conflict against public experimental deltaG before rerunning bootstrap gates. |
| `10` | `candidate_fill_preview` | `3n7a` | `3n7a_955` | `holdout` | `-3.302813` | `-5.04631` | `5` | `-0.058016722408` | `supportive_pair_monitor` | Keep as candidate-only evidence until operator-reviewed metric source payload receipt exists. |
| `11` | `existing_materialized` | `1syi` | `1syi_353` | `holdout` | `-5.934925` | `-7.4282` | `7` | `-0.0585819397993` | `supportive_pair_monitor` | Keep as monitored materialized evidence while higher-impact p05 drivers are reviewed. |
| `12` | `existing_materialized` | `1s38` | `1s38_117` | `holdout` | `-3.284752` | `-7.03256` | `2` | `-0.0585819397993` | `supportive_pair_monitor` | Keep as monitored materialized evidence while higher-impact p05 drivers are reviewed. |

## Claim Boundary

R9 bootstrap recovery queue only re-reads existing materialized and candidate-fill public-benchmark pairs to rank review targets that most affect bootstrap Spearman p05. It does not compute new metric values, write metric payload JSON, approve receipts, promote canonical intake, change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate external state.

## Next Step

Review the highest positive leave-one-out p05 drivers and rank-order conflicts before writing reviewed metric payloads or rerunning claim-grade bootstrap gates.

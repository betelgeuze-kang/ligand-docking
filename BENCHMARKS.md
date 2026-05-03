# 벤치마크 데이터 요약

최종 갱신: 2026-05-03 KST

이 문서는 GitHub에 공개해도 되는 현재 벤치마크 evidence를 한 곳에 정리한 인덱스입니다. 원본 source of truth는 로컬 `runs/` 산출물이며, 대용량 trajectory, 동역학 데이터, raw run-output 파일은 Git에 포함하지 않습니다.

## Claim 범위

현재 로컬 납품 claim 범위는 제한된 `kinase`, `gpcr`, `ion_channel`에만 적용합니다. restricted local P0는 green이지만 commercial scale-up claim은 아직 blocked입니다.

아래 수치를 일반 상용 플랫폼 전체, 일반 GPCR-family scale-up, transporter, CA2/PXR, broader IDP promotion, unattended decision-making claim으로 확장하면 안 됩니다. GPCR positive freeze, frozen-candidate scoreability, family-held-out scorecard, and leakage audit are green, but the guarded 100k rerun still fails claim review on CI-low and top20 stability. `claim_promotion_allowed=false`는 유지합니다.

For the GPCR non-ADRB2 positive freeze workflow, `config/gpcr_non_adrb2_positive_candidates_v1.csv` is the curated candidate input schema. The intended handoff is candidate CSV -> `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json` -> `runs/gpcr_positive_coverage_freeze_packet_current.json` -> `runs/gpcr_frozen_candidate_profile_support_current/summary.json` -> `runs/gpcr_frozen_candidate_scoreability_current.json` -> `runs/gpcr_family_heldout_scorecard_current.json` / `runs/gpcr_family_heldout_scorecard_guardrail_current.json` -> `runs/gpcr_guarded_100k_rerun_readiness_current.json`; the current freeze packet is `frozen=true` with `positive_count=9`, `new_non_adrb2_positive_count=3`, `distinct_positive_gpcr_target_count=4`, and `leakage_audit_pass=true`. Profile support is `profile_ready=true`, scoreability is `pass=true` with `freeze_positive_count=9` and `profile_positive_count=9`, and readiness now has `launch_eligible=true` / `claim_review_eligible=false`. The helper command is `python3 tools/build_gpcr_frozen_candidate_profile_support.py --native-source-csv config/gpcr_non_adrb2_native_sources_v1.csv`, followed by scoreability and readiness refresh.

Transporter AQP1/GLUT1 evidence closure and CA2/PXR placeholder/provenance closure are post-P0 follow-up work only; AQP1/GLUT1 stay parked/review-only outside the delivery claim, and CA2/PXR stays prep-only until placeholder/provenance and `replacement_reference_binding_kcal_mol` are closed. GPCR recovery candidates (`gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, `gpcr_core_structure_support_rescore_v1`) stay comparison-only shadow/guarded-apply lanes. The frozen non-ADRB2 guarded 100k rerun completed with `positive_count=9`, stage2 `40000/40000` ok rows, leakage audit `pass=true`, and family-held-out `pass=true`, but `claim_safe=false` persists because `PR-AUC=0.22869872098030358`, `ranking_pr_auc_ci_low=0.0019312183264511504 < 0.45`, and `top20=0.10 < 0.20`. The operator packet for that blocker is `runs/gpcr_ci_low_recovery_packet_current.md`: `## Metric Table` and `## Rank And Bootstrap Diagnostics` carry the positive ranks, top20 misses, and bootstrap view. `ligand_heavy_runs` cleanup is storage housekeeping only: 2026-05-02 deleted 189 stale `stage2_trajectory_frames` payloads (`98125333296` bytes), the 2026-05-03 follow-up execute pass deleted_count=12 remaining raw trajectory payloads (`556010987428` bytes), and the 2026-05-03 structure-support rerun cleanup deleted the stalled partial payload (`38346317024` bytes) plus the completed rollout payload (`51265129536` bytes). After the latest cleanup, `/` usage is `57%` and `runs/local_heavy_runs` is `28K`. Cleanup does not change the delivery claim, any metric, or the current GPCR `claim_safe=false` boundary. See `docs/post_p0_evidence_closure_status.md` for the operator map.

The matching rank-failure diagnostic packet is `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`. It shows all three non-ADRB2 positives are still tail-ranked (`HTR2A` global rank `1413`, `OPRM1` `3138`, `DRD2` `5298`), so its `next_action` is `claim-locked family-balanced scoring candidate implementation`. The accepted path is shadow/replay -> guarded apply -> full 100k claim review; do not rerun the same packet as claim evidence, and keep `claim_promotion_allowed=false` with threshold relaxation/fake pass forbidden.

The first family-balanced frozen guarded rerun completed after an interrupted execution was resumed with the same tag and set-spec. Stage2 resume reused `34186` existing trajectory rows and generated the remaining `5814`, yielding `40000/40000` ok rows. Ranking recovered materially (`PR-AUC=0.5186945103743427`, `top20=0.25`, `strict_gate_pass=true`) but operational claim review still failed because `PR-AUC < 0.55` and `ranking_pr_auc_ci_low=0.1485815545422209 < 0.45`. This is comparison/reject evidence only; `claim_promotion_allowed=false` remains in force.

2026-05-02에 `fixed_family_reference` score scaling lane도 comparison-only로 추가하고 full 100k까지 실행했습니다. `runs/gpcr_score_reference_stats_current.json`은 fit-role scored rows만 사용하며 `reference_row_count=24`, `eval_role_used_in_reference_count=0`, feature stats `12/12`입니다. 생성된 candidate set-spec은 `runs/gpcr_scaleup_100k_fixed_reference_decoy_intrusion_candidate_current/specs/gpcr_core_decoy_intrusion_100k_fixed-ref-decoy-intrusion100k.json`이고, 실제 full 100k run은 `PR-AUC=0.0328`, `PR-AUC CI low=0.0045`, `top20=0.05`로 실패했습니다. 따라서 GPCR scale-up claim은 계속 blocked입니다.

## 현재 Delivery Gate

| 영역 | 현재 결과 | 핵심 벤치마크 값 | Source artifact |
| --- | --- | --- | --- |
| Local delivery preflight | Pass | `overall_ok=true`, `9/9` steps ok, `failed_count=0` | `runs/local_delivery_preflight_current.json` |
| Verdict gate | 제한 범위 delivery-ready | `delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0`, `commercialization_queue_clear=true` | `runs/local_delivery_verdict_gate_current.json` |
| Accuracy gate | Pass | neighbor parity `avg_py=36.7388`, `avg_rs=36.7388`; speed gate enforced | `runs/accuracy_gate_local_delivery_preflight_current.json` |
| Requirements lock | 필수 로컬 세트 complete | `installed=13/13`, `missing=0`, `blocking_missing=0`, optional/deferred missing `7` | `runs/local_delivery_requirements_lock_current.json` |
| Environment manifest | 재현성 snapshot 존재 | Python `3.10.12`, ROCm env configured, `TORCH_BLAS_PREFER_HIPBLASLT=0` | `runs/local_delivery_environment_manifest_current.json` |
| Commercialization queue | 제한 범위 queue clear | `queue_clear=true`, `blocked_count=0`, `partial_count=0`, `keep_green_count=4`, parked science blocker `1` | `runs/local_engine_commercialization_queue_current.json` |

## Nightly And Accuracy Benchmarks

| Benchmark | 결과 | Metrics | Notes |
| --- | --- | --- | --- |
| Nightly stage6 gate | Green | `stage2_ok_rows=72/72`, `stage6_gate_failed=false`, failed gate metrics `0` | 최신 burndown status는 `nightly_gate_green`입니다. |
| Nightly ranking signal | Green | `auc=1.000`, `pr_auc=1.000`, `ef1=2.000`, `bedroc=1.000`, `topk_hit_rate=0.500`; latest top-level reentry smoke/full pass | `2026-05-02_stage6_top_level_reentry` 기준 evidence입니다. |
| Morton/neighbor parity | Green | Python/Rust 평균 neighbor count가 `36.7388`로 일치 | 로컬 accuracy gate support이며 broad external benchmark claim은 아닙니다. |

Primary artifacts:

- `runs/nightly_gate_burndown_packet_current.json`
- `runs/nightly_stage6_top_level_reentry_packet_current.json`
- `runs/accuracy_gate_local_delivery_preflight_current.json`

## Wetlab Selected All-Atom Gate

| Benchmark | 결과 | Metrics | Notes |
| --- | --- | --- | --- |
| T. cruzi PDE selected all-atom hard gate | Pass | selected `mean_min_distance_A=2.120`, threshold `<=2.500` | 현재 P0-C hard gate는 green입니다. |
| Binding proxy | 현재 delivery gate 기준 pass | `binding_energy_proxy=-0.146`, threshold `<=-0.050` | selected all-atom gate를 support합니다. |
| Claim/equivalence gate | Available | policy `allatom_equivalence_acceptance_representative_v1_2026-04-29` | claim/equivalence evidence가 review chain에 붙어 있습니다. |
| Translation quality follow-up | 아직 not ready | score `68.1`, status `borderline`, blocker `binding_energy_proxy_too_weak_for_translation` | post-P0 quality follow-up 전용이며 현재 제한 delivery claim을 막는 blocker는 아닙니다. `claim_promotion_allowed=false` 유지; PDE translation은 `binding_energy_proxy` → `pose RMSD` → `backmapping` → `local minimization survival` 순서로 봅니다. |

Primary artifacts:

- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json`
- `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json`

## GPCR 100k Scale-Up Benchmarks

일반 GPCR-family/commercial scale-up은 여전히 `claim_safe=false`입니다. GPCR scale-up regression guardrail이 현재 최우선 blocker입니다. ADRB2 pharmacophore 결과는 target-specific candidate evidence로만 해석해야 합니다.
현재 GPCR triage packet은 후보 `8`개를 모두 comparison-only로 유지하며, 그중 `7`개는 reject evidence이고 ADRB2 pharmacophore guarded-apply만 target-specific pass evidence입니다.
최신 failure analysis는 raw ranking rows를 다시 읽어 `source_rows_available=true`로 계산되며, 기존 score column `7`개 중 어느 것도 core gate를 회복하지 못했습니다. 주요 root-cause tag는 `donor_prior_decoy_intrusion`, `weak_contact_prior_mismatch`, `affinity_hint_md_support_mismatch`입니다.

| Candidate / lane | 결과 | PR-AUC | PR-AUC CI low | Top20 hit rate | Positives | Score column | Claim boundary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `residual-v4 apply` core 100k | Fail | `0.3888` | `0.0218` | `0.15` | `6` | `binding_score_composite_v7_residual_active` | Negative core-lane evidence |
| `residual-v4 apply` ChEMBL50 100k | Pass, bounded | `0.8312` | `0.7388` | `1.00` | `56` | `binding_score_composite_v7_residual_active` | bounded support only |
| `linear C100` core 100k | Fail | `0.2367` | `0.0295` | `0.05` | `6` | `binding_score_composite_v7_residual_active` | reject/negative evidence |
| `gpcr_core_decoy_intrusion_v1` shadow core 100k | Fail | `0.3910` | `0.0183` | `0.15` | `6` | `binding_score_composite_v7` | shadow-first, no promotion |
| `gpcr_core_decoy_intrusion_v1` guarded apply core 100k | Fail | `0.3890` | `0.0195` | `0.15` | `6` | `binding_score_composite_v7_residual_active` | reject/negative evidence |
| `fixed_family_reference + gpcr_core_decoy_intrusion_v1` core 100k | Fail | `0.0328` | `0.0045` | `0.05` | `6` | `binding_score_composite_v7_residual_active` | reject/negative evidence |
| `gpcr_core_mismatch_contact_rescore_v1` guarded apply core 100k | Fail | `0.3836` | `0.0157` | `0.15` | `6` | `binding_score_composite_v7_residual_active` | reject/negative evidence |
| `gpcr_core_structure_support_rescore_v1` guarded apply core 100k | Fail, recovery-band | `0.5928` | `0.1287` | `0.25` | `6` | `binding_score_composite_v7_residual_active` | comparison/reject evidence only; superseded by frozen non-ADRB2 rerun for coverage/family review |
| frozen non-ADRB2 GPCR guarded 100k | Fail, coverage/family green | `0.2287` | `0.0019` | `0.10` | `9` | `binding_score_composite_v7` | coverage, leakage, and family-held-out pass; CI-low/top20 still block claim |
| `gpcr_core_family_balanced_rescore_v1` frozen guarded 100k | Fail, recovery-band | `0.5187` | `0.1486` | `0.25` | `9` | `binding_score_composite_v7_residual_active` | resumed r2 completed; strict gate green but operational PR-AUC/CI-low gate still blocks claim |
| `gpcr_adrb2_beta_blocker_pharmacophore_v1` shadow residual audit | Pass, audit-only | `1.0000` | `1.0000` | `0.30` | `6` | `binding_score_composite_v7_residual_shadow` | shadow audit only |
| `gpcr_adrb2_beta_blocker_pharmacophore_v1` guarded apply core 100k | Pass, target-specific | `1.0000` | `1.0000` | `0.30` | `6` | `binding_score_composite_v7_residual_active` | ADRB2 beta-blocker-like only |
| `gpcr_adrb2_beta_blocker_pharmacophore_v1` guarded apply ChEMBL50 100k | Pass, target-specific | `0.9662` | `0.9264` | `1.00` | `56` | `binding_score_composite_v7_residual_active` | ADRB2 beta-blocker-like only |

ADRB2 pharmacophore candidate는 target-specific beta-blocker/aryloxypropanolamine SMARTS reward를 사용합니다. 현재 ChEMBL50 ADRB2 후보는 `coverage-only/review-required`입니다. Non-leaky GPCR +3 requirement and family-held-out scorecard are now green (`gpcr_positive_count=9`, `gpcr_distinct_positive_target_count=4`), but GPCR-family/router-level promotion is still forbidden until the same full 100k claim-review gate clears CI-low and top20 stability.

Next comparison rule:

- `linear C100`은 실제 full 100k rerun에서 실패했으므로 reject evidence로 유지합니다.
- `fixed_family_reference`, `gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, `gpcr_core_structure_support_rescore_v1`은 바로 claim하지 않습니다.
- `fixed_family_reference` scaling 후보는 fit-role-only stats와 eval-role non-use audit가 붙은 guarded comparison lane으로 실행했고 full 100k에서 실패했으므로 reject evidence로 유지합니다.
- `gpcr_core_decoy_intrusion_v1` guarded apply core 100k는 2026-05-02 재실행에서 metric까지 도달했지만 PR-AUC/top20 gate가 실패했으므로 reject evidence로 유지합니다.
- `gpcr_core_mismatch_contact_rescore_v1` guarded apply core 100k는 2026-05-02 `safesync/cache-disabled` 실행에서 stage2를 10000/10000 row로 완주했지만 PR-AUC/top20 gate가 실패했으므로 reject evidence로 유지합니다.
- `gpcr_core_structure_support_rescore_v1` guarded apply rollout run은 recovery-band ranking signal(`PR-AUC=0.592849548112706`, `ROC-AUC=0.9961310119404976`, `top20=0.25`, `strict_gate_pass=true`)을 회복했지만 operational gate가 `ranking_pr_auc_ci_low=0.12868359671529103 < 0.45`로 실패했으므로 reject evidence로 유지합니다.
- Frozen non-ADRB2 guarded 100k는 launch/family/leakage를 통과했지만 operational claim review가 `ranking_pr_auc_ci_low=0.0019312183264511504` 및 `top20=0.10`으로 실패했습니다. 같은 패킷을 claim evidence로 재실행하지 말고 scoring/ranking quality를 고친 뒤 새 guarded evidence를 만들어야 합니다.
- 이 후보들은 같은 full 100k gate에서 shadow 또는 guarded apply 비교를 먼저 통과해야 하며, `gpcr_core_full`과 `ChEMBL50` lane을 분리해서 기록합니다.
- 비교가 green이어도 GPCR-family claim으로 승격하려면 현재 green인 family-held-out/non-leaky validation에 더해 CI-low/top20 full 100k claim-review gate가 green이어야 합니다. 현재 ChEMBL50 ADRB2 후보는 coverage-only/review-required 상태입니다.

Primary artifacts:

- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set2_expanded_ood_gpcr_chembl50_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_linear_c100_logit_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_core_decoy_intrusion_shadow_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-05-02_gpcr_decoy_intrusion_apply_core_v2_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-05-02_mismatch_contact_apply_safesync_r3_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_summary.json`
- `runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage5_ranking_summary.json`
- `runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_summary.json`
- `runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage2_traj_summary.json`
- `runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json`
- `runs/gpcr_adrb2_pharmacophore_shadow_score_eval_current_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_adrb2_pharmacophore_apply_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_adrb2_pharmacophore_chembl50_apply_v1_set2_expanded_ood_gpcr_chembl50_full_p0_n100000_r1_summary.json`
- `runs/gpcr_scaleup_regression_triage_current.json`
- `runs/gpcr_ci_low_recovery_packet_current.json`
- `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`
- `runs/gpcr_positive_coverage_expansion_packet_current.json`
- `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json`
- `runs/gpcr_positive_coverage_freeze_packet_current.json`
- `runs/gpcr_frozen_candidate_profile_support_current/summary.json`
- `runs/gpcr_frozen_candidate_scoreability_current.json`
- `runs/gpcr_family_heldout_scorecard_current.json`
- `runs/gpcr_family_heldout_scorecard_guardrail_current.json`
- `runs/gpcr_guarded_100k_rerun_readiness_current.json`
- `runs/gpcr_100k_failure_analysis_current.json`
- `runs/gpcr_scaleup_100k_residualv4_apply_recovery_packet_current.json`
- `runs/gpcr_score_reference_stats_current.json`
- `runs/gpcr_scaleup_100k_fixed_reference_decoy_intrusion_candidate_current/specs/gpcr_core_decoy_intrusion_100k_fixed-ref-decoy-intrusion100k.json`
- `runs/external_validation_2026-05-02_fixed_reference_decoy_intrusion_r1_set1_core_blind_gpcr_core_full_summary.json`
- `runs/gpcr_ci_low_recovery_packet_current.md`

## Scale-Up KPI Snapshot

| 영역 | 현재 결과 | 값 | Source artifact |
| --- | --- | --- | --- |
| Scale-up benchmark claim safety | Blocked | `claim_safe=false`, status `regression_guardrail_failed` | `runs/ligand_scaleup_benchmark_summary_current.json` |
| Guardrails | Blocked | pass `0`, fail `5`, pending `0` | `runs/ligand_scaleup_benchmark_summary_current.json` |
| Suite status | Not commercialization-ready | suites `3`, ready `2`, comparison-ready `2`, commercialization-ready `0` | `runs/ligand_scaleup_suite_status_current.json` |
| Pending suites | Pending | `equal_size_ab`, `pilot_100k`, `pilot_1m` | `runs/ligand_scaleup_suite_status_current.json` |
| KPI artifact coverage | Measured | `missing_artifact_count=0`, planning-ready `6/6` | `runs/ligand_scaleup_kpi_current.json` |
| Speed guardrail | Fail | slowest task `ion_trpv1_chembl50_full`, measured end-to-end speedup `0.458x` vs threshold `>=1.8x` | `runs/ligand_scaleup_benchmark_summary_current.json` |
| Projected runtime | Measured, not target-ready | slowest projected `1M=16.22h`, `100k=97.31min` | `runs/ligand_scaleup_kpi_current.json` |

## Commercial Expansion Snapshot

| 영역 | 현재 결과 | 값 | Notes |
| --- | --- | --- | --- |
| Core commercial lane score | 강하지만 full-platform ready는 아님 | `82.5` | 우선순위 판단용이며 broad commercial claim은 아닙니다. |
| Family expansion surface | Tracked | `family_count=7` | claim 확장 전 family-held-out scorecard가 필요합니다. |
| Transporter lane | 아직 not claim-safe | closure queue rows `6`, placeholder burndown rows `12` | AQP1/GLUT1 stay outside the delivery claim; AQP1 is first-wave and GLUT1 is second-wave, and the lane remains parked/review-only until closure is complete. |
| AQP1 first-wave quantitative readiness | Blocked | claim-safe kcal-ready count `0` | 포함 전 evidence closure가 필요합니다; `AqB013` exact-human-activity hold stays qualified and `replacement_reference_binding_kcal_mol` remains blank. |
| CA2/PXR lanes | prep-only | CA2 core ledger `3/3` non-placeholder but replacement readiness `0/12`; PXR `8/14` ready-for-apply rows | CA2 still needs replacement workbook closure before config freeze, and PXR stays prep-only until quantitative provenance and `replacement_reference_binding_kcal_mol` close. |

Primary artifacts:

- `runs/commercialization_readiness_current.json`
- `runs/transporter_commercialization_closure_queue_current.json`
- `runs/family_readiness_heatmap_current.json`
- `docs/post_p0_commercial_expansion_queue.md`
- `docs/post_p0_evidence_closure_status.md`

## Refresh Commands

이 문서를 갱신하기 전, repo root에서 아래 evidence surface를 먼저 refresh합니다.

```bash
python3 tools/run_local_delivery_preflight.py
python3 tools/build_local_delivery_verdict_gate.py
python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py
python3 tools/build_ligand_scaleup_kpi_table.py
python3 tools/build_ligand_scaleup_benchmark_summary.py
python3 tools/build_ligand_scaleup_suite_status.py
python3 tools/build_gpcr_100k_failure_analysis.py
python3 tools/build_gpcr_score_reference_stats.py --scores-csv runs/ligand_htvs_nightly_2026-05-02_smoke_stage3_scores.csv --split-csv config/ligand_eval_splits_blind_gpcr_adrb2_v1.csv
python3 tools/build_gpcr_scaleup_recovery_packet.py
python3 tools/build_gpcr_scaleup_regression_triage.py
python3 tools/build_gpcr_ci_low_recovery_packet.py --triage-json runs/gpcr_scaleup_regression_triage_current.json
python3 tools/build_gpcr_family_heldout_scorecard.py
python3 tools/build_gpcr_family_heldout_scorecard_guardrail.py
python3 tools/build_gpcr_positive_coverage_expansion_packet.py --family-scorecard-json runs/gpcr_family_heldout_scorecard_current.json
python3 tools/build_gpcr_non_adrb2_candidate_leakage_audit.py
python3 tools/build_gpcr_positive_coverage_freeze_packet.py
python3 tools/build_gpcr_frozen_candidate_profile_support.py --native-source-csv config/gpcr_non_adrb2_native_sources_v1.csv
python3 tools/build_gpcr_frozen_candidate_scoreability_packet.py --profile-json runs/gpcr_frozen_candidate_profile_support_current/profile.json
python3 tools/build_gpcr_guarded_100k_rerun_readiness.py
python3 tools/build_post_p0_claim_blocker_rollup.py
python3 tools/build_commercialization_readiness_report.py
```

Crash/resume operation for long tests:

- `run_external_validation_blind_sets.py` and `run_ligand_stress_validation.py` default to `--resume`; rerun the same command with the same `--tag`, `--set-spec-json`, and `--sets` after a shutdown.
- Stage2 trajectory generation now forwards `--traj-resume-existing` by default, so existing trajectory artifacts are reused instead of regenerated.
- Candidate profiles can pin this behavior with `"traj_resume_existing": true`; use `"traj_resume_existing": false` only for intentional cold reruns.

Delivery bundle publication은 이 요약 문서가 아니라 runbook을 기준으로 진행합니다.

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_verdict_template.md`

## Interpretation Rules

- 제한된 local-delivery verdict green은 broad commercial platform readiness와 다릅니다.
- Shadow evidence는 단독으로 delivery-ready claim이 될 수 없습니다.
- Target-specific ADRB2 pharmacophore gain은 full GPCR-family/router gain으로 단독 승격할 수 없습니다.
- `claim_promotion_allowed=false` stays in force for GPCR recovery; frozen packet, scoreability, leakage audit, and family-held-out are green, but the guarded 100k claim-review gate still fails CI-low/top20.
- GPCR recovery candidates (`gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, and `gpcr_core_structure_support_rescore_v1`) stay comparison-only shadow/guarded-apply candidates; the GPCR scale-up regression guardrail is the first blocker and claim promotion is forbidden until the same full 100k gate clears `ranking_pr_auc_ci_low >= 0.45` and `top20_hit_rate >= 0.20`.
- For the current GPCR CI-low blocker, use `runs/gpcr_ci_low_recovery_packet_current.md`: `## Metric Table` carries `ranking_pr_auc_ci_low`, `ranking_topk_hit_rate_max_possible`, and `ranking_positive_count`; `## Rank And Bootstrap Diagnostics` carries `positive_ranks` and `top20_missing_positives`; `## Recommended Next Actions` keeps the next hard blocker order. The matching JSON source is `runs/gpcr_ci_low_recovery_packet_current.json`.
- For coverage expansion, use `runs/gpcr_positive_coverage_expansion_packet_current.json`, `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json`, `runs/gpcr_positive_coverage_freeze_packet_current.json`, `runs/gpcr_frozen_candidate_profile_support_current/summary.json`, `runs/gpcr_frozen_candidate_scoreability_current.json`, `runs/gpcr_family_heldout_scorecard_current.json`, `runs/gpcr_family_heldout_scorecard_guardrail_current.json`, and `runs/gpcr_guarded_100k_rerun_readiness_current.json`. Current selected ChEMBL50 ADRB2 candidates are coverage candidates only because they carry `target_specific_adrb2_bias_review_required`; the non-ADRB2 positive freeze workflow uses `config/gpcr_non_adrb2_positive_candidates_v1.csv`, is frozen, scoreability is green via RCSB-backed profile support, and family-held-out is green. Router/platform claim remains forbidden because CI-low/top20 claim review is still blocked.
- Transporter AQP1/GLUT1 stays parked/review-only outside the delivery claim until the evidence closure queue is complete.
- CA2/PXR remain prep-only expansion candidates until placeholder/provenance and `replacement_reference_binding_kcal_mol` are closed.
- `runs/` artifact가 stale/missing이면 green으로 추정하지 말고 blocked/internal-review로 봅니다.
- Threshold relaxation, fake-pass wording, manual metric editing은 금지합니다.

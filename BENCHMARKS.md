# 벤치마크 데이터 요약

최종 갱신: 2026-05-01 KST

이 문서는 GitHub에 공개해도 되는 현재 벤치마크 evidence를 한 곳에 정리한 인덱스입니다. 원본 source of truth는 로컬 `runs/` 산출물이며, 대용량 trajectory, 동역학 데이터, raw run-output 파일은 Git에 포함하지 않습니다.

## Claim 범위

현재 delivery-ready 주장은 제한된 로컬 납품 범위인 `kinase`, `gpcr`, `ion_channel`에만 적용합니다.

아래 수치를 일반 상용 플랫폼 전체, 일반 GPCR-family scale-up, transporter, CA2/PXR, broader IDP promotion, unattended decision-making claim으로 확장하면 안 됩니다. broad scale-up과 family expansion은 아직 non-leaky family-held-out validation과 family scorecard가 추가로 필요합니다.

## 현재 Delivery Gate

| 영역 | 현재 결과 | 핵심 벤치마크 값 | Source artifact |
| --- | --- | --- | --- |
| Local delivery preflight | Pass | `overall_ok=true`, `9/9` steps ok, `failed_count=0` | `runs/local_delivery_preflight_current.json` |
| Verdict gate | 제한 범위 delivery-ready | `delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0` | `runs/local_delivery_verdict_gate_current.json` |
| Accuracy gate | Pass | neighbor parity `avg_py=36.7388`, `avg_rs=36.7388`; speed gate enforced | `runs/accuracy_gate_local_delivery_preflight_current.json` |
| Requirements lock | 필수 로컬 세트 complete | `installed=13/13`, `missing=0`, `blocking_missing=0`, optional/deferred missing `7` | `runs/local_delivery_requirements_lock_current.json` |
| Environment manifest | 재현성 snapshot 존재 | Python `3.10.12`, ROCm env configured, `TORCH_BLAS_PREFER_HIPBLASLT=0` | `runs/local_delivery_environment_manifest_current.json` |
| Commercialization queue | 제한 범위 queue clear | `queue_clear=true`, `blocked_count=0`, `keep_green_count=4`, parked science blocker `1` | `runs/local_engine_commercialization_queue_current.json` |

## Nightly And Accuracy Benchmarks

| Benchmark | 결과 | Metrics | Notes |
| --- | --- | --- | --- |
| Nightly stage6 gate | Green | `stage2_ok_rows=72/72`, `stage6_gate_failed=false`, failed gate metrics `0` | 최신 burndown status는 `nightly_gate_green`입니다. |
| Nightly ranking signal | Green | `auc=1.000`, `pr_auc=1.000`, `ef1=2.000`, `bedroc=1.000`, `ece=0.256`, `topk_hit_rate=0.500` | top-level reentry/burndown chain 기준 evidence입니다. |
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
| Translation quality follow-up | 아직 not ready | score `68.1`, status `borderline`, blocker `binding_energy_proxy_too_weak_for_translation` | post-P0 quality follow-up 전용이며 현재 제한 delivery claim을 막는 blocker는 아닙니다. |

Primary artifacts:

- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json`
- `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json`

## GPCR 100k Scale-Up Benchmarks

일반 GPCR-family/commercial scale-up은 여전히 `claim_safe=false`입니다. ADRB2 pharmacophore 결과는 target-specific candidate evidence로만 해석해야 합니다.

| Candidate / lane | 결과 | PR-AUC | PR-AUC CI low | Top20 hit rate | Positives | Score column | Claim boundary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `residual-v4 apply` core 100k | Fail | `0.3888` | `0.0218` | `0.15` | `6` | `binding_score_composite_v7_residual_active` | Negative core-lane evidence |
| `residual-v4 apply` ChEMBL50 100k | Pass, bounded | `0.8312` | `0.7388` | `1.00` | `56` | `binding_score_composite_v7_residual_active` | bounded support only |
| `linear C100` core 100k | Fail | `0.2367` | `0.0295` | `0.05` | `6` | `binding_score_composite_v7_residual_active` | reject/negative evidence |
| `gpcr_core_decoy_intrusion_v1` shadow core 100k | Fail | `0.3910` | `0.0183` | `0.15` | `6` | `binding_score_composite_v7` | shadow-first, no promotion |
| `gpcr_adrb2_beta_blocker_pharmacophore_v1` shadow residual audit | Pass, audit-only | `1.0000` | `1.0000` | `0.30` | `6` | `binding_score_composite_v7_residual_shadow` | shadow audit only |
| `gpcr_adrb2_beta_blocker_pharmacophore_v1` guarded apply core 100k | Pass, target-specific | `1.0000` | `1.0000` | `0.30` | `6` | `binding_score_composite_v7_residual_active` | ADRB2 beta-blocker-like only |
| `gpcr_adrb2_beta_blocker_pharmacophore_v1` guarded apply ChEMBL50 100k | Pass, target-specific | `0.9662` | `0.9264` | `1.00` | `56` | `binding_score_composite_v7_residual_active` | ADRB2 beta-blocker-like only |

ADRB2 pharmacophore candidate는 target-specific beta-blocker/aryloxypropanolamine SMARTS reward를 사용합니다. non-leaky family-held-out validation packet과 family scorecard가 green이 되기 전에는 GPCR-family 또는 router-level score로 승격하면 안 됩니다.

Next comparison rule:

- `linear C100`은 실제 full 100k rerun에서 실패했으므로 reject evidence로 유지합니다.
- `gpcr_core_decoy_intrusion_v1`과 `gpcr_core_linear_rescore_v1`은 바로 claim하지 않습니다.
- 두 후보는 같은 full 100k gate에서 shadow 또는 guarded apply 비교를 먼저 통과해야 하며, `gpcr_core_full`과 `ChEMBL50` lane을 분리해서 기록합니다.
- 비교가 green이어도 GPCR-family claim으로 승격하려면 family-held-out scorecard와 non-leaky validation이 별도로 green이어야 합니다.

Primary artifacts:

- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set2_expanded_ood_gpcr_chembl50_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_linear_c100_logit_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_core_decoy_intrusion_shadow_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/gpcr_adrb2_pharmacophore_shadow_score_eval_current_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_adrb2_pharmacophore_apply_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json`
- `runs/external_validation_2026-04-30_gpcr_scaleup_100k_adrb2_pharmacophore_chembl50_apply_v1_set2_expanded_ood_gpcr_chembl50_full_p0_n100000_r1_summary.json`

## Scale-Up KPI Snapshot

| 영역 | 현재 결과 | 값 | Source artifact |
| --- | --- | --- | --- |
| Scale-up benchmark claim safety | Blocked | `claim_safe=false`, status `regression_guardrail_failed` | `runs/ligand_scaleup_benchmark_summary_current.json` |
| Guardrails | Blocked | pass `0`, fail `4`, pending `1` | `runs/ligand_scaleup_benchmark_summary_current.json` |
| Suite status | Not commercialization-ready | suites `3`, ready `2`, comparison-ready `1`, commercialization-ready `0` | `runs/ligand_scaleup_suite_status_current.json` |
| Pending suites | Pending | `equal_size_ab`, `pilot_100k`, `pilot_1m` | `runs/ligand_scaleup_suite_status_current.json` |
| Projected 100k runtime | Planning estimate | mean projected `50.65 min` | `runs/ligand_scaleup_kpi_current.json` |
| Projected 1m runtime | Planning estimate | mean projected `8.44 hr` | `runs/ligand_scaleup_kpi_current.json` |
| 10k measured latency | Planning estimate | mean `303.89 sec`, stage2 share `86.01%` | `runs/ligand_scaleup_kpi_current.json` |

## Commercial Expansion Snapshot

| 영역 | 현재 결과 | 값 | Notes |
| --- | --- | --- | --- |
| Core commercial lane score | 강하지만 full-platform ready는 아님 | `82.5` | 우선순위 판단용이며 broad commercial claim은 아닙니다. |
| Family expansion surface | Tracked | `family_count=7` | claim 확장 전 family-held-out scorecard가 필요합니다. |
| Transporter lane | 아직 not claim-safe | closure queue rows `6`, placeholder burndown rows `12` | AQP1/GLUT1은 현재 delivery claim 밖에 둡니다. |
| AQP1 first-wave quantitative readiness | Blocked | claim-safe kcal-ready count `0` | 포함 전 evidence closure가 필요합니다. |

Primary artifacts:

- `runs/commercialization_readiness_current.json`
- `runs/transporter_commercialization_closure_queue_current.json`
- `runs/family_readiness_heatmap_current.json`
- `docs/post_p0_commercial_expansion_queue.md`

## Refresh Commands

이 문서를 갱신하기 전, repo root에서 아래 evidence surface를 먼저 refresh합니다.

```bash
python3 tools/run_local_delivery_preflight.py
python3 tools/build_local_delivery_verdict_gate.py
python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py
python3 tools/build_ligand_scaleup_benchmark_summary.py
python3 tools/build_ligand_scaleup_suite_status.py
python3 tools/build_ligand_scaleup_kpi_table.py
python3 tools/build_commercialization_readiness_report.py
```

Delivery bundle publication은 이 요약 문서가 아니라 runbook을 기준으로 진행합니다.

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_verdict_template.md`

## Interpretation Rules

- 제한된 local-delivery verdict green은 broad commercial platform readiness와 다릅니다.
- Shadow evidence는 단독으로 delivery-ready claim이 될 수 없습니다.
- Target-specific ADRB2 pharmacophore gain은 family-held-out validation 전까지 GPCR-family gain이 아닙니다.
- `runs/` artifact가 stale/missing이면 green으로 추정하지 말고 blocked/internal-review로 봅니다.
- Threshold relaxation, fake-pass wording, manual metric editing은 금지합니다.

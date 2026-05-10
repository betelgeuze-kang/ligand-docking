# 벤치마크 데이터 요약

최종 갱신: 2026-05-05 KST

이 문서는 GitHub에 공개해도 되는 현재 벤치마크 evidence를 한 곳에 정리한 인덱스입니다. 원본 source of truth는 로컬 `runs/` 산출물이며, 대용량 trajectory, 동역학 데이터, raw run-output 파일은 Git에 포함하지 않습니다.

## Claim 범위

현재 로컬 납품 claim 범위는 제한된 `kinase`, `gpcr`, `ion_channel`에만 적용합니다. restricted local P0는 green이지만 commercial scale-up claim은 아직 blocked입니다.

아래 수치를 일반 상용 플랫폼 전체, 일반 GPCR-family scale-up, transporter, CA2/PXR, broader IDP promotion, unattended decision-making claim으로 확장하면 안 됩니다. GPCR positive freeze, frozen-candidate scoreability, family-held-out scorecard, and leakage audit are green, but the current blocker remains GPCR CI-low/top20 ranking quality. The r2 base evidence is `PR-AUC=0.5186945103743427`, `ranking_pr_auc_ci_low=0.1485815545422209`, `top20=0.25`; DRD2 remains buried at global rank `18923` / target rank `5315`. The historical 9-positive `gpcr_core_family_anchor_rescore_v2` replay reached `PR-AUC=0.5767474245351905`, `CI-low=0.21066694653866244`, and `top20=0.25`, but the matching frozen-r2 12-positive comparator is lower at `PR-AUC=0.4326129361306714`, `CI-low=0.12342803469357462`, `top20=0.25`. The v4/v5/v6/v7/v8/v9 shadow lanes are all reject/rework evidence, not claim evidence. Latest direct atom-window v8 base-anchored replay is `PR-AUC=0.1714399632561372`, `CI-low=0.0017126649321306472`, `top20=0.10`; v9 v2-preserved excess-polar replay is `PR-AUC=0.38912765311702374`, `CI-low=0.105138774269897`, `top20=0.25`, still below the v2 matching-label comparator. v10 is selected-slice green but not portable because `none` anchor mode does not rescue DRD2 positive and `all_basic` overpromotes decoys. v11 adds weak-base-gated cationic support and restores the selected DRD2 slice (`positive_rank=1`, `decoys_above_positive=0`), but complete true-base frozen replay is blocked: `input_rows=30000`, `shadow_top20_positive_count=0`, DRD2 decoys above positive `498`, HTR2A `1744`, and OPRM1 `261`. v12 adds a label-free synthetic-anchor saturation penalty plus moderate multi-basic weakbase reward and materially improves DRD2 in the same 30k frozen replay (`global_rank=4102 -> 15`, DRD2 decoys above positive `1505 -> 8`, `top20_positive_count=1`), but HTR2A and OPRM1 remain blocked (`decoys_above_positive=128` and `321`). v13 adds unsupported-strong-base and pose-gap pressure as a claim-locked shadow-only replay, improving the frozen 30k ranks again: DRD2 `global_rank=5` / `target_rank=3` / `decoys_above_positive=2`, HTR2A `134` / `46` / `45`, and OPRM1 `1031` / `255` / `254`, with `shadow_top20_positive_count=1`. v14 tested cationic-center occupancy reward and is reject/rework because HTR2A decoy overpromotion worsened HTR2A target rank to `1139`. v15 removes that reward and keeps cached true-base support-gap penalties only, improving all three frozen positives versus v13: DRD2 `2` / `2` / `1`, HTR2A `39` / `19` / `18`, and OPRM1 `742` / `187` / `186`, with `shadow_top20_positive_count=1`. v16 adds false-support discrimination and improves the all-basic frozen replay to DRD2 `2` / `2` / `1`, HTR2A `16` / `7` / `6`, and OPRM1 `583` / `115` / `114`, with `shadow_top20_positive_count=2`, but remains blocked. The adaptive pose-preserving cache completed `30000/30000` rows with `failed_row_count=0` and removes the OPRM1 pose-collapse blocker, but the v16 adaptive replay is still blocked: DRD2 `2` / `2` / `1`, HTR2A `22` / `6` / `5`, OPRM1 `399` / `158` / `157`, `shadow_top20_positive_count=1`, and gap blockers `positive_anchor_support_missing=2`, `positive_pose_preservation_borderline=2`, `target_decoys_above_positive=3`. This is a real feature-generation improvement, but not claim-safe; OPRM1 now needs new target-portable pose/anchor evidence rather than blind scalar tuning. `claim_promotion_allowed=false` stays in force, and delivery/router/platform claim promotion remains forbidden.

For the GPCR non-ADRB2 positive freeze workflow, `config/gpcr_non_adrb2_positive_candidates_v1.csv` is the curated candidate input schema for the 3-positive current freeze, and `config/gpcr_non_adrb2_positive_candidates_coverage_v1.csv` is the coverage-v1 expansion schema with seven non-ADRB2 GPCR positives (`DRD2`, `HTR2A`, `OPRM1`, `DRD3`, `ADORA2A`, `HRH1`, `OPRD1`). The current freeze packet remains `frozen=true` with `positive_count=9`, `new_non_adrb2_positive_count=3`, `distinct_positive_gpcr_target_count=4`, and `leakage_audit_pass=true`. The coverage-v1 freeze is separately materialized as `runs/gpcr_positive_coverage_freeze_packet_coverage_v1_current.json` with `positive_count=13`, `new_non_adrb2_positive_count=7`, `distinct_positive_gpcr_target_count=8`, and `leakage_audit_pass=true`; `runs/gpcr_frozen_candidate_profile_support_coverage_v1_current/summary.json` is `profile_ready=true` with `combined_reference_row_count=22`, `blocked_target_count=0`, and RCSB-backed native centroids for all seven non-ADRB2 GPCR targets. Coverage-v1 scoreability is `pass=true` with `freeze_positive_count=13` and `profile_positive_count=13`, and `runs/gpcr_guarded_100k_rerun_readiness_coverage_v1_current.json` has `launch_eligible=true` / `claim_review_eligible=false`. The coverage-v1 100k candidate set-spec is `runs/gpcr_scaleup_100k_family_balanced_coverage_v1_candidate_current/specs/gpcr_core_family_balanced_rescore_100k_coverage-v1-family-balanced100k.json` and validates with `run_external_validation_blind_sets.py --validate-only`; it is still claim-locked shadow/comparison evidence until a full rerun clears CI-low/top20/leakage-triage review.

Transporter AQP1/GLUT1 evidence closure and CA2/PXR placeholder/provenance closure are post-P0 follow-up work only; AQP1/GLUT1 stay parked/review-only outside the delivery claim, and CA2/PXR stays prep-only until placeholder/provenance and `replacement_reference_binding_kcal_mol` are closed. GPCR recovery candidates (`gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, `gpcr_core_structure_support_rescore_v1`) stay comparison-only shadow/guarded-apply lanes. The frozen non-ADRB2 guarded 100k rerun completed with `positive_count=9`, stage2 `40000/40000` ok rows, leakage audit `pass=true`, and family-held-out `pass=true`, but `claim_safe=false` persists because `PR-AUC=0.22869872098030358`, `ranking_pr_auc_ci_low=0.0019312183264511504 < 0.45`, and `top20=0.10 < 0.20`. The operator packet for that blocker is `runs/gpcr_ci_low_recovery_packet_current.md`: `## Metric Table` and `## Rank And Bootstrap Diagnostics` carry the positive ranks, top20 misses, and bootstrap view. `ligand_heavy_runs` cleanup is storage housekeeping only: 2026-05-02 deleted 189 stale `stage2_trajectory_frames` payloads (`98125333296` bytes), the 2026-05-03 follow-up execute pass deleted_count=12 remaining raw trajectory payloads (`556010987428` bytes), and the 2026-05-03 structure-support rerun cleanup deleted the stalled partial payload (`38346317024` bytes) plus the completed rollout payload (`51265129536` bytes). After the latest cleanup, `/` usage is `57%` and `runs/local_heavy_runs` is `28K`. Cleanup does not change the delivery claim, any metric, or the current GPCR `claim_safe=false` boundary. See `docs/post_p0_evidence_closure_status.md` for the operator map.

The latest r2 rank evidence is `runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.md` plus `..._stage5_ranking_rows.csv`. HTR2A and OPRM1 recover to target-rank 1 (`global_rank=2` and `global_rank=6`), while DRD2 remains buried at `global_rank=18923` / `target_rank=5315`. The refreshed diagnostic packet adds DRD2 atom-anchor evidence under `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json` / `drd2_pose_physics_diagnostics`: the DRD2 positive maintains the native acidic anchor (`Asp114`) with mean distance about `3.25 A`, but the top DRD2 decoy cluster is even closer on average (`2.48 A`). This means the blocker is not simple anchor absence; it is decoy over-anchoring / ligand-physics-prior separation. Keep this as diagnostic-only evidence. The v8/v9 atom-window experiments confirm that direct atom-window reward can lift DRD2 positive rank but also promotes multipolar hard decoys; v9 preserves Top20 but still fails the v2 comparator. v10 proves the selected-slice cationic/pose-distortion contract, v11 full true-base frozen replay shows all-basic synthetic-anchor overpromotion remains too strong, v12 shows the right DRD2 direction but not enough family portability, v13 reduces frozen decoy intrusion, v14 shows cationic occupancy reward is unsafe, v15 improves true-base support-gap ranks, and v16 is the best all-basic frozen shadow for top20 (`DRD2 2/2/1`, `HTR2A 16/7/6`, `OPRM1 583/115/114`). The new adaptive pose-preserving cache removes OPRM1 pose collapse but shows the current feature set cannot separate OPRM1 positive from 157 same-signature decoys without new pose/anchor evidence. Delivery/router/platform claim promotion remains forbidden and `claim_promotion_allowed=false` stays in force until a portable anchor contract and full guarded review clear CI-low/top20.

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
| `gpcr_core_family_balanced_rescore_v1` frozen guarded 100k | Fail, recovery-band | `0.5186945103743427` | `0.1485815545422209` | `0.25` | `9` | `binding_score_composite_v7_residual_active` | r2 base evidence, not claim evidence; resumed run completed; HTR2A/OPRM1 recovered to target-rank 1, DRD2 still buried (`global_rank=18923`, `target_rank=5315`); strict gate green but operational PR-AUC/CI-low gate still blocks claim |
| `gpcr_core_family_anchor_rescore_v2` shadow replay, historical 9-positive labels | Fail, shadow recovery signal | `0.5767474245351905` | `0.21066694653866244` | `0.25` | `9` | `binding_score_composite_v7_residual_shadow` | claim-locked replay only; improves DRD2 to `global_rank=8562` / `target_rank=2435` and shadow decoys-above-positive to `2434`, but CI-low remains below `0.45` |
| `gpcr_core_family_anchor_rescore_v2` shadow replay, frozen-r2 matching labels | Fail, matching-label comparator | `0.4326129361306714` | `0.12342803469357462` | `0.25` | `12` | `binding_score_composite_v7_residual_shadow` | fair comparator for v6/v7 on frozen-r2 labels; still below claim threshold |
| `gpcr_core_acidic_anchor_overcontact_prior_gate_v4` fixed-reference shadow replay | Fail, reject/no-op | `0.008231735935435774` | `0.0009935430341614215` | `0.00` | `9` | `binding_score_composite_v7_residual_shadow` | claim-locked shadow-only replay; active score locked and fixed-family-reference scaling loaded, but gate activation was `0/40000`, so this is reject evidence and not a claim or guarded-apply candidate |
| `gpcr_core_fixed_reference_live_shadow_v5` fixed-reference shadow replay | Fail, reject | `0.0009207359577815573` | `0.0003077463321739179` | `0.00` | `9` | `binding_score_composite_v7_residual_shadow` | claim-locked shadow-only replay; active score locked and fixed-family-reference scaling loaded; pressure telemetry was live (`17494/40000`) but it failed the v2 comparison gate, so next action returns to DRD2 pose/physics rescue |
| `gpcr_core_class_a_motif_shadow_v6` score-only shadow replay | Fail, reject/rework | `0.26256056498741714` | `0.004745732233913355` | `0.15` | `12` | `binding_score_composite_v7_residual_shadow` | frozen-r2 matching-label replay; active score locked to base (`active_delta_max_abs=0.0`) but failed the v2 matching-label comparison gate |
| `gpcr_core_class_a_anchor_geometry_shadow_v7` score-only shadow replay | Fail, reject/rework | `0.2636663162769534` | `0.005472488059524199` | `0.15` | `12` | `binding_score_composite_v7_residual_shadow` | active score locked to base (`active_delta_max_abs=0.0`), but stage3 proxy anchor geometry rewarded DRD2 decoys more than the positive; next work is direct atom-window geometry / hydrophobic-overcontact diagnostics |
| `gpcr_core_direct_atom_anchor_window_shadow_v8` base-anchored shadow replay | Fail, reject/rework | `0.1714399632561372` | `0.0017126649321306472` | `0.10` | `12` | `binding_score_composite_v7_residual_shadow` | positive label included in atom-window cache (`65/65` features), but direct reward promotes DRD2 hard decoys and hurts early enrichment |
| `gpcr_core_atom_window_excess_polar_shadow_v9` v2-preserved shadow replay | Fail, reject/rework | `0.38912765311702374` | `0.105138774269897` | `0.25` | `12` | `binding_score_composite_v7_residual_shadow` | preserves Top20 and applies excess-polar pressure, but still fails the frozen-r2 v2 comparator (`0.4326129361306714`, `0.12342803469357462`, `0.25`) |
| `gpcr_core_cationic_pose_distortion_shadow_v10` selected repaired DRD2 slice replay | Selected-slice green, claim-locked | n/a | n/a | n/a | `1` | `binding_score_composite_v7_residual_shadow` | active score locked to base; selected-slice positive rank `1`, decoys above positive `0`; not full 100k evidence and not claim evidence |
| `gpcr_core_cationic_weakbase_rescue_shadow_v11` selected repaired DRD2 slice + full true-base frozen replay | Selected-slice green, frozen replay blocked | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | selected-slice positive rank `1`, decoys above positive `0`, active locked; full true-base frozen replay `input_rows=30000`, `shadow_top20_positive_count=0`, DRD2 decoys above positive `498`, HTR2A `1744`, OPRM1 `261`; claim locked |
| `gpcr_core_synthetic_anchor_penalty_shadow_v12` full true-base frozen replay | DRD2 recovery signal, family blocked | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | active score locked to base; full frozen replay `input_rows=30000`, `shadow_top20_positive_count=1`, DRD2 `global_rank=15` / `decoys_above_positive=8`, HTR2A `128`, OPRM1 `321`; claim locked |
| `gpcr_core_pose_support_gap_shadow_v13` full true-base frozen replay | Incremental recovery, still blocked | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | active score locked to base; full frozen replay `input_rows=30000`, `shadow_top20_positive_count=1`, DRD2 `global_rank=5` / `target_rank=3` / `decoys_above_positive=2`, HTR2A `134` / `46` / `45`, OPRM1 `1031` / `255` / `254`; claim locked |
| `gpcr_core_truebase_anchor_occupancy_shadow_v14` full true-base frozen replay | Reject/rework, occupancy reward unsafe | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | active score locked to base; cationic-center occupancy reward overpromotes HTR2A decoys; DRD2 `3` / `2`, HTR2A target rank `1139`, OPRM1 target rank `187`; claim locked |
| `gpcr_core_truebase_gap_penalty_shadow_v15` full true-base frozen replay | Best current frozen shadow, still blocked | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | active score locked to base; removes v14 occupancy reward and keeps cached true-base penalties; `shadow_top20_positive_count=1`, DRD2 `global_rank=2` / `target_rank=2` / `decoys_above_positive=1`, HTR2A `39` / `19` / `18`, OPRM1 `742` / `187` / `186`; claim locked |
| `gpcr_core_false_support_discriminator_shadow_v16` full all-basic true-base frozen replay | Best all-basic top20 recovery, still blocked | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | active score locked to base; `shadow_top20_positive_count=2`, DRD2 `2` / `2` / `1`, HTR2A `16` / `7` / `6`, OPRM1 `583` / `115` / `114`; claim locked |
| `gpcr_core_false_support_discriminator_shadow_v16` adaptive pose-preserving true-base frozen replay | Feature-generation repair, still blocked | n/a | n/a | n/a | `3` frozen positives | `binding_score_composite_v7_residual_shadow` | adaptive cache `30000/30000`, failures `0`; OPRM1 pose collapse removed, but `shadow_top20_positive_count=1`, DRD2 `2` / `2` / `1`, HTR2A `22` / `6` / `5`, OPRM1 `399` / `158` / `157`; gap blockers now `positive_anchor_support_missing=2`, `positive_pose_preservation_borderline=2`, `target_decoys_above_positive=3`; claim locked |
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
- `gpcr_core_family_anchor_rescore_v2`는 현재 shadow replay evidence입니다. `gpcr_basic_amine_proxy`는 positives를 잡지만 decoy도 많이 잡아서 단독 claim feature가 아닙니다. Historical 9-positive replay는 `PR-AUC=0.5767474245351905`, `CI-low=0.21066694653866244`, `top20=0.25`였고, frozen-r2 matching-label comparator는 `PR-AUC=0.4326129361306714`, `CI-low=0.12342803469357462`, `top20=0.25`입니다. 둘 다 claim threshold `CI-low >= 0.45` 아래입니다.
- `gpcr_core_acidic_anchor_overcontact_prior_gate_v4`는 fixed-family-reference shadow-only replay까지 실행했지만 reject입니다. `runs/gpcr_acidic_anchor_v4_shadow_replay_summary_current.json` shows `score_scaling_mode=fixed_family_reference`, non-empty `score_reference_stats_hash`, and `shadow_only_active_locked=true`, but `gpcr_acidic_anchor_overcontact_prior_gate` activated on `0/40000` rows and the evaluator produced `PR-AUC=0.008231735935435774`, `PR-AUC CI-low=0.0009935430341614215`, `top20=0.00`. Keep it as negative evidence; the next scorer must be redesigned around fixed-reference-live features rather than relaunching this gate.
- `gpcr_core_family_anchor_rescore_v2` is the feature donor/baseline for the next DRD2 motif-aware diagnostic; broad GPCR/basic-amine generalization is not allowed.
- `gpcr_core_fixed_reference_live_shadow_v5`도 fixed-family-reference shadow-only replay까지 실행했지만 reject입니다. `runs/gpcr_fixed_reference_live_v5_shadow_replay_summary_current.json` shows `fixed_reference_live_positive_pressure_count=17494` and active score locking, but `runs/gpcr_fixed_reference_live_v5_shadow_replay_eval_current.json` produced `PR-AUC=0.0009207359577815573`, `PR-AUC CI-low=0.0003077463321739179`, `top20=0.00`. Keep it as negative evidence and return to DRD2 pose/physics rescue after the v5 reject.
- The class A aminergic/opioid-like orthosteric motif-aware v6, anchor-geometry v7, direct atom-window v8, and excess-polar v9 replays are reject/rework evidence. v8 found that direct atom-window support can improve DRD2 target rank but overpromotes multipolar hard decoys; v9 preserved Top20 but still failed the frozen-r2 v2 comparator. v10 is selected-slice green only after pseudo-allatom repair, closest-basic-amine cationic geometry, and pose-distortion pressure; v11 adds weak-base gating but full true-base frozen replay remains blocked by all-basic synthetic-anchor decoy overpromotion. v12 adds synthetic-anchor saturation pressure, v13 adds pose-support gap pressure, v14 rejects unsafe cationic-occupancy reward, v15 removes that reward, and v16 adds false-support discrimination. v16 improves all-basic top20 recovery, while adaptive pose-preserving repair removes OPRM1 pose collapse but exposes a no-discriminator OPRM1 surface. Positive anchor support and target-internal decoy separation still block claim. Treat v10/v11/v12/v13/v14/v15/v16/adaptive as shadow feature-contract evidence, not claim or guarded-apply wins.
- `gpcr_core_acidic_anchor_overcontact_prior_gate_v4` and `gpcr_core_fixed_reference_live_shadow_v5` are tombstone reject evidence; keep them compare-only and do not relaunch them unchanged.
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
- `runs/gpcr_residual_prototype_spec_family_anchor_v2_shadow.json`
- `runs/gpcr_family_anchor_v2_shadow_replay_eval_current.json`
- `runs/gpcr_residual_prototype_spec_fixed_reference_live_shadow_v5.json`
- `runs/gpcr_fixed_reference_live_v5_shadow_replay_eval_current.json`
- `runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.json`
- `runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.json`
- `runs/gpcr_cationic_pose_distortion_v10_shadow_replay_review_current.json`
- `runs/gpcr_cationic_pose_distortion_frozen_cache_mode_review_current.json`
- `runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json`
- `runs/gpcr_cationic_weakbase_v11_shadow_replay_review_current.json`
- `runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_summary_current.json`
- `runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.json`
- `runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.json`
- `runs/gpcr_cationic_weakbase_v11_frozen_shadow_replay_review_current.json`
- `runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.json`
- `runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.json`
- `runs/gpcr_synthetic_anchor_penalty_v12_frozen_shadow_replay_review_current.json`
- `runs/gpcr_frozen_pose_support_gap_packet_current.json`
- `runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.json`
- `runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.json`
- `runs/gpcr_pose_support_gap_v13_frozen_shadow_replay_review_current.json`
- `runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.json`
- `runs/gpcr_residual_prototype_spec_truebase_anchor_occupancy_shadow_v14.json`
- `runs/gpcr_truebase_anchor_occupancy_v14_frozen_shadow_replay_review_current.json`
- `runs/gpcr_truebase_anchor_occupancy_v14_frozen_gap_packet_current.json`
- `runs/gpcr_residual_prototype_spec_truebase_gap_penalty_shadow_v15.json`
- `runs/gpcr_truebase_gap_penalty_v15_frozen_shadow_replay_review_current.json`
- `runs/gpcr_truebase_gap_penalty_v15_frozen_gap_packet_current.json`
- `runs/gpcr_residual_prototype_spec_false_support_discriminator_shadow_v16.json`
- `runs/gpcr_false_support_discriminator_v16_frozen_shadow_replay_review_current.json`
- `runs/gpcr_false_support_discriminator_v16_frozen_gap_packet_current.json`
- `runs/gpcr_cationic_pose_distortion_frozen_feature_cache_adaptive_truebase_current.json`
- `runs/gpcr_false_support_discriminator_v16_adaptive_frozen_shadow_replay_review_current.json`
- `runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json`
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
python3 tools/build_gpcr_guarded_100k_rank_failure_diagnostics.py
python3 tools/build_gpcr_drd2_pose_generation_repair_packet.py
python3 tools/repair_gpcr_drd2_pseudo_allatom_backmapping.py --anchor-mode positive_only
python3 tools/build_gpcr_atom_window_anchor_feature_cache.py --input-csv runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv --target CHEMBL217_DRD2_HUMAN --score-col score --top-n 0 --include-positives --out-csv runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.csv --out-json runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.json --out-md runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.md
python3 tools/build_gpcr_drd2_cationic_center_geometry_cache.py
python3 tools/build_gpcr_drd2_hard_decoy_slice_packet.py
python3 tools/build_gpcr_drd2_hard_decoy_penalty_envelope.py
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_cationic_pose_distortion_shadow_v10 --out-json runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.json --out-csv runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.csv --out-md runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.json --out-scores-csv runs/gpcr_cationic_pose_distortion_v10_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.md
python3 tools/build_gpcr_cationic_pose_distortion_shadow_replay_review.py
python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN --ligand-filter CHEMBL301265 --anchor-mode none --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.md
python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN --ligand-filter CHEMBL301265 --anchor-mode all_basic --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.md
python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,CHEMBL233_OPRM1_HUMAN --row-limit 300 --anchor-mode all_basic --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.md
python3 tools/build_gpcr_cationic_pose_distortion_frozen_cache_mode_review.py
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_cationic_weakbase_rescue_shadow_v11 --out-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-csv runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.csv --out-md runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-scores-csv runs/gpcr_cationic_weakbase_v11_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_weakbase_v11_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_weakbase_v11_shadow_replay_summary_current.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-scores-csv runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_summary_current.md
python3 tools/build_gpcr_cationic_pose_distortion_shadow_replay_review.py --input-scores-csv runs/gpcr_cationic_weakbase_v11_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_cationic_weakbase_v11_shadow_replay_summary_current.json --out-json runs/gpcr_cationic_weakbase_v11_shadow_replay_review_current.json --out-md runs/gpcr_cationic_weakbase_v11_shadow_replay_review_current.md
python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,CHEMBL233_OPRM1_HUMAN --row-limit 16500 --row-offset 0 --anchor-mode all_basic --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.md
python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,CHEMBL233_OPRM1_HUMAN --row-limit 13500 --row-offset 16500 --anchor-mode all_basic --resume-existing --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-scores-csv runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
python3 tools/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py --input-scores-csv runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --expected-complete-rows 30000
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_synthetic_anchor_penalty_shadow_v12 --out-json runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.json --out-csv runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.csv --out-md runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.json --out-scores-csv runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
python3 tools/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py --input-scores-csv runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --expected-complete-rows 30000 --out-json runs/gpcr_synthetic_anchor_penalty_v12_frozen_shadow_replay_review_current.json --out-md runs/gpcr_synthetic_anchor_penalty_v12_frozen_shadow_replay_review_current.md
python3 tools/build_gpcr_frozen_pose_support_gap_packet.py
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_pose_support_gap_shadow_v13 --out-json runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.json --out-csv runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.csv --out-md runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.json --out-scores-csv runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
python3 tools/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py --input-scores-csv runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --expected-complete-rows 30000 --out-json runs/gpcr_pose_support_gap_v13_frozen_shadow_replay_review_current.json --out-md runs/gpcr_pose_support_gap_v13_frozen_shadow_replay_review_current.md
python3 tools/build_gpcr_frozen_pose_support_gap_packet.py --input-scores-csv runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-json runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.json --out-csv runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.csv --out-md runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.md
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_truebase_anchor_occupancy_shadow_v14 --out-json runs/gpcr_residual_prototype_spec_truebase_anchor_occupancy_shadow_v14.json --out-csv runs/gpcr_residual_prototype_spec_truebase_anchor_occupancy_shadow_v14.csv --out-md runs/gpcr_residual_prototype_spec_truebase_anchor_occupancy_shadow_v14.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_truebase_anchor_occupancy_shadow_v14.json --residual-prototype-mode apply --reset-prior-active-to-base --active-lock-required --out-scores-csv runs/gpcr_truebase_anchor_occupancy_v14_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_truebase_anchor_occupancy_v14_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_truebase_anchor_occupancy_v14_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_truebase_gap_penalty_shadow_v15 --out-json runs/gpcr_residual_prototype_spec_truebase_gap_penalty_shadow_v15.json --out-csv runs/gpcr_residual_prototype_spec_truebase_gap_penalty_shadow_v15.csv --out-md runs/gpcr_residual_prototype_spec_truebase_gap_penalty_shadow_v15.md
python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_truebase_gap_penalty_shadow_v15.json --residual-prototype-mode apply --reset-prior-active-to-base --active-lock-required --out-scores-csv runs/gpcr_truebase_gap_penalty_v15_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_truebase_gap_penalty_v15_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_truebase_gap_penalty_v15_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_family_anchor_rescore_v2 --out-json runs/gpcr_residual_prototype_spec_family_anchor_v2_shadow.json --out-csv runs/gpcr_residual_prototype_spec_family_anchor_v2_shadow.csv --out-md runs/gpcr_residual_prototype_spec_family_anchor_v2_shadow.md
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
- Target-specific ADRB2 pharmacophore gain은 full GPCR-family/router gain이나 broad GPCR/basic-amine generalization으로 단독 승격할 수 없습니다.
- `claim_promotion_allowed=false` stays in force for GPCR recovery; frozen packet, scoreability, leakage audit, and family-held-out are green, but the guarded 100k claim-review gate still fails CI-low/top20.
- `runs/gpcr_residual_prototype_spec_family_anchor_ci_stability_v3.json` is diagnostic-only (`prototype_mode=shadow_only`, `scorer_apply_allowed=false`); if a v4 scorer is not yet merged, keep it as the next shadow/guarded-comparison direction only, not completed evidence.
- GPCR recovery candidates (`gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, and `gpcr_core_structure_support_rescore_v1`) stay comparison-only shadow/guarded-apply candidates; the GPCR scale-up regression guardrail is the first blocker and claim promotion is forbidden until the same full 100k gate clears `ranking_pr_auc_ci_low >= 0.45` and `top20_hit_rate >= 0.20`. Do not try to bypass this with full 100k reruns, threshold relaxation, target identity feature, or fake pass, and do not generalize the v2 basic-amine feature donor into broad GPCR/basic-amine wording.
- The class A aminergic/opioid-like orthosteric motif-aware shadow v6 and anchor-geometry shadow v7 replays are comparison-only reject/rework evidence with active score locked to base. Both failed the frozen-r2 matching-label v2 comparison gate, so the next work is direct atom-window anchor geometry / hydrophobic-overcontact diagnostics rather than GPCR router/broad claim unlock or broad basic-amine wording.
- DRD2 pose-generation repair is now explicit and claim-locked. `runs/gpcr_drd2_pose_generation_repair_packet_current.json` records `positive_global_rank=18923`, `positive_within_target_rank=5315`, `decoys_above_positive_count=5314`, source positive atom coverage `2/14 = 0.142857`, and blockers for tail rank, low backmapping atom coverage, missing pose RMSD/local minimization survival, overanchored decoys, and multipolar-basic intrusion. `runs/gpcr_drd2_pseudo_allatom_repair_current.json` materializes selected-row pseudo-allatom repair only (`65/65` repaired, positive `14` heavy atoms, coverage `1.0`, `anchor_mode=positive_only`, `claim_promotion_allowed=false`). The repaired atom-window cache puts the positive at mean anchor distance `2.8214482267014858 A` with `2.8-4.2 A` window fraction `0.8083333333333333`. `runs/gpcr_drd2_cationic_center_geometry_cache_current.json` now measures closest basic-amine center to acidic anchor and fixes the positive at mean `3.1999997921453787 A` with cationic window fraction `1.0`. With cationic geometry plus pose-distortion pressure, `runs/gpcr_drd2_hard_decoy_slice_packet_current.json` reduces `valid_anchor_challenge_count` to `0` and separates `pose_distorted_valid_anchor_count=10`; the bounded envelope is pairwise-green for this selected repaired slice (`runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json`: `bounded_best_positive_rank=1`, `decoys_above_positive_count=0`, `claim_promotion_allowed=false`). `runs/gpcr_cationic_pose_distortion_frozen_cache_mode_review_current.json` shows why v10 is not portable yet (`none` support `0.0`, `all_basic` top10 decoys `10/10`). v11 restores selected-slice rank `1`, but the complete true-base frozen replay remains blocked (`runs/gpcr_cationic_weakbase_v11_frozen_shadow_replay_review_current.json`: `input_rows=30000`, `shadow_top20_positive_count=0`, DRD2 decoys above positive `498`, HTR2A `1744`, OPRM1 `261`). v12 improves DRD2 materially, v13 improves all three positives, v14 is rejected because cationic occupancy reward overpromotes HTR2A decoys, v15 improves support-gap penalties, and v16 is the best all-basic top20 recovery (`DRD2 2/2/1`, `HTR2A 16/7/6`, `OPRM1 583/115/114`). The adaptive pose-preserving cache completes `30000/30000` rows and removes OPRM1 pose collapse, but the adaptive v16 replay remains blocked (`DRD2 2/2/1`, `HTR2A 22/6/5`, `OPRM1 399/158/157`). The lane is still blocked because positive anchor support and target-internal decoy separation remain insufficient. Next step is OPRM1 target-portable pose/anchor evidence generation or alignment repair plus HTR2A decoy support discrimination, not claim widening.
- For the current GPCR CI-low blocker, use `runs/gpcr_ci_low_recovery_packet_current.md`: `## Metric Table` carries `ranking_pr_auc_ci_low`, `ranking_topk_hit_rate_max_possible`, and `ranking_positive_count`; `## Rank And Bootstrap Diagnostics` carries `positive_ranks` and `top20_missing_positives`; `## Recommended Next Actions` keeps the next hard blocker order. The matching JSON source is `runs/gpcr_ci_low_recovery_packet_current.json`.
- For coverage expansion, use `runs/gpcr_positive_coverage_expansion_packet_current.json`, `config/gpcr_non_adrb2_positive_candidates_coverage_v1.csv`, `config/gpcr_non_adrb2_native_sources_coverage_v1.csv`, `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_coverage_v1_current.json`, `runs/gpcr_positive_coverage_freeze_packet_coverage_v1_current.json`, `runs/gpcr_frozen_candidate_profile_support_coverage_v1_current/summary.json`, `runs/gpcr_frozen_candidate_scoreability_coverage_v1_current.json`, `runs/gpcr_guarded_100k_rerun_readiness_coverage_v1_current.json`, and `runs/gpcr_scaleup_100k_family_balanced_coverage_v1_candidate_current/specs/gpcr_core_family_balanced_rescore_100k_coverage-v1-family-balanced100k.json`. The coverage-v1 workflow is frozen, scoreability is green via RCSB-backed profile support, and the set-spec validates, but router/platform claim remains forbidden because the full guarded rerun has not produced green CI-low/top20/leakage-triage review.
- The next GPCR scorer work is to move beyond scalar penalties and repair the feature-generation surface. v16/adaptive removes the OPRM1 hard pose-collapse blocker, but `runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json` still shows family portability is insufficient (`positive_anchor_support_missing=2`, `positive_pose_preservation_borderline=2`, `target_decoys_above_positive=3`). Add OPRM1 pose/anchor alignment evidence, HTR2A decoy support discrimination, and conditional prior-gating diagnostics before any guarded 100k rerun. Use `gpcr_core_family_anchor_rescore_v2` only as feature donor/baseline and do not generalize `gpcr_basic_amine_proxy` into broad GPCR/basic-amine wording.
- Transporter AQP1/GLUT1 stays parked/review-only outside the delivery claim until the evidence closure queue is complete.
- CA2/PXR remain prep-only expansion candidates until placeholder/provenance and `replacement_reference_binding_kcal_mol` are closed.
- `runs/` artifact가 stale/missing이면 green으로 추정하지 말고 blocked/internal-review로 봅니다.
- Threshold relaxation, fake-pass wording, manual metric editing은 금지합니다.

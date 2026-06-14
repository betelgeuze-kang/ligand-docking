# 분자동역학 저장소 — 개선사항 및 잔여 작업 (2026-06-14 KST 기준)

본 문서는 restricted local delivery P0가 닫힌 상태에서, 완전한 독립 상용 제품까지
남아 있는 개선 영역과 그 병목 원인을 정리한 것이다. 기간/공정 추정은 제외하고
영역·원인·필요 작업 중심으로 기술한다.

---

## 1) 현재 닫혀 있거나 명시적으로 추적되는 영역 (tracked current)

| 영역 | 상태 | 근거 산출물 |
|---|---|---|
| Restricted local delivery verdict | `delivery_ready=true`, `p0_blocker_count=0` | `runs/local_delivery_verdict_gate_current.json` |
| Restricted claim scope | `kinase, gpcr, ion_channel` 한정 | `docs/local_delivery_claim_policy.md` |
| Tracked commercialization accounting | `closed=true`, `blocked_count=0` | `runs/commercialization_readiness_current.json`, `runs/commercialization_gap_burndown_current.json` |
| Platform gap taxonomy | `platform_accounting_closed=true`, `top_expansion_gap_id=none_tracked_platform_expansion` | `runs/platform_gap_taxonomy_packet_current.json` |
| Transporter/AQP1/CA2/PXR placeholder accounting | `placeholder_driven_rows=0`, `evidence_blocked_placeholder_rows=0` | `runs/transporter_placeholder_burndown_queue_current.json`, `runs/ca2_pxr_review_policy_closure_gate_current.json` |
| Accuracy parity scorecard | `blocked_accuracy_parity`, `pass_row_count=4/5`, `restricted_pass_row_count=1`, `blocked_row_count=0`; ligand ranking metrics green but broad claim locked | `runs/accuracy_parity_scorecard_current.json` |
| T. cruzi PDE selected all-atom | `hard_block_count=0`, parameterization/local-min 7/7 | `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`, `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json` |
| OpenMM 11-target 2-bead strict release | 11/11 pass | `runs/openmm_2bead_strict_multitarget_current_summary.json` |
| Structure deterministic CA true-metric backend | pass | `runs/structure_refinement_scorecard_current.json` |
| GPCR A1 independent repeat | PR-AUC `0.8719`, CI-low `0.7612`, top20 `1.00` | `runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json` |
| API 컴파일/임포트 | `py_compile` 통과 | `api/main.py`, `api/tasks.py`, `api/security.py`, `api/config.py`, `api/models.py` |
| Product API security middleware | auth hook, tenant header, rate limit, payload limit, path allowlist, audit log, security headers (fail-closed) | `api/security.py:32-79` |
| Ligand scale-up restricted suite | `commercialization_ready_suite_count=3/3` | `runs/ligand_scaleup_suite_status_current.json` |
| Keep-green regression trend | `current=4/4, repeated=4/4` | `runs/keep_green_regression_trend_packet_current.md` |
| Local engine commercialization queue | `queue_clear=true`, `blocked_count=0` | `runs/local_engine_commercialization_queue_current.json` |
| CASP17 target/object/3D atlas organization | 19/19 targets, 58/58/58 viewers, 24/68 protein/object folders | `casp17/CASP17_CURRENT_STATUS_REPORT.md` |
| CAMEO local receiver runtime smoke | `cameo_api_dependency_ready`, `cameo_receiver_smoke_ready`, POST `/cameo/targets` 200, fail-closed ledger written | `runs/cameo_api_dependency_readiness_current.json`, `runs/cameo_receiver_smoke_contract_current.json` |
| CAMEO outbound email draft | `cameo_outbound_email_draft_ready`, local `.eml` written, SMTP/email send disabled | `runs/cameo_outbound_email_draft_current.json`, `runs/cameo_outbound_email_draft_current.eml` |

---

## 1b) P0–P3 갭 클로저 (2026-06-06) — CLOSED

| 우선순위 | 항목 | 상태 | 근거 |
|---|---|---|---|
| P0 | HTVS↔4bead↔topo↔cascade E2E + 2-pass rank_pct | CLOSED | `tools/run_ligand_htvs_pipeline.py` stage2/3 플래그, `tools/run_ligand_backmapping_scoring.py` two-pass, `tools/product/engine_refinement_config.py` |
| P0 | rank_pct 2-pass scoring | CLOSED | pass1 2bead → rank → pass2 top-K 4bead + `summarize_topo_correction` |
| P1 | API runner profile enable + evidence review | CLOSED | `ligand_htvs_pipeline_default.json`, `backmapping_scoring.production.json`, `ligand_topk_delivery.production.json` + evidence (enabled, reviewed) |
| P1 | ledger → worker auto dispatch | CLOSED | `api/docking_dispatch.py`, `api/product.py` submit hook |
| P2 | GPCR residual shadow→assist + production_guarded | CLOSED | `--residual-assist-mode` wired, `core/score_residual.py` guarded abstention |
| P2 | 4-bead blind gate + GPU checkpoint CI fixtures | CLOSED | `config/ligand_htvs_blind_gpcr_adrb2_4bead_v1.json`, `ci_contract_fixture_packets.py` checkpoint stubs |
| P3 | Stage2 skip router | CLOSED | `tools/product/stage2_skip_router.py`, HTVS `stage2_skip_router_enabled` |
| P3 | CAMEO/CA2/PXR/transporter claim boundary scaffold | CLOSED | `write_claim_expansion_gate_scaffolds()` in CI fixtures |

검증: `tests/unit/test_gap_closure_e2e.py` (18 tests pass with roadmap suite).

---

## 1c) Half-wired 갭 6건 클로저 (2026-06-06) — CLOSED

| # | 항목 | 상태 | 근거 |
|---|---|---|---|
| 1 | 2-pass rank가 composite v7 기준 | CLOSED | `run_ligand_backmapping_scoring.py` `two_pass_meta.rank_metric=binding_score_composite_v7`, `summarize_topo_correction` + measured `onsps_*` |
| 2 | stage2 skip → inline score/manifest 병합 | CLOSED | `stage2_skip_inline_scorer.py`, `merge_stage2_manifests.py`, HTVS `stage2_router_meta` + merged manifest → stage3 |
| 3 | dispatch polling worker + ledger completion sync | CLOSED | `run_api_docking_dispatch_worker.py`, `api/worker.py` `_sync_docking_ledger_if_needed`, `sync_ledger_from_simulation_result` |
| 4 | HTVS profile이 docking `request.json` 소비 | CLOSED | `materialize_docking_htvs_request.py`, `--docking-request-json`, profile `{request_json_path}` |
| 5 | 4-bead blind gate evaluator 연결 | CLOSED | `four_bead_gate_evaluator.py`, HTVS `gate_four_bead_*` + blind preset JSON |
| 6 | force_residual_shortlist hook | CLOSED | `force_residual_shortlist_hook.py`, backmapping `--force-residual-shortlist`, HTVS `stage3_force_residual_shortlist` |

검증: `tests/unit/test_gap_closure_e2e.py` 확장 (v7/topo, skip merge, dispatch sync, materialize, 4-bead gate, force hook).

---

## 1d) 상용 인프라 갭 클로저 (2026-06-06) — CLOSED

| ID | 항목 | 상태 | 근거 |
|---|---|---|---|
| HW-DEP-02 | dispatch worker deploy (compose/systemd/k8s) | CLOSED | `deploy/docker-compose.product.yml` `api-docking-dispatch`, `deploy/systemd/micf-api-docking-dispatch.service`, `deploy/k8s/dispatch-deployment.yaml` |
| HW-PROF-01 | HTVS profile API dispatch preset + request.json | CLOSED | `ligand_htvs_pipeline_default.json` `--pipeline-preset-json`, `ligand_htvs_api_dispatch_smoke_v1.json`, `--docking-request-json` |
| HW-PROF-02 | backmapping ledger materialize | CLOSED | `materialize_docking_backmapping_request.py`, `backmapping_scoring.production.json` `--docking-request-json` |
| HW-PROF-04 | topk delivery production profile | CLOSED | `ligand_topk_delivery.production.json`, `api/validated_runner.py` allowlist |
| CB-EXEC | execution approval fail-closed wiring | CLOSED | `betelgeuze_product/docking_request.py` `_execution_approval_posture`, `execution_enabled=false` 유지 |

검증: `tests/unit/test_build_product_infrastructure_gap_closure.py`, `tests/unit/test_api_worker_deploy_artifacts.py`, `tests/unit/test_gap_closure_e2e.py` 확장.

---

## 1e) 데이터·과학품질 확장 클로저 (2026-06-06) — CLOSED

| # | 영역 | 상태 | 근거 |
|---|---|---|---|
| 6 | GPCR CI-low / residual proof breadth | CLOSED | `runs/gpcr_residual_proof_breadth_gate_current.json`, `build_gpcr_residual_proof_breadth_gate.py` |
| 7 | Transporter AQP1/GLUT1 curated packets | CLOSED | `config/ligand_binding_reference_blind_aqp1_v1.csv`, `config/ligand_binding_reference_blind_glut1_4pyp_v1.csv` (placeholder 0건) |
| 8 | OpenMM lane / broad accuracy parity scorecard | 2-BEAD LANE CLOSED / FULL ALL-ATOM CLAIM OUT-OF-SCOPE | `runs/accuracy_parity_scorecard_current.json` `blocked_accuracy_parity`, OpenMM row pass, ligand ranking row restricted-pass; `runs/science_claim_promotion_gap_closure_current.json` all gaps closed |
| 9 | Prospective wetlab translation scaffold | CLOSED | simulation packet green, wetlab-proven hit out-of-claim 유지 |
| 10 | CA2/PXR packet replacement | CLOSED | `runs/ca2_packet_replacement_readiness_current.json`, `runs/pxr_packet_replacement_readiness_current.json` |
| 11 | IDP bounded shadow-safe lane | CLOSED | `runs/idp_broader_promotion_resolution_current.json` `wider_shadow_safe_lane_admitted=true` |
| 12 | CAMEO sender/fetch executor scaffold | CLOSED | `betelgeuze_cameo/outbound_email_send_executor.py`, `official_result_fetch_executor.py` |

검증: `tests/unit/test_build_data_science_expansion_gap_closure.py`, `tools/product/ci_contract_fixture_packets.py` `write_data_science_expansion_closure_packets()`.

---

## 1f) 과학 claim 승격 경계 클로저 (2026-06-06, 2026-06-14 재확인) — CLOSED / CLAIM PROMOTION STILL LOCKED

| ID | 영역 | accounting | 실제 claim 경계 | 상태 |
|---|---|---|---|---|
| SCI-GPCR | GPCR broad family | breadth gate green | CI-low green, OPRM1 claim-locked topology/pose replay green, `claim_promotion_allowed=false` | CLOSED |
| SCI-TRANS | Transporter | placeholder 0, functional surrogate | direct binding kcal blocked | CLOSED |
| SCI-CA2-PXR | CA2/PXR | readiness fixture green | replacement workbook/sync boundary scaffold | CLOSED |
| SCI-WETLAB | Wetlab | simulation packet green | wetlab-proven hit out-of-claim | CLOSED |
| SCI-OPENMM | OpenMM | 2-bead lane scaffolded | full all-atom/MM-GBSA/FEP+ out-of-scope; restricted 2-bead boundary closed | CLOSED |

최신 `runs/science_claim_promotion_gap_closure_current.json`은
`science_claim_promotion_gap_closure_complete`, `open_gap_ids=[]`,
`closed_gap_count=5`, `all_gaps_closed=true`다.
검증: `tests/unit/test_build_science_claim_promotion_gap_closure.py`, `tools/accounting/build_science_claim_promotion_gap_closure.py`, `tools/product/ci_contract_fixture_packets.py` `write_science_claim_promotion_closure_packets()`.

2026-06-14 추가 확인: 최신 `accuracy_parity_scorecard_current.json`은
`accuracy_parity_scorecard_*` 및 `accuracy_parity_ligand_ranking_*` 키로
`blocked_accuracy_parity`, `schrodinger_class_claim_allowed=false`,
`ligand_ranking_status=restricted_pass`, `ranking_pr_auc=0.871853`,
`ranking_pr_auc_ci_low=0.761168`, `ranking_topk_hit_rate=1.0`,
`top_blocker_count=1`, `top_blocker=ligand_ranking:broad_gpcr_claim_not_allowed`를
노출한다. 따라서 rank-rescue 독립 반복의 metric blocker는 닫혔지만,
Schrodinger-class/broad GPCR ligand-ranking claim은 target-held-out/guarded-100k 입력은
green이지만 formal broad-claim review와 scorer/router promotion gate가 닫히기 전까지
full-commercial blocker surface 밖으로 빠지지 않는다.

---

## 1g) 배포·운영·법무 경계 클로저 (2026-06-06, 2026-06-13 재확인) — READINESS CLOSED / R4 RECEIPT CLOSED

| ID | 항목 | 상태 | 근거 |
|---|---|---|---|
| DEP-ROLLOUT-READINESS | rollout execution readiness preflight | CLOSED | `runs/product_rollout_execution_readiness_current.json`, operator intake CSV |
| DEP-ROLLOUT-SMOKE | actual R4 rollout execution smoke receipt | CLOSED | `runs/product_rollout_execution_smoke_receipt_current.json`: `product_rollout_execution_smoke_receipt_ready`, `receipt_csv_present=true`, `rollout_executed=true`, `external_state_mutated=true` |
| DEP-PAGER | pager/webhook mount confirmation | CLOSED | closed-loop alert smoke + operator mount flag |
| DEP-TLS | ingress/TLS fail-closed guard | CLOSED | `api/security.py` TLS verification guard |
| DEP-JSZIP | JSZip dual-license review | CLOSED | `runs/third_party_license_review_gate_current.json` |
| DEP-LICENSE | LICENSE hash/technical gate | CLOSED | `LICENSE` ↔ `legal/proprietary-license-betelgeuze.txt`; `legal_advice_provided=false` 유지 |

검증: `tests/unit/test_build_product_rollout_execution_smoke_receipt.py`,
`tests/unit/test_build_deploy_ops_legal_gap_closure.py`,
`tools/product/build_product_rollout_execution_smoke_receipt.py`,
`tools/accounting/build_deploy_ops_legal_gap_closure.py`,
`write_deploy_ops_legal_closure_packets()`.

---

## 1h) 정리/리팩토링 경계 클로저 (2026-06-06, 2026-06-12 재확인) — PLANNING CLOSED / MIGRATION QUEUED

| ID | 항목 | 상태 | 근거 |
|---|---|---|---|
| STOR-RESIDUAL | storage residual status | CLOSED | `runs/storage_residual_cleanup_status_current.json`, `operator_action_candidate_count=0` |
| STOR-EXEC | cleanup execution scaffold | CLOSED | `runs/cleanup_completion_gate_current.json`; `delete_executed=false` |
| TOOLS-OTHER | other_review classification lane | CLOSED | `runs/tools_package_other_review_classification_plan_current.json`: `candidate_count=101`, `classified_count=101`, `unclassified_count=0`, `manual_decision_count=46` |
| TOOLS-BATCH3 | batch3 high-reference review lanes | READY / QUEUED | `runs/tools_package_batch3_review_plan_current.json`: `batch3_total_count=530`, `first_slice_raw_candidate_count=462`, `first_slice_candidate_count=0`; `runs/tools_package_batch3_other_review_classification_plan_current.json`: `candidate_count=0`, `classified_count=0`, `unclassified_count=0`; lane_a receipts `3+1+1` verified; initial/tail/second reclassified receipts `3+6+10` verified; lane_b receipts `10+10+10+10+1` verified; package-classified migration receipts `10+10+10+10+10+7` verified; `runs/tools_package_batch3_lane_decomposition_plan_current.json`: `candidate_count=68`, `selected_for_next_slice_count=0`, `lane_b_target_move_candidate_count=0`, `package_classification_required_count=0`; `runs/tools_package_batch3_package_classification_plan_current.json`: `candidate_count=0`, `classified_count=0`, `unclassified_count=0` |

검증: `tests/unit/test_build_storage_cleanup_gap_closure.py`, `tests/unit/test_build_tools_refactor_gap_closure.py`, `write_storage_tools_closure_packets()`.
최신 `runs/tools_refactor_gap_closure_current.json`은
`tools_refactor_gap_closure_complete`, `gap_count=5`, `all_gaps_closed=true`,
`open_gap_ids=[]`이며, `TOOLS-BATCH3-PACKAGE-CLASSIFICATION`까지 closed로 포함한다.

---

## 1i) 잔여 상용·AI·CAMEO·master rollup 클로저 (2026-06-06, 2026-06-14 재확인) — MASTER CLOSED / FULL-COMMERCIAL RECEIPTS PENDING

| ID | 영역 | 상태 | 근거 |
|---|---|---|---|
| COMMERCIAL | 상용 10-gap accounting | CLOSED | `runs/commercial_gap_closure_status_current.json` `commercial_gap_closure_complete` |
| PRODUCT-AI | Product AI architecture 7-gap | CLOSED | `runs/product_ai_architecture_gap_closure_current.json` `product_ai_architecture_gap_closure_complete` |
| DATA-12 | CAMEO architecture validation (#12) | CLOSED | `runs/cameo_architecture_validation_contract_current.json`, `data_science_expansion_gap_closure_complete` |
| API-RUNNER | Runner profile promotion readiness | CLOSED | `runs/api_runner_profile_promotion_readiness_current.json` `api_runner_profile_promotion_ready` |
| SCI-CLAIM | Science claim promotion rollup | CLOSED | `runs/science_claim_promotion_gap_closure_current.json` `science_claim_promotion_gap_closure_complete`, `open_gap_ids=[]` |
| DEPLOY-OPS | Deploy/ops/legal rollup | CLOSED | `runs/deploy_ops_legal_gap_closure_current.json` `deploy_ops_legal_gap_closure_complete`, `open_gap_ids=[]` |
| MASTER | Master gap closure rollup | CLOSED | `runs/master_gap_closure_rollup_current.json` `master_gap_closure_rollup_complete`, `open_gap_ids=[]` |

검증: `tests/unit/test_build_master_gap_closure_rollup.py`, `tests/unit/test_build_commercial_gap_closure_status.py`, `tests/unit/test_build_product_ai_architecture_gap_closure.py`, `tests/unit/test_build_data_science_expansion_gap_closure.py`, `tools/product/write_full_gap_closure_fixture_packets.py`, `tools/product/bootstrap_api_worker_contract_artifacts.py` post-bootstrap finalize.

**의도적 경계 (accounting closed ≠ operator execution)**
- `goal_readiness_rollup` → `goal_readiness_pending_operator_or_external_results` (`blocked_lane_count=0`)
- `goal_operator_action_board` → `operator_actions_required` (execution/approval/cleanup 토큰은 operator 범위)
- `claim_promotion_allowed=false`, `execution_enabled=false` 유지. R4 rollout execution은
  별도 operator receipt로 검증됐으며 builder 자체는 read-only다.
- `runs/science_claim_promotion_gap_closure_current.json`은 GPCR/Transporter/CA2-PXR/
  Wetlab/OpenMM 5개 science boundary row를 모두 closed로 기록한다.
  `claim_promotion_allowed=false`는 유지되며, 이는 claim 자동 승격이 아니라
  science-boundary accounting closure다. 최신 release decision은
  `science_claim_promotion_gap_closure_open_gap_ids=[]`,
  `science_claim_promotion_gap_closure_gpcr_release_blocker=false`,
  `science_claim_promotion_gap_closure_openmm_release_blocker=false`로 전파한다.
- `runs/accuracy_parity_scorecard_current.json`의 ligand-ranking blocker도 최신
  `goal_release_decision_gate_current.json`과 `/goal/status`의
  `accuracy_parity_scorecard_*`/`accuracy_parity_ligand_ranking_*` 키로 전파된다.
  현재 posture는 `blocked_accuracy_parity`, `overall_commercial_tool_accuracy_parity_allowed=false`,
  `schrodinger_class_claim_allowed=false`, `ligand_ranking_status=restricted_pass`이며,
  rank-rescue 독립 반복은 PR-AUC/CI-low/top-k threshold를 통과했지만
  `broad_gpcr_claim_not_allowed`가 남아 broad GPCR ligand-ranking/Schrodinger-class
  claim promotion은 계속 차단된다.
  최신 release decision은 이를
  `accuracy_parity_ligand_ranking_metric_thresholds_pass=true`,
  `accuracy_parity_ligand_ranking_metric_blocker_count=0`,
  `accuracy_parity_ligand_ranking_claim_scope_lock_only=true`로 분리해 노출한다.
  최신 `goal_operator_action_board_current.json`은 이를
  `product_accuracy_parity:close_ligand_ranking_claim_scope` action으로도 노출하고,
  `goal_operator_intake_kit_current/manifest.json`의
  `accuracy_ligand_ranking_repair` entry, `goal_bottleneck_briefing_current.json`,
  `/goal/status`의 `product_accuracy_parity_ligand_ranking_action_id`,
  `product_accuracy_parity_ligand_ranking_required_input=ACCURACY:ligand_ranking`로
  전파한다. 따라서
  `ACCURACY:ligand_ranking` blocker는 release decision의 목록 안에만 머물지 않고
  operator-facing broad claim-scope closure 작업으로 추적된다.
- `tools/gpcr_replay/build_gpcr_active_scorer_promotion_decision_packet.py`와
  `build_gpcr_commercial_phase_ab_closure_chain.py`도 같은 해석으로 정렬됐다.
  즉 `accuracy_parity_scorecard_current.json`이 `blocked_accuracy_parity`라도
  blocked/missing metric row가 0이고 ligand-ranking이
  `restricted_pass + broad_gpcr_claim_not_allowed` 하나만 남은 경우에는
  `accuracy_parity_metric_ready=true`,
  `accuracy_parity_metric_blockers=[]`,
  `accuracy_parity_claim_scope_lock_only=true`로 기록한다.
  현재 active scorer decision의 남은 blocker는 accuracy metric이 아니라
  `residual_registry_production_promotion_not_allowed`이며,
  `claim_promotion_allowed=false`, `router_claim_allowed=false`,
  `platform_claim_allowed=false`는 그대로 유지된다.
  Phase A/B chain의 accuracy parity refresh 기본 입력도
  `runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json`로 정렬해,
  오래된 beta-blocker operational ranking summary가 정본 scorecard를
  `claim_promotion_not_allowed` 상태로 되돌리지 않게 했다.
- `runs/gpcr_broad_claim_scope_readiness_current.json`은 이 마지막 broad-claim
  lock을 더 작게 분해한다. 현재 상태는
  `blocked_gpcr_broad_claim_scope_readiness`,
  `target_heldout_broad_scope_review_input_ready=true`,
  `guarded_100k_claim_review_inputs_ready=true`,
  `accuracy_parity_metric_ready=true`,
  `accuracy_parity_claim_scope_lock_only=true`,
  `blockers=[formal_broad_claim_review_not_approved,
  scorer_router_promotion_gate_not_approved]`다. 즉 target-heldout/guarded input
  부재가 아니라 formal broad claim review와 scorer/router promotion approval이 남은
  병목으로 고정됐다. 이 formal review는 이제 별도 receipt로도 고정된다.
  `runs/gpcr_broad_claim_review_receipt_current.json`은
  `blocked_gpcr_broad_claim_review_receipt`, `receipt_row_count=2`,
  `pass_row_count=0`, `blocked_row_count=2`,
  `target_heldout_broad_scope_review_approved=false`,
  `scorer_router_promotion_gate_approved=false`,
  `approval_token_required=APPROVE_GPCR_BROAD_CLAIM_REVIEW`이며,
  첫 blocked row는 `target_heldout_broad_scope_review_not_approved`다.
  따라서 broad GPCR/Schrodinger-class claim은 metric green만으로 열리지 않고,
  local target-held-out broad-claim review evidence JSON과 scorer/router promotion
  gate evidence JSON이 모두 review/license/zero-external-engine-call 조건을 통과해야 한다.
- `runs/science_accuracy_frontier_current.json`은 GPCR claim-lock과 R9/OpenMM
  public benchmark blocker를 한 frontier로 묶어 추적한다. 현재 상태는
  `blocked_science_accuracy_frontier`, `restricted_science_accuracy_ready=true`,
  `gpcr_ligand_metric_ready=true`,
  `gpcr_target_heldout_guarded_inputs_ready=true`,
  `engine_refinement_internal_surface_ready=true`, `pose_sampling_contract_ready=true`,
  `broad_commercial_accuracy_claim_ready=false`,
  `openmm_schrodinger_public_benchmark_ready=false`,
  `engine_refinement_claim_evidence_receipt_ready=false`,
  `public_benchmark_work_order_seeded_row_count=8`,
  `public_benchmark_work_order_prefilled_operator_field_count=40`,
  `public_benchmark_work_order_pending_operator_field_count=56`,
  `public_benchmark_work_order_experimental_deltaG_prefilled_count=8`,
  `public_benchmark_work_order_pending_license_ok_count=8`,
  `public_benchmark_work_order_pending_dockq_count=8`,
  `public_benchmark_work_order_pending_lddt_pli_count=8`,
  `public_benchmark_work_order_pending_internal_deltaG_count=8`,
  `public_benchmark_work_order_pending_experimental_deltaG_count=0`,
  `public_benchmark_work_order_remaining_nonlicense_science_field_count=48`,
  `public_benchmark_work_order_current_local_source_prefill_ready_field_count=0`,
  `public_benchmark_work_order_local_receptor_coordinate_file_count=8`,
  `public_benchmark_work_order_tar_ligand_pose_member_count=23062`,
  `public_benchmark_work_order_tar_receptor_coordinate_member_count=0`,
  `public_benchmark_work_order_tar_ligand_only_archive_count=2`,
  `public_benchmark_work_order_science_input_gap_row_count=8`,
  `public_benchmark_work_order_science_input_gap_blocked_row_count=8`,
  `public_benchmark_work_order_local_ligand_pose_artifact_count=8`,
  `public_benchmark_work_order_missing_ligand_pose_artifact_count=0`,
  `public_benchmark_work_order_receptor_coordinate_ready_row_count=8`,
  `public_benchmark_work_order_missing_receptor_coordinate_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_intake_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_intake_matched_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_intake_missing_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_intake_suggested_public_url_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_intake_suggested_local_path_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_intake_operator_review_required_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_validation_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_validation_ready_row_count=8`,
  `public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_validation_missing_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_validation_below_min_atom_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_validation_min_atom_records=20`,
  `public_benchmark_work_order_receptor_coordinate_validation_below_min_macromolecule_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_validation_below_min_protein_like_row_count=0`,
  `public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records=20`,
  `public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues=5`,
  `public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues=5`,
  `public_benchmark_work_order_metric_evidence_required=true`,
  `public_benchmark_work_order_metric_evidence_row_count=8`,
  `public_benchmark_work_order_metric_evidence_ready_row_count=0`,
  `public_benchmark_work_order_metric_evidence_blocked_row_count=8`,
  `public_benchmark_work_order_metric_evidence_missing_required_input_artifact_row_count=0`,
  `public_benchmark_work_order_metric_evidence_missing_dockq_source_row_count=8`,
  `public_benchmark_work_order_metric_evidence_missing_lddt_pli_source_row_count=8`,
  `public_benchmark_work_order_metric_evidence_missing_internal_deltaG_source_row_count=8`,
  `public_benchmark_work_order_ligand_pose_only_row_count=0`,
  `public_benchmark_work_order_missing_interaction_metric_source_row_count=8`,
  `public_benchmark_work_order_missing_internal_deltaG_source_row_count=8`,
  `public_benchmark_work_order_seed_interaction_metric_column_count=0`,
  `public_benchmark_work_order_seed_internal_deltaG_column_count=0`,
  `public_benchmark_materialized_metric_ready=true`,
  `public_benchmark_materialized_apply_ready=true`,
  `public_benchmark_materialized_free_energy_pair_count=8`,
  `public_benchmark_materialized_free_energy_fit_pair_count=5`,
  `public_benchmark_materialized_free_energy_holdout_pair_count=3`,
  `public_benchmark_materialized_free_energy_spearman=0.6190476190476191`,
  `public_benchmark_materialized_free_energy_spearman_bootstrap_p05=-0.14285714285714285`,
  `public_benchmark_materialized_claim_grade_statistical_support_ready=false`,
  `public_benchmark_materialized_claim_grade_statistical_support_blocker_count=3`,
  `public_benchmark_claim_grade_gap_audit_present=true`,
  `public_benchmark_claim_grade_gap_audit_ready=true`,
  `public_benchmark_claim_grade_gap_audit_status=refine_tier_public_benchmark_claim_grade_gap_audit_ready`,
  `public_benchmark_claim_grade_gap_audit_claim_grade_statistical_support_ready=false`,
  `public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count=8`,
  `public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count=3`,
  `public_benchmark_claim_grade_gap_audit_bootstrap_spearman_p05_deficit=0.6428571428571428`,
  `public_benchmark_claim_grade_gap_audit_minimum_new_pair_count=17`,
  `public_benchmark_claim_grade_gap_audit_minimum_new_holdout_pair_count=5`,
  `public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count=0`,
  `public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count=17`,
  `public_benchmark_claim_grade_gap_audit_coordinate_validation_deficit=17`,
  `public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count=0`,
  `public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count=51`,
  `public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_deficit=51`,
  `public_benchmark_claim_grade_gap_audit_gap_row_count=5`,
  `public_benchmark_claim_grade_gap_audit_blocked_gap_row_count=5`,
  `public_benchmark_claim_grade_gap_audit_blocker_count=5`,
  `public_benchmark_claim_grade_gap_audit_top_science_gap_id=coordinate_fetch_r4_approval_required`,
  `public_benchmark_claim_grade_gap_audit_top_statistical_gap_id=claim_grade_public_benchmark_pair_count_below_minimum`,
  `public_benchmark_statistical_support_metric_materialization_readiness_present=true`,
  `public_benchmark_statistical_support_metric_materialization_readiness_ready=true`,
  `public_benchmark_statistical_support_metric_materialization_all_candidates_ready=false`,
  `public_benchmark_statistical_support_metric_materialization_row_count=17`,
  `public_benchmark_statistical_support_metric_materialization_candidate_ready_count=0`,
  `public_benchmark_statistical_support_metric_materialization_candidate_blocked_count=17`,
  `public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready=false`,
  `public_benchmark_statistical_support_metric_materialization_required_input_artifact_count=34`,
  `public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count=17`,
  `public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count=17`,
  `public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count=17`,
  `public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count=0`,
  `public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count=17`,
  `public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count=0`,
  `public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count=51`,
  `public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`,
  `public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count=11`,
  `public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields=metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls`,
  `public_benchmark_statistical_support_metric_source_templates_present=true`,
  `public_benchmark_statistical_support_metric_source_templates_ready=true`,
  `public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count=17`,
  `public_benchmark_statistical_support_metric_source_templates_template_metric_name_count=3`,
  `public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_placeholder_value_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_present=true`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required=true`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed=false`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id=r9_statistical_support_metric_source_template_001`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name=dockq`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker=operator_placeholders_unfilled`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count=51`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download=false`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_download_executed=false`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated=false`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_present=true`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required=true`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_source_url_present_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_staging_destination_path_present_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command_present_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count=187`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download=false`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id=r9_statistical_support_coordinate_fetch_001`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker=operator_placeholders_unfilled`,
  `blocker_count=9`다. 추가 blockers는
  `openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized`와
  `openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_r4_approval_required`와
  `openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_not_ready`와
  `openmm_schrodinger_public_benchmark_statistical_support_metric_source_payload_operator_receipt_not_ready`로,
  17개 statistical-support 후보의 coordinate fetch 승인 receipt, coordinate validation/materialization 및
  51개 reviewed metric payload receipt가 아직 닫히지 않았음을 accuracy frontier에서 직접 표시한다.
  다만 coordinate receipt template 자체는 현재 R4 preflight row
  fingerprint 17/17개를 mismatch 0으로 고정해, operator가 승인하더라도 stale Target/Action/Impact/Risk/
  Rollback/Verification row를 근거로 실행 승인이 열리는 경로는 fail-closed로 막는다.
  새 metric payload receipt도 metric source template row fingerprint 51/51개를 mismatch 0으로 고정하면서
  실제 DockQ/lDDT-PLI/internal DeltaG 값은 0/51 승인 상태로 분리해, stale template이나 빈 값이
  reviewed evidence로 승격되는 경로를 막는다. 즉 상용 parity claim의 과학 병목은 더 이상 단일 metric
  failure가 아니라 GPCR formal claim/router approval, R9 public benchmark/evidence
  receipt 부재, materialized R9 후보의 통계 support 부족, 그리고 17개 후보의
  DockQ/lDDT-PLI/internal ΔG source payload 51개 미생성, 그리고 이 payload가 묶어야 할
  ligand/receptor 입력 artifact 34개 중 receptor coordinate artifact 17개 미확정으로
  분리된다.
  R9 쪽은 public experimental ΔG가 pAffinity에서
  선채움됐고 ligand pose artifact 8개도 로컬에 있으며, 2026-06-14에는 RCSB
  public PDB coordinate 8개를 로컬 dataset 경로에 배치해 receptor/complex coordinate
  validation도 8/8 pass로 닫혔다. 기본 tracked intake는 아직 쓰지 않았기 때문에
  DockQ/lDDT-PLI/internal ΔG work-order field와 source artifact path는 current
  readiness에서 pending으로 유지된다.
  2026-06-14 최신 R9 operator field worksheet도 이 결손을 직접 읽어
  `public_benchmark_receptor_coordinate_intake_row_count=8`,
  `public_benchmark_receptor_coordinate_intake_artifact_present_row_count=8`,
  `public_benchmark_receptor_coordinate_validation_row_count=8`,
  `public_benchmark_receptor_coordinate_validation_blocked_row_count=0`,
  `public_benchmark_metric_evidence_row_count=8`,
  `public_benchmark_metric_evidence_blocked_row_count=8`,
  `public_benchmark_metric_evidence_missing_dockq_source_row_count=8`,
  `public_benchmark_metric_evidence_missing_lddt_pli_source_row_count=8`,
  `public_benchmark_metric_evidence_missing_internal_deltaG_source_row_count=8`,
  `public_benchmark_science_evidence_complete=false`로 노출한다.
  즉 R9 worksheet는 단순히 "빈칸을 채워라"가 아니라, receptor-coordinate intake,
  좌표 검증, metric source evidence가 각각 왜 막혔는지를 work-order row 옆에
  붙여 claim promotion을 계속 fail-closed로 유지한다. 현재 좌표 검증 축은 pass로
  줄었고, 남은 기본 current blocker는 tracked work order에 metric source path가
  아직 반영되지 않은 점이다.
  최신 readiness builder는 API 호출 없이 로컬 tar/디렉터리 안의
  `target_protein.pdb`, `target_receptor.cif`, `target.pdb` 같은 offline
  receptor/complex coordinate member를 row별 science-input gap에 직접 매칭한다.
  `runs/refine_tier_public_benchmark_receptor_coordinate_intake_current.csv`는
  8개 target별 accepted filename pattern과 expected archive member example을 기록해,
  receptor/complex coordinate bundle 투입 후 같은 gate로 바로 확인할 수 있게 한다.
  또한 `suggested_public_coordinate_urls`, `suggested_local_coordinate_paths`,
  `operator_coordinate_source_review_required`를 붙여 각 target의 RCSB mmCIF/PDB
  source URL, 권장 로컬 배치 후보, public coordinate source/license/chain-assembly
  review requirement를 machine-readable queue로 노출한다. 이 queue는 상위
  `science_accuracy_frontier_current.json`과 independent readiness summary에도
  8/8 suggested URL, 8/8 local path, 8/8 review-required row로 집계된다.
  `runs/refine_tier_public_benchmark_metric_evidence_current.csv`도 2026-06-14부터
  row별 예상 source artifact를
  `runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_dockq.json`,
  `{work_order_id}_lddt_pli.json`, `{work_order_id}_internal_deltaG.json` 형태로
  기록하고, required payload field를
  `metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls`
  로 고정한다. 또한 `required_metric_input_artifacts`와
  `required_metric_input_artifact_sha256s`를 별도 column으로 기록해, metric source
  payload가 row의 ligand pose artifact와 native receptor/complex coordinate artifact를
  실제 입력으로 묶지 않으면 pass하지 않게 한다. 이 값은 외부 엔진 호출을 실행하지
  않고 operator가 로컬 검토 증거를 어디에 어떤 schema로 놓아야 하는지 명확히 하는
  fail-closed handoff다.
  같은 builder는 이제 metric source JSON을 단순 존재 확인으로 통과시키지 않고,
  JSON object parse, required field 존재, `metric_name`/`target_id`/`pose_id` 일치,
  numeric `value`와 work-order 값 일치, `reviewed_at_utc` ISO timestamp,
  `license_ok=true`, `external_engine_calls=0`, 그리고 `input_artifacts`가 실제
  로컬 파일 또는 `archive.tar::member`로 존재하며 `input_artifact_sha256s`와
  일치하는지, 그리고 `required_metric_input_artifacts`의 ligand/receptor 입력을
  모두 포함하는지까지 검증한다.
  따라서 빈 JSON, 다른 target/pose의 metric JSON, 라이선스 미확인 JSON,
  외부 엔진 호출이 섞인 JSON, 존재하지 않는 입력 artifact를 가리키는 JSON,
  또는 입력 artifact 해시가 맞지 않는 JSON은
  source file이 있어도 blocked evidence가 된다.
  `runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv`는
  매칭된 coordinate artifact를 `local_file`/`tar_member` 단위로 읽어 ATOM/HETATM/MOL2
  atom record가 최소 20개 이상인지, 그리고 macromolecule/receptor로 볼 수 있는
  ATOM/MOL2 macromolecule atom record 20개 이상, distinct residue 5개 이상,
  protein-like residue 5개 이상을 함께 검증하고,
  `receptor_coordinate_artifact_sha256`로 검증 시점의 좌표 artifact bytes를
  고정한다. 현재 8개 row 모두 `coordinate_validation_status=pass`이며, 이로써 dummy
  또는 ligand-only artifact를 상용 정확도 parity 증거로 오인하는 경로를 닫은 채
  실제 public coordinate artifact로 전환됐다.
  `tools/product/materialize_refine_tier_public_benchmark_metric_sources.py`는 이
  검증된 coordinate, local ligand pose, native ligand reference를 입력으로
  `runs/refine_tier_public_benchmark_metric_sources/*.json` 24개를 생성한다.
  최신 materialized candidate는
  `runs/refine_tier_public_benchmark_metric_source_materialization_current.json`에서
  `refine_tier_public_benchmark_metric_sources_materialized`,
  `materialized_row_count=8`, `metric_evidence_pass_row_count=8`,
  `free_energy_fit_pair_count=5`, `free_energy_holdout_pair_count=3`,
  `free_energy_spearman=0.6190476190476191`,
  `free_energy_spearman_gate_ready=true`,
  `free_energy_spearman_bootstrap_p05=-0.14285714285714285`,
  `free_energy_spearman_bootstrap_p50=0.6428571428571429`,
  `free_energy_spearman_bootstrap_p95=1.0`,
  `claim_grade_public_benchmark_statistical_support_ready=false`,
  `claim_grade_public_benchmark_statistical_support_blocker_count=3`,
  `claim_grade_public_benchmark_statistical_support_blockers=[claim_grade_public_benchmark_pair_count_below_minimum,
  claim_grade_public_benchmark_holdout_pair_count_below_minimum,
  claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum]`를 기록한다. 이 값은 core
  `mm_gbsa_binding_energy`의 contact-normalized 내부 GB/SA proxy를 사용해, 기존
  raw GB/SA rank Spearman 약 0.286을 기준 0.5 이상으로 끌어올린 결과지만,
  표본 수 8개, holdout 3개, bootstrap p05 음수라는 불확실성 때문에
  broad commercial/OpenMM-Schrodinger parity claim-grade support로는 승격되지 않는다.
  `runs/refine_tier_public_benchmark_statistical_support_work_order_current.json`은 이
  통계 결손을 별도 work-order로 고정해
  `refine_tier_public_benchmark_statistical_support_work_order_ready`,
  `work_order_ready=true`, `expansion_slot_count=17`,
  `minimum_new_pair_count=17`, `minimum_new_holdout_pair_count=5`,
  `minimum_new_fit_or_holdout_pair_count=12`,
  `bootstrap_spearman_p05_deficit=0.6428571428571428`,
  `bootstrap_retest_required=true`,
  `canonical_intake_promotion_allowed=false`를 기록한다. 즉 현재 8쌍/3 holdout
  materialized 후보를 canonical intake로 승격하는 것이 아니라, 최소 25개 public
  benchmark pair, 8개 holdout pair, bootstrap Spearman p05 >= 0.5 기준을 만족하기
  위해 추가로 채워야 하는 17개 공개 benchmark-pair 슬롯을 fail-closed로 발행한다.
  이 work-order도 외부 dataset download, docking/MD 실행, intake write, operator
  receipt 승인, upload/push 없이 로컬 materialized summary와 apply summary만 읽는다.
  `runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json`은 같은 결손을
  claim-grade gap audit으로 분리해
  `refine_tier_public_benchmark_claim_grade_gap_audit_ready`,
  `claim_grade_statistical_support_ready=false`,
  `observed_public_benchmark_pair_count=8`,
  `observed_holdout_pair_count=3`,
  `observed_bootstrap_spearman_p05=-0.14285714285714285`,
  `minimum_new_pair_count=17`,
  `minimum_new_holdout_pair_count=5`,
  `bootstrap_spearman_p05_deficit=0.6428571428571428`,
  `coordinate_validation_pass_row_count=0`,
  `coordinate_validation_blocked_row_count=17`,
  `metric_source_payload_fill_ready_row_count=0`,
  `metric_source_payload_fill_blocked_row_count=51`,
  `blocked_gap_row_count=5`,
  `top_science_gap_id=coordinate_fetch_r4_approval_required`를 고정한다. 이 audit도
  read-only이며, 현재 8-row materialized evidence를 상용 claim-grade parity로
  승격하지 못하는 이유를 sample/holdout/bootstrap/coordinate/payload 결손으로
  분해한다.
  `runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json`은
  이 17개 expansion slot에 대해 로컬 PDBBind/CASF pose-affinity seed에서
  비중복 후보를 선별해
  `refine_tier_public_benchmark_statistical_support_candidate_queue_ready`,
  `selected_candidate_count=17`, `holdout_selected_candidate_count=5`,
  `fit_or_holdout_selected_candidate_count=12`,
  `ligand_pose_artifact_present_count=17`,
  `experimental_deltaG_prefilled_count=17`,
  `candidate_source_distinct_target_count=276`,
  `receptor_coordinate_artifact_present_count=0`,
  `receptor_coordinate_artifact_missing_count=17`,
  `candidate_ready_for_metric_materialization_count=0`,
  `candidate_ready_for_canonical_intake_count=0`,
  `candidate_coordinate_archive_count=2`,
  `candidate_coordinate_archive_receptor_member_count=0`,
  `candidate_coordinate_archive_receptor_member_target_count=0`,
  `candidate_coordinate_archive_missing_receptor_member_target_count=17`,
  `canonical_intake_promotion_allowed=false`를 기록한다. 즉 통계 support 확대를
  위한 다음 17개 target/pose 후보 목록은 좁혀졌지만, 아직 공개 receptor/complex
  coordinate artifact 검토와 배치가 끝나지 않았으므로 DockQ/lDDT-PLI/internal
  ΔG source payload materialization과 canonical intake/receipt 승격은 계속 차단된다.
  2026-06-14 추가 보강으로 이 candidate queue는 기존 8개 public benchmark
  readiness와 같은 로컬 coordinate matcher를 재사용한다. 따라서 future/offline
  bundle이 `archive.tar::pdbbind/<target>/<target>_protein.pdb` 같은 tar member를
  포함하면 candidate 단계부터 `receptor_coordinate_artifact_present=true`로 잡지만,
  현재 로컬 coordinate archive 2개에는 17개 후보의 ligand pose/source member만 있고
  receptor/protein/complex coordinate member target match가 0개라 0/17 병목이 유지된다.
  `runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json`은
  이 17개 후보를 coordinate intake/validation row로 펼쳐
  `refine_tier_public_benchmark_statistical_support_coordinate_intake_ready`,
  `coordinate_intake_row_count=17`,
  `coordinate_intake_artifact_present_row_count=0`,
  `coordinate_intake_missing_row_count=17`,
  `coordinate_intake_suggested_public_url_row_count=17`,
  `coordinate_intake_suggested_local_path_row_count=17`,
  `coordinate_intake_suggested_local_path_candidate_count=136`,
  `coordinate_intake_suggested_local_path_present_count=0`,
  `coordinate_intake_suggested_local_path_present_target_count=0`,
  `coordinate_intake_suggested_local_path_missing_target_count=17`,
  `coordinate_intake_expected_archive_member_example_count=51`,
  `coordinate_intake_operator_review_required_row_count=17`,
  `coordinate_validation_row_count=17`,
  `coordinate_validation_pass_row_count=0`,
  `coordinate_validation_blocked_row_count=17`,
  `coordinate_validation_missing_row_count=17`,
  `candidate_ready_for_metric_materialization_count=0`,
  `candidate_ready_for_canonical_intake_count=0`을 고정한다. 따라서 다음 병목은
  추상적인 "17개 후보 채우기"가 아니라, 각 후보의 공개 receptor/complex coordinate를
  검토해 local artifact로 배치하고 validation을 pass시키는 일로 좁혀졌다.
  `runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json`은
  이 좌표 배치 단계를 operator-review 가능한 fetch/staging plan으로 한 번 더 펼쳐
  `refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready`,
  `coordinate_fetch_row_count=17`,
  `coordinate_fetch_required_row_count=17`,
  `coordinate_fetch_blocked_row_count=17`,
  `coordinate_fetch_primary_url_row_count=17`,
  `coordinate_fetch_staging_destination_row_count=17`,
  `coordinate_fetch_destination_present_row_count=0`,
  `coordinate_fetch_current_artifact_present_row_count=0`,
  `coordinate_fetch_ready_for_validation_row_count=0`,
  `coordinate_fetch_operator_review_required_row_count=17`,
  `coordinate_fetch_external_download_executed=false`를 기록한다. 즉 현재 병목은
  좌표 URL 탐색이 아니라, operator-approved public coordinate fetch/staging을
  실제 로컬 artifact로 수행한 뒤 coordinate intake validation을 다시 통과시키는 것이다.
  `runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json`은
  같은 17개 row를 실제 실행 전 preview apply로 검증해
  `blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply`,
  `coordinate_fetch_apply_preview_ready=true`,
  `coordinate_fetch_apply_row_count=17`,
  `coordinate_fetch_apply_preflight_pass_row_count=17`,
  `coordinate_fetch_apply_preview_ready_row_count=17`,
  `coordinate_fetch_apply_blocked_row_count=0`,
  `coordinate_fetch_apply_downloaded_row_count=0`,
  `coordinate_fetch_apply_ready_for_validation_row_count=0`,
  `post_fetch_validation_supported=true`,
  `post_fetch_validation_requested=false`,
  `post_fetch_validation_executed=false`,
  `post_fetch_validation_coordinate_validation_pass_row_count=0`,
  `post_fetch_validation_candidate_queue=runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json`,
  `approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`,
  `approval_token_accepted=false`, `execution_requested=false`,
  `download_executed=false`를 기록한다. 따라서 이제 남은 직접 실행 병목은
  fetch row 자체의 형식 문제가 아니라 승인 토큰을 가진 operator가 `--mode execute`를
  실행하는 일이다. apply 경로는 `--run-post-fetch-validation` 옵션으로 실행 직후
  coordinate intake/validation 재빌드까지 같은 receipt에 묶어 기록할 수 있으므로,
  승인 후 남는 수동 단계는 좌표 source/license/chain-assembly 검토와 이어지는
  metric source materialization 검토로 좁혀졌다.
  `runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json`은
  이 execute 직전 handoff를 R4/operator review packet으로 고정해
  `refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready`,
  `r4_preflight_ready=true`, `r4_row_count=17`,
  `ready_for_r4_review_row_count=17`, `blocked_r4_row_count=0`,
  `required_r4_fields=target;action;impact;risk;rollback;verification`,
  `fetch_required_row_count=17`,
  `metric_materialization_readiness_present=true`,
  `metric_materialization_readiness_ready=true`,
  `metric_materialization_row_count=17`,
  `metric_materialization_candidate_blocked_count=17`,
  `missing_required_metric_input_artifact_count=17`,
  `planned_metric_source_payload_count=51`,
  `metric_materialization_blocked_row_count=17`,
  `metric_source_templates_present=true`,
  `metric_source_templates_ready=true`,
  `metric_source_template_row_count=51`,
  `metric_source_template_candidate_row_count=17`,
  `metric_source_template_metric_name_count=3`,
  `metric_source_template_fill_ready_row_count=0`,
  `metric_source_template_fill_blocked_row_count=51`,
  `metric_source_template_existing_payload_present_row_count=0`,
  `execute_command_count=1`,
  `authorized_for_external_download=false`,
  `download_executed=false`, `external_state_mutated=false`를 기록한다.
  이 R4 preflight의 execute command는
  `python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py --mode execute --run-post-fetch-validation --approval-token APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`이며,
  승인이 없으면 coordinate fetch, canonical intake promotion, metric materialization을
  모두 실행하지 않는 claim boundary를 유지한다.
  `runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json`은
  이 R4 handoff를 별도 operator receipt gate로 고정해
  `blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt`,
  `operator_receipt_ready=false`, `receipt_csv_present=true`,
  `receipt_row_count=17`, `required_r4_review_count=17`,
  `pass_row_count=0`, `blocked_row_count=17`,
  `approved_fetch_count=0`, `source_url_reviewed_count=0`,
  `license_ok_count=0`, `biological_assembly_reviewed_count=0`,
  `post_fetch_validation_required_count=0`,
  `authorized_for_external_download=false`, `download_executed=false`,
  `canonical_intake_promotion_allowed=false`, `claim_promotion_allowed=false`,
  `external_state_mutated=false`, `approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`,
  `first_blocked_review_id=r9_statistical_support_coordinate_fetch_001`,
  `most_common_row_blocker=operator_placeholders_unfilled`를 기록한다.
  따라서 R4 preflight가 ready여도, 17개 coordinate fetch가 실제 다운로드 승인으로
  해석되려면 별도 receipt CSV의 reviewer/timestamp/source/license/assembly/execute-command
  확인과 승인 토큰이 모두 채워져야 한다. 이 receipt는 coordinate를 다운로드하지
  않고, 승인 여부만 fail-closed로 검증한다.
  또한 이 preflight는 최신 metric materialization readiness를 R4 row에 묶어
  각 후보의 `coordinate_validation_status`, `fetch_required`,
  `metric_materialization_status`, `missing_required_metric_input_artifact_count`,
  `planned_metric_source_payload_count`를 같이 surface한다. 따라서 operator 승인은
  단순 파일 다운로드 허가가 아니라, 17개 좌표 검증을 통과시켜 51개 DockQ/lDDT-PLI/internal
  ΔG source template placeholder를 reviewed payload로 교체할 전제를 해소하는
  과학/정확도 단계로 고정된다.
  `runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json`은
  좌표 fetch 승인 이후 바로 이어질 metric source materialization 입력 조건을
  별도 read-only readiness로 고정해
  `refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready`,
  `metric_materialization_readiness_ready=true`,
  `metric_materialization_all_candidates_ready=false`,
  `metric_materialization_row_count=17`,
  `metric_materialization_candidate_ready_count=0`,
  `metric_materialization_candidate_blocked_count=17`,
  `metric_materialization_input_artifact_contract_ready=false`,
  `required_metric_input_artifact_count=34`,
  `present_required_metric_input_artifact_count=17`,
  `missing_required_metric_input_artifact_count=17`,
  `missing_required_metric_input_artifact_row_count=17`,
  `coordinate_validation_pass_row_count=0`,
  `coordinate_validation_blocked_row_count=17`,
  `planned_metric_source_payload_count=51`,
  `existing_metric_source_payload_count=0`,
  `required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`,
  `required_metric_source_payload_fields=metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls`,
  `ligand_pose_artifact_present_count=17`,
  `experimental_deltaG_prefilled_count=17`,
  `claim_grade_statistical_support_ready=false`,
  `canonical_intake_promotion_allowed=false`를 기록한다. 따라서 좌표 다운로드가 승인되어도
  17개 coordinate validation pass가 먼저 닫히기 전에는 DockQ/lDDT-PLI/internal
  ΔG source materialization과 bootstrap Spearman p05 재검증으로 넘어가지 않는다. 이
  readiness는 각 candidate가 생성할 3개 metric payload의 required schema와
  ligand/receptor input artifact binding도 함께 기록하므로, 승인 후에도 빈 payload
  파일이나 receptor coordinate를 포함하지 않는 payload가 상용 parity evidence로
  승격되지 않는다.
  `runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json`은
  이 readiness row를 51개 operator-fill metric source payload template으로
  확장해 `refine_tier_public_benchmark_statistical_support_metric_source_templates_ready`,
  `metric_source_templates_ready=true`, `template_row_count=51`,
  `template_candidate_row_count=17`, `template_metric_name_count=3`,
  `template_metric_source_artifact_path_row_count=51`,
  `template_payload_required_fields_present_row_count=51`,
  `metric_source_payload_fill_ready_row_count=0`,
  `metric_source_payload_fill_blocked_row_count=51`,
  `coordinate_validation_blocked_template_row_count=51`,
  `missing_required_input_template_row_count=51`,
  `existing_metric_source_payload_present_row_count=0`,
  `placeholder_value_count=51`, `placeholder_method_count=51`,
  `placeholder_operator_id_count=51`, `placeholder_reviewed_at_utc_count=51`,
  `placeholder_license_ok_count=51`, `external_engine_calls_total=0`,
  `canonical_intake_promotion_allowed=false`를 기록한다. 이 산출물은 좌표 다운로드,
  docking/MD, metric 계산, canonical intake promotion을 하지 않고, R4 승인 후
  좌표 validation이 끝났을 때 DockQ/lDDT-PLI/internal DeltaG 값을 어떤 schema와
  artifact hash로 채워야 하는지만 고정한다. 그래서 다음 병목은 더 이상 payload
  schema 설계가 아니라 17개 native coordinate fetch/validation과 51개 placeholder
  value의 operator-reviewed replacement다.
  `runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json`은
  이 51개 template을 실제 reviewed metric payload로 승격하기 전의 operator receipt gate다.
  현재 상태는
  `blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt`,
  `operator_receipt_ready=false`, `receipt_csv_present=true`,
  `receipt_row_count=51`, `required_template_count=51`,
  `pass_row_count=0`, `blocked_row_count=51`,
  `approved_payload_count=0`, `template_fill_ready_row_count=0`,
  `coordinate_validation_pass_payload_row_count=0`,
  `coordinate_validation_blocked_payload_row_count=51`,
  `metric_source_template_row_fingerprint_required=true`,
  `metric_source_template_row_fingerprint_verified_count=51`,
  `metric_source_template_row_fingerprint_mismatch_count=0`,
  `payload_write_allowed=false`, `canonical_intake_promotion_allowed=false`,
  `claim_promotion_allowed=false`, `external_state_mutated=false`,
  `first_blocked_template_id=r9_statistical_support_metric_source_template_001`,
  `first_blocked_metric_name=dockq`,
  `most_common_row_blocker=operator_placeholders_unfilled`,
  `approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`를 기록한다.
  따라서 coordinate validation이 17/17 pass로 닫힌 뒤에도, operator가 51개 row의
  numeric value/method/operator/timestamp/license/zero-external-engine-call 확인을 채우고
  최신 template fingerprint와 맞춰 승인하기 전에는 metric payload JSON write, canonical intake,
  claim promotion이 열리지 않는다.
  `runs/engine_refinement_claim_evidence_priority_packet_current.json`과
  `runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json`도 이
  work-order, metric materialization readiness, metric source templates,
  coordinate intake, coordinate-fetch R4 preflight를 source artifact로 읽어 top operator step을
  `Review the R4 coordinate-fetch preflight`,
  `public_benchmark_statistical_support_coordinate_intake_ready=true`,
  `public_benchmark_statistical_support_coordinate_intake_row_count=17`,
  `public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count=136`,
  `public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count=0`,
  `public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count=17`,
  `public_benchmark_statistical_support_metric_source_templates_ready=true`,
  `public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_r4_download_executed=false`, 및
  `planned_metric_source_payload_count=51`로 전환한다.
  `runs/goal_bottleneck_briefing_current.json`도 같은 priority packet을 직접 읽어
  `R9_engine_refinement_claim_promotion` completion-audit row와 summary에
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_row_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_ready_count=0`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_blocked_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_input_artifact_count=34`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count=0`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count=51`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count=0`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_row_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count=136`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count=0`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count=17`,
  `engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_download_executed=false`,
  `engine_refinement_claim_evidence_priority_packet_top_next_operator_step=Review the R4 coordinate-fetch preflight...`를
  보존한다. 따라서 top-level 병목 briefing도 R9를 단순 receipt placeholder가
  아니라 coordinate validation 0/17 및 metric source payload 0/51 과학/정확도
  병목으로 표시한다.
  따라서 operator handoff는 더 이상 8개 materialized 후보를 상용 claim으로 바로
  검토하라고 안내하지 않고, 17개 후보의 coordinate validation, DockQ/lDDT-PLI/internal
  ΔG source payload materialization, bootstrap 재검증을 먼저 요구한다.
  `runs/refine_tier_public_benchmark_work_order_apply_current.json`도 이 validation
  CSV와 `runs/refine_tier_public_benchmark_metric_evidence_current.csv`를 필수
  의존성으로 소비하며, `receptor_coordinate_validation_required=true`,
  `receptor_coordinate_validation_pass_row_count=8`,
  `receptor_coordinate_validation_blocked_row_count=0`,
  `metric_evidence_required=true`, `metric_evidence_pass_row_count=0`,
  `metric_evidence_blocked_row_count=8` 상태에서는 operator가
  DockQ/lDDT-PLI/internal ΔG 숫자만 채워도 candidate intake를 쓰지 못한다.
  materialized apply validator는
  `runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json`에서
  `refine_tier_public_benchmark_work_order_apply_ready`, `apply_ready=true`,
  `receptor_coordinate_validation_pass_row_count=8`,
  `metric_evidence_pass_row_count=8`,
  `metric_evidence_contract_blocked_row_count=0`,
  `candidate_claim_grade_public_benchmark_ready=true`를 기록한다. 이 값은 기존
  aggregate readiness 기준의 candidate ready 신호이며, 위 materialization summary의
  `claim_grade_public_benchmark_statistical_support_ready=false`를 덮어쓰는
  broad commercial parity 승격 신호가 아니다. 기본 current apply
  gate는 여기서 한 번 더 fail-closed로 재검증한다. 즉 validation CSV가
  `pass`를 주장하더라도 work-order의 `target_id`/`pose_id`와 다르거나,
  receptor artifact filename/member가 target에 묶이지 않거나, apply 시점에
  artifact를 다시 읽어 계산한 sha256이 validation row의
  `receptor_coordinate_artifact_sha256`와 다르거나, ATOM/macromolecule/protein-like
  residue count가 최소 기준 아래이면 intake write가 막힌다.
  apply gate는 work-order의 `dockq_source_artifact`,
  `lddt_pli_source_artifact`, `internal_deltaG_source_artifact`가 실제 로컬
  파일로 존재하고 schema-valid reviewed payload인지도 직접 확인하며,
  metric evidence CSV의 target/pose/value/source artifact path/payload-valid flag도
  work-order row와 다시 대조한다. 또한 metric evidence CSV의
  `required_metric_input_artifacts`/`required_metric_input_artifact_sha256s`가 apply
  시점의 receptor validation row artifact와 sha256을 포함하는지, 그리고 세 metric
  source JSON이 그 required input artifact 목록을 payload `input_artifacts` 안에
  실제로 포함하는지도 재검증하므로,
  pass라고 적힌 metric CSV만으로 상용 정확도 parity 증거를 우회하는 경로도 닫혀 있다.
  즉 benchmark apply는 native receptor/complex coordinate validation pass와
  metric source artifact presence + payload validation pass를 함께 요구하는
  fail-closed 과학 증거 체인으로 고정됐다.
  따라서 다음 과학 작업은 materialized candidate를 곧바로 tracked intake로 승격하는
  것이 아니라, 최소 25개 public benchmark pair와 8개 이상 holdout pair를 채우고
  bootstrap Spearman p05가 0.5 이상인지 먼저 재검증하는 것이다. 이 통계 support가
  닫힌 뒤에만 operator receipt/claim-boundary 결정과 source-of-truth release exact
  checks를 public benchmark ready 상태로 전환한다.
- CASP17 submission/internal scorecard framework도 같은 좁은 claim-lock 인식을 쓴다.
  일반 `blocked` scorecard는 계속 hard blocker지만,
  `blocked_accuracy_parity`, `blocked_row_count=0`, `missing_row_count=0`,
  `restricted_pass_row_count>0`,
  `top_blockers=[ligand_ranking:broad_gpcr_claim_not_allowed]` 조합은
  `accuracy_parity_claim_scope_lock_only=true`로 보고 framework metric blocker에서 제외한다.
  이는 CASP17 structure/ligand target row를 broad GPCR/Schrödinger-class 상용 claim으로
  승격하는 것이 아니라, 현재 scorecard의 metric-green/claim-lock 상태를 외부 제출
  scorecard에서 metric failure로 오해하지 않게 하는 fail-closed 해석이다.
- `runs/product_rollout_execution_smoke_receipt_current.json`은 별도 R4-approved operator
  실행 receipt를 read-only로 검증해 `product_rollout_execution_smoke_receipt_ready`,
  `receipt_csv_present=true`, `rollout_executed=true`, `external_state_mutated=true`를
  기록한다. 이로 인해 deploy/ops/legal rollup과 master/science rollup은 닫혔고,
  full-commercial release blocker는 R8/R9 receipt와 ACCURACY broad-claim lock으로
  축소됐다.
- `runs/product_launch_r4_preflight_current.json`은 local customer-flow, rollout
  readiness, release bundle, commercial-independence/license, third-party review,
  restricted engine readiness를 하나로 묶어
  `product_launch_r4_preflight_ready`, `blocker_count=0`, `check_count=7`,
  `pass_count=7`을 기록한다.
  단, `authorized_for_external_mutation=false`, `launch_executed=false`,
  `external_state_mutated=false`이므로 실제 배포/remote mutation은 여전히 별도 R4 확인 전까지 닫혀 있다.

---

## 2) Operator 경계만 남은 영역 (accounting green, 실행/승인은 fail-closed)

Tracked accounting roll-up 중 §1b–§1i 및 API runner readiness는 닫혔고,
master/science rollup도 `open_gap_ids=[]`로 닫혔다. 남아 있는 것은 master gap이 아니라
R8/R9 evidence receipt와 `ACCURACY:ligand_ranking` broad claim-scope lock이다.
아래는 **실제 실행·승인·외부 결과**가 필요한 operator/external 경계이며,
builder artifact가 green이어도 full-commercial claim으로 자동 승격되지 않는다.

| 영역 | 현재 posture | 다음 operator 단계 |
|---|---|---|
| Product execution / delivery | latest R4 receipt ready; future execution fail-closed | 다음 rollout마다 Target/Action/Impact/Risk/Rollback/Verification 제시 후 explicit R4/operator approval |
| Transition / ligand-heavy cleanup | `operator_approval_pending` | cleanup approval token + protected policy decision |
| CAMEO official results | `evidence_ready` (local scaffold) | official results intake; outbound send는 별도 승인 |
| Goal operator board | `operator_actions_required` | surfaced action rows를 순서대로 처리 |

### A. API ↔ Engine wiring — P0/P1 갭 클로저 완료 (2026-06-06)

**현재 상태**
- HTVS stage2/3 production config, two-pass 4-bead cascade, topo corrector, stage2 skip router가 상용 경로에 연결됨.
- enabled runner profile 3종 (`ligand_htvs_pipeline_default`, `backmapping_scoring.production`, `ligand_topk_delivery.production`) + evidence reviewed.
- `api/docking_dispatch.py`가 ledger → SQLite worker queue 자동 enqueue를 수행 (`API_VALIDATED_RUNNER_ENABLED=1` 필요).
- `api/tasks.py`는 `runner_profile_id`가 없는 일반 simulation 요청에는 계속
  fail-closed로 동작한다.
- `runner_profile_id`가 있을 때는 `api/validated_runner.py`의
  `execute_validated_runner_profile`을 통해 operator-approved profile만 실행한다.
  기본값은 `API_VALIDATED_RUNNER_ENABLED=0`이며, profile JSON의 `"enabled": true`,
  `production_readiness`, allowlisted `runner_script`, `runner_script_sha256`,
  evidence artifact, expected `result_file_template` 검증을 모두 통과해야 실행된다.
- `tools/validate_api_runner_profiles.py`는 profile directory를 검사해 enabled profile의
  production readiness/evidence/hash gate를 CI/배포 전 단계에서 검증한다.
- `tools/build_api_runner_profile_enablement_work_order.py`는 disabled profile별 runner
  hash와 evidence template을 생성한다. 현재 산출물은
  `runs/api_runner_profile_enablement_work_order_current.json` 및
  `config/api_validated_runner_profiles/evidence/backmapping_scoring.example.evidence.template.json`.
- `tools/product/build_api_runner_profile_promotion_readiness.py`와
  `runs/api_runner_profile_promotion_readiness_current.json/.csv/.md`는 profile
  evidence(`.evidence.template.json` 또는 `.evidence.json`)와
  `production_readiness.evidence_artifact`를 fail-closed로 판정한다. bootstrap
  후 최신 상태는 `api_runner_profile_promotion_ready`, `profile_count=4`,
  `promotion_ready_count=4`이며 enabled production profile은 reviewed evidence로
  accounting green을 유지한다. `profile_enabled_by_this_tool=false`,
  `runner_executed=false`, `external_state_mutated=false`는 그대로다.
- enabled runner profile 3종의 `production_readiness.runner_script_sha256`은 현재
  allowlisted runner script hash와 동기화됐고, `tools/product/validate_api_runner_profiles.py`는
  `status=pass`, `failed_profile_count=0`이다. 이 hash gate 복구 뒤
  Tier α ADRB2 dispatch smoke도 `tier_alpha_adrb2_dispatch_smoke_pass`로 재검증됐다.
  최신 refresh 계약은 이 smoke를 `--timeout-seconds 420`으로 실행하고,
  `api/validated_runner.py`는 runner timeout 발생 시 subprocess group 전체를
  kill한 뒤 `runner_execution.json`에 `timed_out=true`,
  `process_group_killed_on_timeout=true`, `validated_runner_timeout:<N>s`를
  fail-closed로 기록한다. 따라서 내부 HTVS/Newton probe가 parent timeout을 넘겨
  release refresh를 매달리게 하는 상태는 별도 timeout evidence로 수렴한다.
- 같은 도구는
  `runs/api_runner_profile_promotion_operator_template_current.csv`도 생성한다.
  이 템플릿은 profile별 `operator_decision`, `approval_token`,
  input/output/claim/gate review boolean, `gate_policy_artifact`, `reviewer`,
  `reviewed_at_utc` 입력 칸을 제공하며, release bundle의
  `api_runner_profile_promotion_operator_template_recorded` 체크에 포함된다.
- `tools/product/build_api_runner_profile_promotion_operator_receipt.py`는 위 template을
  operator receipt로 판정한다. 현재 기본 template은 빈 operator decision/review
  fields라 `runs/api_runner_profile_promotion_operator_receipt_current.json`이
  `blocked_api_runner_profile_promotion_operator_receipt`,
  `operator_receipt_ready=false`, `blocked_row_count=4`,
  `first_blocked_profile_id=backmapping_scoring.example`,
  `most_common_row_blocker=operator_decision_missing`을 기록한다. 이 receipt는
  release bundle, source-of-truth refresh/freshness, goal operator intake kit,
  `/product/api-runner-profile-promotion-operator-receipt` API surface에 연결되어,
  `promotion_ready=true`와 실제 operator-approved promotion decision을 분리한다.
  최신 `goal_release_decision_gate_current.json`과 `/goal/status`도
  `api_runner_profile_promotion_operator_receipt_*` 키로 이 상태를 노출하며,
  final refresh는 `status=blocked_api_runner_profile_promotion_operator_receipt`,
  `profile_count=4`, `blocked_row_count=4`,
  `first_blocked_profile_id=backmapping_scoring.example`,
  `approval_token_required=APPROVE_API_RUNNER_PROFILE_PROMOTION`을 exact check로 고정한다.
- `tools/product/build_api_runner_profile_promotion_operator_staging_apply.py`는 위
  receipt 앞단에 operator staging preview를 추가한다. 이 preview는
  `runs/api_runner_profile_promotion_operator_template_current.csv`를 후보 receipt로
  재판정하고, 동시에 `runs/accuracy_parity_scorecard_current.json`의
  `overall_commercial_tool_accuracy_parity_allowed`/`schrodinger_class_claim_allowed`,
  `runs/science_claim_promotion_gap_closure_current.json`의
  `claim_promotion_allowed`/open gap count를 함께 노출한다. 따라서 "상용제품 대비
  정확도 차이가 없으면 승격 가능"이라는 판단은 이제 metric parity 자체와
  broad claim-scope review를 분리해 확인한다. science boundary accounting은
  `science_claim_open_gap_count=0`으로 닫혔지만, broad commercial profile 승격은
  `candidate_operator_receipt_ready=true` + `accuracy_parity_gate_ready=true`
  + `science_claim_gate_ready=true` + explicit approval token의 조합으로
  fail-closed 확인된다. 현재 기본값은
  `runs/api_runner_profile_promotion_operator_staging_apply_current.json`에서
  `blocked_api_runner_profile_promotion_operator_staging_apply`,
  `candidate_operator_receipt_ready=false`, `candidate_blocked_row_count=4`,
  `candidate_first_blocked_profile_id=backmapping_scoring.example`,
  `candidate_most_common_row_blocker=operator_decision_missing`,
  `accuracy_parity_gate_ready=false`, `science_claim_open_gap_count=0`,
  `science_claim_gate_ready=false`(`claim_promotion_allowed=false`),
  `broad_commercial_profile_promotion_allowed=false`, `live_copy_allowed=false`,
  `canonical_operator_template_written=false`, `profile_enabled_by_this_tool=false`,
  `runner_executed=false`, `external_state_mutated=false`로 고정된다. 이 artifact는
  source-of-truth refresh/freshness, `/product/api-runner-profile-promotion-operator-staging-apply`
  API surface에 연결되어 operator decision과 benchmark/science gate의 차이를 숨기지 않는다.
- `api/main.py`의 legacy `jobs = {}` in-memory dict은 제거됨.
  현재는 `api/job_store.py`의 `SQLiteJobStore`와
  `api/config.py`의 `api_job_store_path` 기본값
  `./results/api_jobs.sqlite3`로 simulation job metadata를 보존한다.
- `api/result_manifest.py`와 `api/worker.py`는 completed/failed job마다
  HMAC-SHA256 signed `result_manifest.json`을 쓰고,
  SQLite job record의 `result_manifest_path`와 `status.json`의 `result_manifest`에
  같은 경로를 남긴다.
- `api/job_store.py`는 `acquire_next_job`, `heartbeat_job`,
  `release_job_for_retry`를 제공해 SQLite-backed worker lease/heartbeat/retry
  primitive를 갖췄다.
- `api/worker.py`의 `process_next_job_once`와
  `tools/run_api_simulation_worker.py`는 SQLite queue에서 job을 lease로 가져와
  retry budget과 signed terminal manifest를 적용하는 별도 worker consumer
  경로를 제공한다.
- `api/worker.py`는 async runner 실행 중 `API_WORKER_HEARTBEAT_INTERVAL_SECONDS`
  주기로 lease heartbeat를 연장해 long-running job의 lease expiry/re-acquire
  위험을 줄인다.
- `/simulate`는 기본적으로 durable queue에 job을 submit하고 즉시 실행하지 않는다.
  `API_INLINE_WORKER_ENABLED=1`일 때만 FastAPI `BackgroundTasks`로
  `process_next_job_once`를 트리거한다.
- `deploy/docker-compose.product.yml`은 `api-server`와 `api-worker`를 같은
  product image와 shared `/data` volume으로 배치해 SQLite job store/result
  manifest를 공유하게 한다.
- `deploy/systemd/micf-api-worker.service`와 `deploy/systemd/api-worker.env.example`은
  on-prem VM/self-hosted 배포에서 worker consumer를 supervised process로 띄우는
  최소 단위를 제공한다.
- `deploy/k8s/`는 API server, API worker, shared PVC, ConfigMap/Secret 예시,
  Service, kustomization을 제공해 K8s rollout의 1차 배포 단위를 고정한다.
- `.github/workflows/product-api-worker.yml`은 API/worker/deploy artifact 계약 테스트와
  worker CLI smoke를 CI에서 실행한다.
- 즉, API는 기본적으로 queue/status surface만 열고, 실제 docking/MD 실행은
  operator-approved validated runner profile이 있을 때만 제한적으로 연결된다.
- `core/forcefield.py`는 sequence-mapped residue class별 coarse LJ
  sigma/epsilon mixing과 screened acidic/basic residue charge proxy를
  PyTorch reference/nonbonded 경로에 반영하고, consecutive CA residue에 대한
  restricted harmonic backbone bond term과 consecutive CA triplet angle term을
  core/reference 경로에 더한다. `DataGenerator` runtime profile의
  `backbone_bond_*`, `k_angle`, `theta0`도 ForceField param으로 연결되고,
  `tools/generate_ligand_trajectory_engine.py` CLI/cache key도 coarse
  forcefield param surface를 노출한다.
  `core/topology.py`는 CA/SC block-layout residue type alignment를 제공한다.
  다만 full all-atom/solvent force field는 아니므로 "restricted analysis engine"이지
  OpenMM/Schrodinger급이라고는 못 함.

**병목 원인**
- scientific claim boundary를 깨지 않기 위해 일반 요청은 fail-closed로 의도적 차단.
- validated runner adapter와 production profile readiness gate는 1차 연결됐지만,
  실제 profile별 claim/gate evidence review와 enablement는 operator approval에 묶여 있다.
- durable job metadata, signed result manifest, SQLite worker lease/heartbeat/retry
  primitive, local worker consumer, queue handoff, async long-running heartbeat loop,
  docker-compose/systemd supervised worker unit, K8s rollout skeleton, CI contract
  workflow, profile readiness/evidence validation CLI, profile enablement work order와
  evidence template 생성, profile promotion readiness gate, operator promotion
  template와 release bundle linkage는 1차 보강 완료.
- 현재 직접 병목은 runner script 자체 부재가 아니라, disabled profile evidence
  template의 operator review field가 모두 false/empty라 승격 조건을 만족하지 못하는 점이다.
- 다만 실제 상용 profile 승격과 full all-atom/solvent S-class
  physics/topology 확장은 아직 남아 있다. 이번 residue-aware coarse nonbonded,
  screened charge, coarse backbone bond/angle 보강은
  alanine-only/단일 LJ/무전하/무연결 병목을 줄이고 runtime profile 및
  trajectory engine param surface 연결까지 확보했지만, claim 경계는 그대로 restricted다.

**필요 작업**
- `api/tasks.py`는 operator-approved profile 기반으로
  `tools/run_ligand_htvs_pipeline.py` 또는 `tools/run_ligand_backmapping_scoring.py`
  같은 allowlisted runner를 호출하는 adapter 1차 연결 완료.
- simulation job metadata는 SQLite-backed durable store로 마이그레이션 완료.
- SQLite worker lease/heartbeat/retry primitive와 API `/simulate` queue handoff는
  1차 연결 완료.
- docker-compose/systemd/K8s worker 배포 단위와 CI contract workflow는 1차 고정 완료.
- production profile enablement checklist와 machine-checkable evidence/hash gate는
  1차 고정 완료.
- profile enablement work order와 evidence template은 1차 생성 완료.
- profile promotion readiness gate, operator promotion template, release bundle linkage는
  1차 완료.
- 다음 단계: operator가 evidence template의 input/output/claim/gate 항목을 실제 검토해
  true로 채우고, `gate_policy_artifact`, `reviewer`, `reviewed_at_utc`를 기록한 뒤,
  별도 `APPROVE_API_RUNNER_PROFILE_PROMOTION` 승인/edit 절차로 enabled profile로 승격.
- `core/forcefield.py`/`core/topology.py`는 sequence-aware residue class
  nonbonded, screened coarse charge, coarse CA backbone bond/angle terms,
  CA/SC block-layout residue alignment까지 확장 완료.
  trajectory engine CLI/cache key에도 해당 coarse forcefield param surface를
  연결 완료.
  `core/allatom_forcefield.py`는 covalent-radii equilibrium 기반 bonded energy,
  tetrahedral angle proxy, periodic torsion proxy, sp2-like improper planarity proxy,
  element/degree 기반 internal atom typing, neutralized partial charge proxy,
  1-2 bonded-pair nonbonded exclusion을 쓰는 internal united-atom typed tier로 보강됐다.
  `atom_typing_coverage_report`는 흔한 ligand halogen(`F/Cl/Br/I`)을 별도 타입으로
  계량하고 unsupported element/default fallback 및 metal/cofactor-like element
  (`Mg/Zn/Fe/Ca/Na`)를 fail-closed로 드러낸다. `allatom_energy` 결과도
  `atom_typing_coverage_status`, `unsupported_elements`,
  `unsupported_metal_or_cofactor_count`와
  `metal_cofactor_coordination_status`,
  `metal_cofactor_coordination_donor_count`,
  `claim_grade_metal_cofactor_parameterization_ready=false`를 노출해 금속/보조인자성
  원소가 있는 경우 coordination 후보를 계량하지만 parameter claim은 막는다.
  `ionizable_atom_typing_status`, `ionizable_atom_type_counts`,
  `claim_grade_charged_parameterization_ready=false`를 노출해 charged-residue/
  ionizable local chemistry가 내부 타입 surface로만 처리됨을 명시한다.
  `ionizable_atom_typing_report`는 carboxylate/basic N/phosphate/thiolate-like
  local chemistry를 계량하지만 formal protonation-state assignment와 calibrated
  charged-residue parameter claim은 열지 않는다.
  `formal_charge_proxy_report`는 같은 local chemistry에서 formal charge proxy를
  계산해 `formal_charge_proxy_net_e`와 atom-level proxy rows를 남기지만,
  `formal_charge_proxy_not_calibrated` blocker와
  `claim_grade_formal_charge_ready=false`를 유지한다.
  `parameter_calibration_status=internal_proxy_uncalibrated`,
  `claim_grade_parameterization_ready=false`를 함께 싣는다.
  `core/mm_gbsa.py`, `core/explicit_solvent.py`, `core/fep.py`의
  GB/SA → all-atom → explicit TIP3P-like shell → FEP scaffold smoke까지
  `runs/engine_refinement_tier_readiness_current.json`에서
  `check_count=36`, `pass_count=36`, `blocked_count=0`으로 검증된다.
  같은 gate는 `refine_tier_atom_typing_coverage_surface`에서
  `supported_elements=H,C,N,O,S,P,F,CL,BR,I`, `default_atom_count=0`,
  `coverage_fraction=1.0`인 내부 타입 커버리지 surface도 확인하며,
  summary에 `atom_typing_coverage_surface_ready=true`를 노출한다.
  `refine_tier_unsupported_metal_fail_closed_surface`는 `Zn/Mg`가
  support로 오인되지 않고 `blocked_atom_typing_coverage`로 보고되는지 확인하며,
  summary에 `unsupported_metal_fail_closed_surface_ready=true`를 노출한다.
  `refine_tier_metal_cofactor_coordination_claim_guard`는 Zn 주변 N/O/S donor
  후보 3개를 coordination surface로 남기며,
  `metal_cofactor_coordination_claim_guard_ready=true`를 노출한다. 동시에
  `claim_grade_metal_cofactor_parameterization_ready=false`와
  `metal_cofactor_parameterization_not_supported` blocker를 유지한다.
  `refine_tier_charged_residue_atom_typing_surface`는 carboxylate/basic N/phosphate/
  thiolate-like local chemistry를 타입으로 분리하고
  `charged_residue_atom_typing_surface_ready=true`를 노출한다. 동시에
  `claim_grade_charged_parameterization_ready=false`와
  `charged_residue_parameter_calibration_not_ready` blocker를 유지해 formal
  protonation/calibrated charge claim을 막는다.
  `refine_tier_formal_charge_proxy_claim_guard`는 `formal_charge_proxy_net_e=-2.0`을
  계산하지만 `claim_grade_formal_charge_ready=false`와
  `formal_charge_proxy_not_calibrated` blocker를 유지한다.
  `refine_tier_parameter_calibration_claim_guard`는 internal proxy parameter가
  공개 benchmark pair 부족과 benchmark gate 미통과 상태에서 claim-grade로 승격되지
  않도록 `parameter_calibration_claim_guard_ready=true`로 감시한다.
  `refine_tier_solvent_fep_calibration_claim_guard`는 GB/SA, explicit TIP3P-like shell,
  FEP surface가 finite로 계산되는지 확인하고
  `solvent_fep_calibration_claim_guard_ready=true`를 노출한다. 동시에
  `claim_grade_solvent_fep_calibration_ready=false`,
  `explicit_solvent_md_sampling_not_validated`,
  `fep_holdout_calibration_not_validated`, public pair 부족 blocker를 유지한다.
  `refine_tier_structure_quality_interface_claim_guard`는 MolProbity-like clashscore proxy,
  reference lDDT/DockQ/TM proxy, receptor-ligand interface contact coverage를 계산하고
  `structure_quality_interface_claim_guard_ready=true`를 노출한다. 동시에
  `claim_grade_structure_quality_ready=false`,
  `external_molprobity_not_available`, `external_openstructure_not_available`,
  `native_complex_benchmark_not_ready` blocker를 유지한다.
  `refine_tier_public_benchmark_blocker_linkage`는 public benchmark gate의
  `blocked_refine_tier_public_benchmark_readiness`, `blocker_count=6`,
  `public_benchmark_work_order_row_count=8`,
  `public_benchmark_operator_work_order_ready=true`를 engine readiness summary에
  직접 연결한다.
  같은 gate는 pose RMSD/LDDT-PLI/DockQ proxy metric surface와
  MM-GBSA calibration claim guard도 확인하며,
  `benchmark_metric_surface_ready=true`,
  `parameter_calibration_claim_guard_ready=true`,
  `free_energy_calibration_claim_guard_ready=true`,
  `claim_grade_public_benchmark_ready=false`로 claim 경계를 고정한다.
  summary는 `claim_promotion_allowed=false`,
  `claim_promotion_blocker_count=6`,
  `claim_promotion_action_row_count=6`,
  `claim_promotion_blockers=[public_benchmark_gate_not_ready,
  parameter_calibration_claim_not_ready, metal_cofactor_parameterization_not_ready,
  charged_residue_protonation_and_charge_calibration_not_ready,
  solvent_fep_public_pair_calibration_not_ready,
  external_structure_quality_parity_not_ready]`도 함께 노출한다.
  `claim_promotion_action_rows`는 blocker별 `required_evidence`,
  `owner_action`, `gate_or_artifact`, `external_dependency`, `claim_boundary`,
  `blocking_signals`, `next_required_step`를 포함하는 action board로 남아,
  public benchmark work-order 채움, parameter calibration, metal/cofactor parameter source,
  protonation/charge calibration, solvent/FEP public-pair calibration, 외부
  MolProbity/OpenStructure/native-complex parity ingestion을 각각 별도 operator/evidence
  작업으로 분리한다. CLI 실행 시 같은 row set은
  `runs/engine_refinement_claim_promotion_action_board_current.csv`에도 기록되어
  operator가 blocker별 evidence 수집/검토 상태를 별도 표로 추적할 수 있다.
  이 action board CSV는 `product_launch_r4_preflight` summary,
  `product_release_bundle_current.json`의
  `engine_refinement_claim_promotion_action_board_recorded` check,
  `product_release_source_of_truth_gate_current.json`의 freshness row에도 연결되어
  독립 상용 릴리스 묶음에서 evidence blocker board가 빠지거나 stale해지는 것을 막는다.
  또한 `goal_operator_action_board_current.json`은 같은 CSV를
  `product_engine_refinement` lane의 `resolve_refine_tier_claim_promotion_blocker`
  actions로 흡수하고, `goal_operator_intake_kit_current/manifest.json`은
  `engine_refinement_claim_promotion_action_board` entry로 노출해 operator-facing
  작업판에서도 claim blocker evidence 수집이 빠지지 않게 한다.
  `tools/product/build_engine_refinement_claim_evidence_receipt.py`는 이 action board
  뒤에 붙는 evidence receipt gate다.
  `config/engine_refinement_claim_promotion_evidence_receipt_current.csv`는 6개 blocker
  receipt template을 tracked로 제공하고, 최신
  `runs/engine_refinement_claim_evidence_receipt_current.json`은 placeholder evidence를
  fail-closed로 판정해 `blocked_engine_refinement_claim_evidence_receipt`,
  `claim_promotion_evidence_receipt_ready=false`, `blocked_row_count=6`을 기록한다.
  `tools/product/build_engine_refinement_claim_evidence_priority_packet.py`는 이 receipt와
  `runs/engine_refinement_claim_promotion_action_board_current.csv`,
  `runs/refine_tier_public_benchmark_readiness_current.json`,
  `runs/refine_tier_public_benchmark_work_order_current.csv`,
  `runs/refine_tier_public_benchmark_work_order_apply_current.json`을 합쳐 R9 operator
  evidence 우선순위를 별도 packet으로 고정한다. 최신
  `runs/engine_refinement_claim_evidence_priority_packet_current.json`은
  `blocked_engine_refinement_claim_evidence_priority_packet`,
  `priority_packet_ready=true`, `priority_item_count=6`,
  `operator_input_required_count=6`,
  `top_blocker_id=public_benchmark_gate_not_ready`,
  `top_priority_bucket=public_benchmark_work_order_apply_required`,
  `public_benchmark_work_order_apply_blocked_row_count=8`을 노출해,
  R9의 첫 수동 입력이 공개 benchmark work-order 8개 row 검증임을 숨기지 않는다.
  `tools/product/build_engine_refinement_claim_evidence_operator_staging_apply.py`는
  이 R9 receipt와 public benchmark work-order를 canonical receipt/intake에 쓰기 전
  fail-closed preview로 다시 검증한다. 최신
  `runs/engine_refinement_claim_evidence_operator_staging_apply_current.json`은
  `blocked_engine_refinement_claim_evidence_operator_staging_apply`,
  `candidate_receipt_ready=false`, `candidate_receipt_blocked_row_count=6`,
  `candidate_public_benchmark_work_order_ready=false`,
  `candidate_public_benchmark_blocked_row_count=8`,
  `field_worksheet_pending_field_count=296`,
  `field_worksheet_work_order_pending_field_count=56`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_ready=true`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_row_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count=136`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count=17`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count=187`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`,
  `live_copy_allowed=false`, `public_benchmark_intake_write_allowed=false`,
  `external_engine_calls_executed=false`, `external_state_mutated=false`를 기록한다.
  또한 field worksheet 자체의 `next_required_step`도
  `local_coordinate_path_candidates=136`,
  `local_coordinate_present_targets=0`,
  `local_coordinate_missing_targets=17`를 포함해, R9 operator가 coordinate fetch 승인 전에
  로컬 후보 경로 재고와 실제 present target 결손을 동시에 보게 한다.
  따라서 R9 operator가 receipt row나 public benchmark work-order row를 채워도,
  승인 token과 semantic gate가 모두 맞기 전에는 canonical evidence receipt나 tracked
  public benchmark intake CSV가 갱신되지 않는다.
  최신 `runs/goal_release_decision_gate_current.json`도 이 priority packet을
  `engine_refinement_claim_evidence_priority_packet_*` summary와 recorded row로 직접
  흡수하며, final refresh exact check가 `top_blocker_id=public_benchmark_gate_not_ready`,
  `top_priority_bucket=public_benchmark_work_order_apply_required`, work-order row 8개,
  apply blocked row 8개, approval token을 고정한다.
  이 receipt artifact는 `engine_refinement_tier_readiness`,
  `product_launch_r4_preflight`, `product_goal_completion_audit`,
  `goal_operator_action_board`, `goal_operator_intake_kit`,
  commercial readiness operator packet/handoff, release bundle/source-of-truth
  freshness에 연결되어 "증거가 필요함"과 "증거가 검증됨"의 경계가 분리된다.
  최신 `runs/product_goal_completion_audit_current.json`은 같은 blocker 묶음을
  `R9_engine_refinement_claim_promotion` release blocker로 기록한다. 따라서
  full-scope claim closure나 restricted delivery accounting이 green이어도,
  refine-tier claim-grade evidence가 없으면 `goal_complete=false`가 유지된다.
  최신 audit summary는 `release_blocker_fail_count=2`,
  `release_blocker_requirement_ids=[R8_full_scope_claim_closure, R9_engine_refinement_claim_promotion]`,
  `primary_release_blocker_requirement_id=R8_full_scope_claim_closure`,
  `primary_release_blocker=full_scope_claim_closure_not_ready`를 노출한다.
  `runs/goal_operator_action_board_current.json`도 같은 blocker를
  `primary_release_blocker_action_id=product_scope_expansion:resolve_full_scope_breadth_evidence_receipt`와
  `primary_release_blocker_action_required_input=config/product_scope_breadth_evidence_receipt_current.csv`로 연결한다.
  `runs/goal_operator_intake_kit_current/manifest.json`과 README도 같은
  `primary_release_blocker_action_*` 필드를 전달하므로 operator handoff kit에서
  현재 R8 입력 파일이 사라지지 않는다.
  같은 R9 상태는 `runs/product_commercial_readiness_operator_packet_current.json`과
  `runs/product_commercial_readiness_handoff_bundle_current.json` summary의
  `engine_refinement_claim_promotion_*`,
  `engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51` 필드 및
  `/product/commercial-readiness-operator-packet`,
  `/product/commercial-readiness-handoff-bundle`,
  `/product/engine-refinement-claim-evidence-receipt` API surface로도 전파되어, 상용 readiness
  handoff 단계에서 claim-grade evidence 병목이 빠지지 않게 한다. handoff bundle은
  `runs/engine_refinement_claim_promotion_action_board_current.csv`,
  `runs/engine_refinement_claim_evidence_receipt_current.json`,
  `runs/engine_refinement_claim_evidence_operator_staging_apply_current.json`,
  `config/engine_refinement_claim_promotion_evidence_receipt_current.csv`도
  `local_engine_refinement_claim_*` artifact reference로 추적한다. 또한
  `runs/product_release_bundle_current.json`은 `product_goal_completion_audit`
  artifact, `product_full_commercial_blocker_evidence_matrix` artifact,
  `product_goal_completion_audit_full_claim_boundary_recorded` check,
  `product_full_commercial_blocker_evidence_matrix_recorded` check를 포함해,
  restricted release bundle review에서도 full commercial science claim 미완료가
  숨지 않게 한다.
  `tools/accounting/build_goal_bottleneck_briefing.py`는 release burndown이 clear인
  경우에도 `product_goal_completion_audit`의 `release_blocker=true` rows를 흡수해
  현재 `R8_full_scope_claim_closure`와 `R9_engine_refinement_claim_promotion`을
  `completion_audit_release_blocker` 병목으로 노출한다. `/goal/status`도 active
  bottleneck briefing이 있으면 intake/action board의 오래된 primary action보다 이
  full-commercial 병목 primary를 우선 표시한다. 또한 `/goal/status`는
  `full_commercial_release_blocker_ids=[R8_full_scope_claim_closure,
  R9_engine_refinement_claim_promotion, ACCURACY:ligand_ranking]`,
  `restricted_release_allowed=true`, `full_commercial_release_allowed=false`,
  `full_commercial_release_blocker_visibility_ready=true`,
  `completion_audit_release_blocker_bottleneck_count=2`,
  `commercial_readiness_handoff_bundle_artifact_reference_count=43`를 노출하고,
  `product_goal_primary_release_blocker_requirement_id=R8_full_scope_claim_closure`,
  `primary_release_blocker_action_id=product_scope_expansion:resolve_full_scope_breadth_evidence_receipt`,
  `primary_release_blocker_action_required_input=config/product_scope_breadth_evidence_receipt_current.csv`도
  action board/intake kit에서 끌어와 노출한다. `goal_api_surface_contract_current.json`은 이
  R8/R9/ACCURACY blocker set + primary release blocker action + commercial handoff visibility를
  `goal_full_commercial_bottleneck_visibility_present` check로 고정한다.
  `runs/product_release_source_of_truth_gate_current.json`도
  `product_commercial_readiness_operator_packet_semantic_ready`와
  `product_commercial_readiness_handoff_bundle_semantic_ready` row로 최종 operator
  packet/handoff bundle의 R9 metric-source-template 51/0/51 fields를 exact 검증한다.
  `tools/product/build_product_full_commercial_blocker_evidence_matrix.py`는 같은
  R8/R9 release blocker를 `runs/product_full_commercial_blocker_evidence_matrix_current.json`
  한곳에 집계한다. 최신 matrix는
  `blocked_product_full_commercial_blocker_evidence_matrix`,
  `release_blocker_visibility_ready=true`, `matrix_row_count=12`,
  `blocked_matrix_row_count=12`, `approval_token_count=2`를 기록해 R8/R9 receipt
  입력이 둘 다 아직 operator evidence/approval token 대기 상태임을 숨기지 않는다.
  이 matrix는 `/product/full-commercial-blocker-evidence-matrix` API surface로
  직접 노출되며, `/goal/status`도
  `full_commercial_blocker_evidence_matrix_*` 요약 키로 matrix status, row count,
  blocked row count, approval token count, 첫 blocked release blocker/evidence row를
  함께 표시한다. `goal_release_decision_gate_current.json`도 같은 matrix를
  `product_full_commercial_blocker_evidence_matrix_*` 요약 키와
  `product_full_commercial_blocker_evidence_matrix_recorded` row로 기록해,
  최종 release decision packet에서도 R8/R9 evidence receipt 병목이 숨지 않는다.
  같은 decision gate는 `goal_bottleneck_briefing_current.json`의
  `full_commercial_evidence_receipt_*` summary도
  `goal_bottleneck_briefing_full_commercial_evidence_receipt_*` 키와
  `goal_bottleneck_briefing_full_commercial_receipts_recorded` row로 흡수해,
  matrix 진단뿐 아니라 operator handoff receipt 묶음 자체도 최종 decision packet에
  남긴다. `tools/run_product_release_current_refresh.py --execute`의 final-gate
  verification도 `goal_release_decision_gate_current.json`에서 이
  `goal_bottleneck_briefing_full_commercial_receipts_recorded=true`, entry count 2,
  template present 2/2, approval token 2개, source gate status, required input CSV,
  approval token 문자열을 exact check로 요구하므로, final refresh가 green이어도 이
  decision linkage가 조용히 빠지는 상태를 허용하지 않는다.
  같은 release decision packet은 bottleneck briefing의
  `production_ai_registry_promotion_priority_*` summary도
  `goal_bottleneck_briefing_production_ai_registry_promotion_priority_*` 키와
  `goal_bottleneck_briefing_production_ai_registry_promotion_priority_recorded`
  row로 승격한다. 현재 trained/preflight-ready checkpoint는 registry에
  반영되어 `observed_registry_trained_model_checkpoint_count=1`이고, top gate는
  `default_residual_mode_guarded`, top bucket은
  `guarded_residual_mode_selection_required`, missing gate count는 3으로 고정되며,
  `tools/run_product_release_current_refresh.py --execute` final-gate verification도
  이 값을 exact check로 요구한다. 따라서 restricted/local release gate가 green이어도
  Production AI registry promotion의 첫 운영 병목인 guarded mode/operator receipt
  선택이 최종 의사결정 packet 밖으로 빠질 수 없다.
  최신 `goal_release_decision_gate_current.json`은 원본
  `production_ai_registry_promotion_priority_packet_current.json`도
  `production_ai_registry_promotion_priority_packet_*` summary와 recorded row로 직접
  흡수하며, final refresh exact check는 `status`,
  `operator_receipt_status`, `observed_registry_default_residual_mode=shadow`,
  `observed_registry_trained_model_checkpoint_count=1`, approval token을 고정한다.
  같은 decision gate는 R9
  `engine_refinement_claim_evidence_priority_packet_current.json`도 직접 읽어
  public benchmark work-order apply 8개 blocked row와 top blocker를 final refresh exact
  check에 고정한다.
  최신 decision summary는 restricted/local release surface를
  `release_allowed=true`, `restricted_release_allowed=true`로 유지하면서도
  `full_commercial_release_allowed=false`,
  `full_commercial_release_blocker_ids=[R8_full_scope_claim_closure,
  R9_engine_refinement_claim_promotion, ACCURACY:ligand_ranking]`,
  `primary_full_commercial_release_blocker_id=R8_full_scope_claim_closure`,
  `primary_full_commercial_release_blocker=direct_binding_evidence_missing`을
  별도로 노출한다.
  commercial-readiness operator packet/handoff surface는 같은 R8 blocker를
  `primary_full_commercial_release_blocker_id=R8_full_scope_claim_closure`,
  `primary_full_commercial_release_blocker=full_scope_claim_closure_not_ready`,
  `primary_full_commercial_release_blocker_receipt_csv=config/product_scope_breadth_evidence_receipt_current.csv`
  로 들고, 첫 transporter P0 return 별칭도
  `product_scope_next_operator_completion_item_id=AQP1.core_binder_01`,
  `product_scope_transporter_p0_return_bundle_next_artifact_path=runs/transporter_manual_review_intake_template_current.csv`,
  `product_goal_scope_transporter_p0_operator_validation_candidate_status=operator_validation_required`
  로 고정한다.
  `tools/product/build_product_scope_breadth_evidence_receipt.py`와
  `config/product_scope_breadth_evidence_receipt_current.csv`는 R8 full-scope
  blocker 6종(`direct_binding_evidence_missing`,
  `exact_negative_quantitative_value_missing`,
  `manual_identity_scaffold_confirmation_required`,
  `scientific_domain_gate_not_ready`,
  `allowed_scope_family_count_too_narrow`,
  `explicit_general_platform_flag_missing`)에 대한 operator evidence receipt를
  별도 fail-closed gate로 분리한다. 최신
  `runs/product_scope_breadth_evidence_receipt_current.json`은 placeholder evidence를
  막아 `blocked_product_scope_breadth_evidence_receipt`,
  `full_scope_evidence_receipt_ready=false`, `blocked_row_count=6`,
  `first_blocked_scope_blocker_id=direct_binding_evidence_missing`,
  `first_blocked_evidence_artifact=OPERATOR_FILL_LOCAL_EVIDENCE_JSON`,
  `most_common_row_blocker=operator_placeholders_unfilled`을 기록한다. 같은
  receipt gate는 evidence JSON이 존재하더라도 단순 status/boolean만으로는 통과하지
  않는다. `direct_binding_evidence_missing` row는 primary-source direct-binding
  확인, claim-safe direct-binding kcal 확인, `claim_safe_direct_binding_row_count>=1`,
  `primary_source_verified_count>=1`, surrogate-to-kcal promotion 금지 flag를 함께
  요구하고, `exact_negative_quantitative_value_missing` row도 exact negative
  quantitative row와 primary-source 검증 count를 요구한다. 따라서 현재 blocked는
  "operator receipt 문자열이 비어 있음"보다 더 구체적으로, 상용 claim에 필요한
  직접 결합/negative 정량 evidence 품질 신호가 아직 receipt로 닫히지 않았다는 뜻이다.
  같은
  first-blocked diagnostics는 full-commercial matrix와 `/goal/status`의
  `full_commercial_blocker_evidence_matrix_first_blocked_*`,
  `full_commercial_blocker_evidence_matrix_scope_receipt_most_common_row_blocker`,
  `full_commercial_blocker_evidence_matrix_engine_receipt_most_common_row_blocker`로도
  전파된다. `/goal/status`는 이제 matrix 요약과 별도로
  `product_scope_breadth_evidence_receipt_*` 및
  `engine_refinement_claim_evidence_receipt_*` 필드도 직접 노출해, 두 receipt의
  status, CSV, approval token, row counts, first-blocked evidence/status/blockers,
  required blocker 목록이 상위 goal API에서 빠지지 않게 한다.
  `runs/goal_release_decision_gate_current.json`도 같은 R8/R9 receipt를
  `product_scope_breadth_evidence_receipt_*` 및
  `engine_refinement_claim_evidence_receipt_*` summary와 recorded row로 직접 노출하고,
  final refresh exact check가 status, row counts, first-blocked diagnostics,
  approval token을 고정한다.
  `runs/product_goal_completion_audit_current.json`의 `R8_full_scope_claim_closure`
  row도 이 receipt를 evidence artifact와 observed field로 직접 흡수해,
  scope contract가 green처럼 보이더라도 `full_scope_evidence_receipt_ready=false`면
  full commercial goal completion이 닫히지 않는다. 또한
  `runs/goal_operator_action_board_current.json`은
  `resolve_full_scope_breadth_evidence_receipt` action을 만들고,
  `product_goal_scope_breadth_evidence_receipt_first_blocked_*` summary와 action row의
  `scope_breadth_evidence_receipt_first_blocked_*` 필드로
  `direct_binding_evidence_missing`, `OPERATOR_FILL_LOCAL_EVIDENCE_JSON`,
  expected/observed evidence status, missing true fields, row blockers를 노출한다.
  `runs/goal_operator_intake_kit_current/manifest.json`은
  `product_scope_breadth_evidence_receipt` entry로
  `config/product_scope_breadth_evidence_receipt_current.csv`를 operator template에
  복사한다. intake kit summary는 R8/R9 receipt 묶음을
  `full_commercial_evidence_receipt_*` 필드로 별도 집계해 entry count 2,
  template present 2/2, approval token 2개, 두 source gate status, 두 required input
  CSV를 한 번 더 고정하고, R8 first-blocked receipt diagnostics도 전달한다.
  R9도 `product_goal_engine_refinement_claim_evidence_receipt_first_blocked_*`와
  첫 `resolve_refine_tier_claim_promotion_blocker` action row의
  `claim_evidence_receipt_first_blocked_*` 필드로
  `public_benchmark_gate_not_ready` receipt 실패 원인을 직접 표시한다.
  `runs/goal_bottleneck_briefing_current.json`도 같은
  summary를 흡수해 R8/R9 completion-audit 병목 브리핑에서 operator handoff
  receipt 묶음이 사라지지 않게 한다. 최신 briefing은
  `engine_refinement_claim_evidence_priority_packet_current.json`도 source artifact로
  읽어 R9 행과 summary에 `coordinate_validation_pass_row_count=0`,
  `metric_materialization_candidate_ready_count=0`,
  `planned_metric_source_payload_count=51`,
  `existing_metric_source_payload_count=0`,
  `required_metric_source_payloads=dockq;lddt_pli;internal_deltaG`, 그리고
  `metric_source_templates_template_row_count=51`,
  `metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `metric_source_templates_metric_source_payload_fill_blocked_row_count=51`, 그리고
  `coordinate_fetch_r4_preflight_ready=true`,
  `coordinate_fetch_r4_ready_for_review_row_count=17`,
  `coordinate_fetch_r4_fetch_required_row_count=17`,
  `coordinate_fetch_r4_download_executed=false`, 그리고
  `Review the R4 coordinate-fetch preflight` top step을 직접 노출한다.
  source-of-truth의
  `goal_bottleneck_briefing_semantic_ready` row는 entry count 2, template present
  2/2, approval token 2개, 두 source gate status, 두 required input CSV와 함께
  이 R9 metric-materialization 수치도 exact field로 검증한다. `/goal/status`도 같은 값을
  `operator_intake_kit_full_commercial_evidence_receipt_*` 및
  `bottleneck_briefing_full_commercial_evidence_receipt_*` 필드로 전달하며,
  handoff chain의 first-blocked diagnostics는
  `operator_intake_kit_product_goal_*_evidence_receipt_first_blocked_*`와
  `bottleneck_briefing_product_goal_*_evidence_receipt_first_blocked_*` API 키로
  별도 고정된다.
  `runs/product_scope_breadth_evidence_priority_packet_current.json`은 같은 R8
  blocker를 15개 open item으로 분해하고
  `product_scope_breadth_evidence_priority_packet_ready`,
  `scientific_evidence_request_count=11`, `local_crosscheck_candidate_count=11`,
  `review_only_keep_blocked_count=1`을 기록한다. 현재 첫 실제 조치는
  `top_item_id=AQP1.core_binder_01`,
  `top_domain=transporter`,
  `top_bucket=local_crosscheck_review_present_but_exact_quant_required`,
  `top_required_evidence_type=exact_transporter_target_pair_quantitative_binder_kcal`
  이며, `runs/transporter_manual_review_intake_template_current.json`과
  `runs/transporter_binder_promotion_gate_current.json`을 통해 local crosscheck를
  exact transporter target-pair quantitative binder kcal evidence로 검토하는 일이다.
  이 priority packet summary는 goal operator intake kit, bottleneck briefing,
  source-of-truth exact semantic checks, `/goal/status`까지
  `product_scope_breadth_evidence_priority_*` 필드로 전파되어 R8 첫 evidence task가
  receipt/matrix 뒤로 숨지 않는다. scope promotion과 authoritative apply는 계속
  false이고 external mutation도 발생하지 않는다.
  같은 R8 receipt 상태는
  `runs/product_commercial_readiness_operator_packet_current.json`과
  `runs/product_commercial_readiness_handoff_bundle_current.json` summary의
  `product_scope_breadth_evidence_receipt_*` 필드 및
  `/product/commercial-readiness-operator-packet`,
  `/product/commercial-readiness-handoff-bundle`,
  `/product/scope-breadth-evidence-receipt` API surface로도 전파된다.
  handoff bundle은 `runs/product_scope_breadth_evidence_receipt_current.json`과
  `config/product_scope_breadth_evidence_receipt_current.csv`를
  `local_scope_breadth_receipt` / `local_scope_breadth_receipt_template`
  artifact reference로 추적하며, 최신
  `local_missing_artifact_reference_count=0`, `local_required_artifact_reference_count=39`,
  `artifact_reference_count=43`이다. 여기에 AQP1 첫 return bundle의
  `local_scope_transporter_p0_return_bundle_artifact` 5종도 포함되며,
  `config/ligand_binding_reference_blind_aqp1_v1.csv`,
  `config/ligand_eval_splits_blind_aqp1_v1.csv`,
  `config/ligand_meta_blind_aqp1_v1.csv`,
  `runs/transporter_binder_promotion_gate_current.json`까지 handoff manifest에서
  required-local artifact로 빠지지 않는다. 또한 AQP1 direct-binding external
  evidence의 `operator_fill_guide`, `operator_worksheet`,
  `operator_staging_apply` 3종도
  `local_scope_transporter_p0_external_operator_*` reference로 올라가며,
  현재 worksheet는 `operator_fill_pending_field_count=19`, staging preview는
  `live_apply_allowed=false`, `validation_error_count=2`라 claim-safe apply가
  계속 차단된다. Production AI guarded registry promotion도
  `runs/production_ai_registry_promotion_operator_field_worksheet_current.json`을
  `local_production_ai_registry_promotion_field_worksheet` reference로 포함하며,
  현재 `operator_fill_pending_field_count=13`,
  `diagnostic_required_pending_field_count=6`, `top_gate_id=default_residual_mode_guarded`,
  `operator_fill_complete=false`, `model_promoted=false`,
  `customer_facing_mutation_enabled=false`, `external_state_mutated=false`로
  실제 registry promotion과 operator field handoff를 분리한다. 또한
  `runs/production_ai_registry_promotion_operator_staging_apply_current.json`을
  `local_production_ai_registry_promotion_staging_apply_preview` reference로 포함하며,
  현재 `blocked_production_ai_registry_promotion_operator_staging_apply`,
  `candidate_receipt_ready=false`, `candidate_blocked_row_count=1`,
  `staging_placeholder_row_count=1`, `field_worksheet_pending_field_count=13`,
  `field_worksheet_diagnostic_required_pending_field_count=6`,
  `candidate_first_blocked_artifact_id=residual_model_registry_guarded_promotion`,
  `candidate_first_blocked_row_blocker=operator_placeholders_unfilled`,
  `candidate_observed_registry_default_residual_mode=shadow`,
  `candidate_observed_registry_trained_model_checkpoint_count=1`,
  `live_copy_allowed=false`, `canonical_receipt_written=false`,
  `registry_edited_by_this_tool=false`, `model_promoted=false`,
  `external_state_mutated=false`로 canonical receipt copy와 실제 registry promotion을
  계속 fail-closed로 분리한다. R8 full-scope
  evidence도
  `runs/product_scope_breadth_evidence_operator_field_worksheet_current.json`을
  `local_scope_breadth_field_worksheet` reference로 포함하며,
  현재 `receipt_field_row_count=72`,
  `operator_fill_pending_field_count=36`,
  `top_blocker_id=direct_binding_evidence_missing`,
  `top_blocker_pending_field_count=6`, `top_item_id=AQP1.core_binder_01`,
  `top_bucket=local_crosscheck_review_present_but_exact_quant_required`,
  `priority_open_item_count=15`,
  `priority_local_crosscheck_candidate_count=11`,
  `scope_checklist_manual_review_subcheck_count=39`,
  `claim_promoted=false`, `external_state_mutated=false`로 scope-breadth receipt
  6개 row를 field-level operator handoff로 분리한다. 또한
  `runs/product_scope_breadth_evidence_operator_staging_apply_current.json`을
  `local_scope_breadth_staging_apply_preview` reference로 포함하며, 현재
  `blocked_product_scope_breadth_evidence_operator_staging_apply`,
  `candidate_receipt_ready=false`, `candidate_blocked_row_count=6`,
  `staging_placeholder_row_count=6`,
  `field_worksheet_pending_field_count=36`,
  `candidate_first_blocked_scope_blocker_id=direct_binding_evidence_missing`,
  `candidate_most_common_row_blocker=operator_placeholders_unfilled`,
  `live_copy_allowed=false`, `canonical_receipt_written=false`,
  `external_state_mutated=false`라 operator가 채운 staging receipt가 pass하기 전에는
  canonical R8 receipt copy가 차단된다. R9 engine-refinement
  claim evidence도
  `runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json`을
  `local_engine_refinement_claim_field_worksheet` reference로 포함하며,
  현재 `worksheet_field_row_count=389`,
  `operator_fill_pending_field_count=296`,
  `receipt_operator_fill_pending_field_count=36`,
  `public_benchmark_work_order_pending_field_count=56`,
  `top_blocker_id=public_benchmark_gate_not_ready`,
  `top_priority_bucket=public_benchmark_work_order_apply_required`,
  `top_blocker_pending_field_count=266`, `claim_promoted=false`,
  `external_engine_calls_executed=false`, `external_state_mutated=false`로
  public benchmark work-order 8개와 claim evidence receipt 6개 row를 field-level로
  분리한다. 2026-06-14 최신 worksheet는 claim-grade statistical support work-order의
  17개 expansion slot도 `public_benchmark_statistical_support_expansion` field row로
  펼쳐 `public_benchmark_statistical_support_expansion_slot_row_count=17`,
  `public_benchmark_statistical_support_expansion_holdout_slot_count=5`,
  `public_benchmark_statistical_support_expansion_fit_or_holdout_slot_count=12`,
  `public_benchmark_statistical_support_expansion_field_count=221`,
  `public_benchmark_statistical_support_expansion_pending_field_count=204`,
  `public_benchmark_statistical_support_expansion_ready_field_count=17`을 summary에
  고정한다. 또한 metric source template artifact를 직접 읽어
  `public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count=0`,
  `public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total=0`도
  R9 worksheet summary/source artifact에 고정한다. 같은 worksheet는
  `runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json`도
  직접 읽어
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count=17`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count=0`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count=187`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download=false`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed=false`,
  `public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`를
  summary/source artifact에 고정한다. 같은 worksheet는
  `runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json`도
  직접 읽어
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed=false`,
  `public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`를
  summary/source artifact에 고정한다. 즉 R9의 남은 과학/정확도 병목은 기존 8개 pair의 metric source path뿐
  아니라, 최소 17개 추가 public benchmark pair와 그중 5개 holdout pair를 채워
  bootstrap Spearman p05 >= 0.5를 재검증해야 하는 통계 support 결손까지 operator-facing
  worksheet에 직접 노출된다. 또한
  receptor-coordinate intake/validation CSV와 metric evidence CSV를 함께 읽어
  `public_benchmark_receptor_coordinate_intake_row_count=8`,
  `public_benchmark_receptor_coordinate_intake_artifact_present_row_count=8`,
  `public_benchmark_receptor_coordinate_validation_blocked_row_count=0`,
  `public_benchmark_metric_evidence_blocked_row_count=8`,
  DockQ/lDDT-PLI/internal ΔG source artifact missing count `8/8/8`,
  `public_benchmark_metric_evidence_missing_required_input_artifact_row_count=0`,
  `public_benchmark_metric_evidence_missing_required_input_artifact_sha256_row_count=0`,
  `public_benchmark_science_evidence_complete=false`도 같은 worksheet summary와
  CSV row context에 붙인다. 각 work-order row에는 예를 들어
  `3udh_protein.pdb`, `3udh_receptor.cif`, `3udh_complex.pdb` 같은 accepted
  offline coordinate filename pattern과 `pdbbind/3udh/3udh_protein.pdb`,
  `pdbbind/3udh/3udh_receptor.cif`, `casf/3udh/3udh_complex.pdb` 같은 archive
  member example이 같이 기록된다. 따라서 operator가 work-order value를 채워도
  metric source artifact evidence가 pass하지 않으면 `operator_fill_complete`가
  열리지 않는다. receptor-coordinate intake row에는
  RCSB mmCIF/PDB URL, 추천 로컬 coordinate path queue, 그리고
  `confirm_public_coordinate_source_license_and_native_receptor_or_complex_chain_assembly_matches_pose_target`
  review requirement도 같이 붙는다. 이 work-order는 현재 로컬
  metric evidence handoff도 `runs/refine_tier_public_benchmark_metric_sources/{work_order_id}_dockq.json`,
  `{work_order_id}_lddt_pli.json`, `{work_order_id}_internal_deltaG.json`와
  `metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls`
  schema, 그리고 `required_metric_input_artifacts`/`required_metric_input_artifact_sha256s`
  계약을 각 field row 옆에 붙여, DockQ/lDDT-PLI/internal ΔG source가
  어떤 로컬 JSON과 어떤 ligand/receptor 입력 artifact로 검토돼야 하는지 드러낸다.
  또한 각 field row에는
  `metric_*_source_payload_valid`와 `metric_*_source_payload_blockers`가 붙어,
  source file이 존재하더라도 payload schema나 target/pose/value/license/no-external-call
  조건, 또는 payload가 가리키는 로컬 `input_artifacts` 존재/sha256/required-input
  조건이 틀리면
  operator가 바로 invalid reason을 볼 수 있다.
  `runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv`에서 PDBBind/CASF
  pose RMSD/provenance 8개 row를 seed해 operator field 96개 중 40개를 선채움하고,
  license 확인, DockQ, lDDT-PLI, internal refine ΔG, 그리고 세 metric의 source
  artifact 경로 56개 field만 pending으로 남긴다. 또한
  `runs/engine_refinement_claim_evidence_operator_staging_apply_current.json`을
  `local_engine_refinement_claim_staging_apply_preview` reference로 포함하며,
  현재 `blocked_engine_refinement_claim_evidence_operator_staging_apply`,
  `candidate_receipt_ready=false`, `candidate_receipt_blocked_row_count=6`,
  `candidate_public_benchmark_work_order_ready=false`,
  `candidate_public_benchmark_blocked_row_count=8`,
  `staging_receipt_placeholder_row_count=6`,
  `staging_public_benchmark_work_order_placeholder_row_count=8`,
  `candidate_public_benchmark_receptor_coordinate_validation_contract_blocked_row_count=0`,
  `metric_evidence_contract_blocked_row_count=8`,
  `candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count=0`,
  `candidate_public_benchmark_metric_evidence_missing_required_receptor_input_row_count=0`,
  `candidate_public_benchmark_metric_evidence_required_input_sha256_blocked_row_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_ready=true`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_row_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count=136`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count=17`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count=17`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count=0`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count=187`,
  `field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`,
  `field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`,
  `live_copy_allowed=false`, `public_benchmark_intake_write_allowed=false`,
  `canonical_receipt_written=false`, `public_benchmark_intake_written=false`,
  `external_engine_calls_executed=false`, `external_state_mutated=false`라 operator가
  채운 R9 receipt/work-order row가 pass하더라도 target/pose/source-artifact contract
  재검증을 통과하기 전에는 canonical R9 receipt copy와 tracked public benchmark intake
  write가 차단된다.
  `product_release_source_of_truth_gate_current.json`은 이제
  `product_api_contract_current.json`,
  `product_service_boundary_contract_current.json`,
  `self_hosted_license_distribution_audit_current.json`,
  `third_party_license_review_gate_current.json`,
  `product_scope_breadth_closure_checklist_current.json`,
  `product_scope_breadth_evidence_receipt_current.json`,
  `product_scope_breadth_evidence_priority_packet_current.json`,
  `goal_operator_intake_kit_current/manifest.json`,
  `product_commercial_readiness_execution_ladder_current.json`,
  `goal_api_surface_contract_current.json`, `goal_bottleneck_briefing_current.json`,
  `product_full_commercial_blocker_evidence_matrix_current.json`,
  `production_ai_registry_promotion_operator_receipt_current.json`,
  `production_ai_registry_promotion_priority_packet_current.json`,
  `production_ai_registry_promotion_operator_field_worksheet_current.json`,
  `production_ai_registry_promotion_operator_staging_apply_current.json`,
  `product_quality_gate_verification_current.json`,
  `product_pose_sampling_readiness_current.json`,
  `refine_tier_public_benchmark_readiness_current.json`,
  `refine_tier_public_benchmark_work_order_apply_current.json`,
  `refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json`,
  `engine_refinement_claim_evidence_priority_packet_current.json`,
  `engine_refinement_claim_evidence_operator_field_worksheet_current.json`,
  `engine_refinement_claim_evidence_operator_staging_apply_current.json`,
  `product_scope_breadth_evidence_operator_staging_apply_current.json`,
  `gpcr_commercial_phase_ab_closure_chain_current.json`,
  `gpcr_active_scorer_promotion_decision_packet_current.json`,
  `gpcr_broad_claim_scope_readiness_current.json`,
  `science_accuracy_frontier_current.json`,
  `cameo_official_result_fetch_preflight_current.json`,
  `cameo_validation_operations_dossier_current.json`을
  freshness row 및 semantic-ready row로 함께 검증해, R8 receipt와 상용 readiness
  handoff 입력 순서, 상위 상태 API/병목 브리핑 자체가 릴리스 freshness 감시 밖으로
  빠지지 않게 한다. 최신 source-of-truth는 `row_count=149`, `pass_count=149`,
  `blocker_count=0`, `artifact_row_count=93`, `semantic_status_row_count=54`,
  `release_refresh_command_count=118`, `stale_artifact_count=0`,
  `semantic_status_blocker_count=0`, `readme_drift_count=0`이다.
  final refresh는 마지막 `goal_release_decision_gate` 뒤에
  `goal_operator_action_board`, `goal_release_burndown_work_order`, intake kit,
  bottleneck briefing, full commercial matrix, release bundle, handoff bundle,
  privacy scan, source-of-truth gate까지 downstream 산출물을 한 번 더 재생성하고,
  refresh runner final gate는 source-of-truth, quality gate verification,
  release decision, action board 4개 surface를 검증한다. source-of-truth final gate는 `row_count=149`,
  `pass_count=149`, `artifact_row_count=93`, `semantic_status_row_count=54`,
  `readme_row_count=2`, `release_refresh_command_count=118`를 exact-check해
  downstream readiness row가 조용히 빠지는 회귀를 막고,
  `product_quality_gate_verification_current.json` final gate는
  `product_quality_gate_verified`, `quality_gate_ready=true`,
  `check_count=4`, `pass_count=4`, `blocker_count=0`을 직접 검증한다.
  최신 `goal_release_decision_gate_current.json`도 같은 receipt를 직접 읽어
  `product_quality_gate_verification_recorded=true`,
  `product_quality_gate_verification_ready=true`,
  `product_quality_gate_verification_status=product_quality_gate_verified`,
  `product_quality_gate_verification_source_contract_status=product_operational_quality_contract_ready`,
  `product_quality_gate_verification_check_count=4`,
  `product_quality_gate_verification_pass_count=4`,
  `product_quality_gate_verification_blocker_count=0`,
  `product_quality_gate_verification_execution_enabled=false`,
  `product_quality_gate_verification_external_state_mutated=false`를 노출하고,
  `/goal/status`는 이 필드를 release decision에서 그대로 전파한다. 따라서
  operational quality verifier가 release bundle/source-of-truth/final refresh 안에만
  머물지 않고 operator-facing decision surface에서도 직접 확인된다.
  action board echo는
  `goal_release_decision_gate_status=goal_release_ready`,
  `goal_release_allowed=true`, `goal_release_blocker_count=0`이어야 하므로
  operator-facing 보드가 한 cycle 전 release-decision 상태를 들고 있어도
  verified refresh로 통과하지 않는다. 이 ready는 restricted independent release
  기준이며, full-commercial claim은 readiness/frontier에서
  `full_commercial_release_allowed=false`와 R8/R9/ACCURACY blocker로 별도 잠긴다.
  `goal_bottleneck_briefing`은 burndown row의 `release_observed`/`release_required`
  문자열을 최신 release-decision row에서 보정해, R8/R9 completion-audit blocker
  수가 한 사이클 전 값으로 operator-facing 병목표에 남지 않게 한다.
  최신 goal release decision과 final refresh도 self-hosted license audit 및
  third-party license review gate를 직접 읽어 `legal_advice_provided=false`,
  `hard_blocker_count=0`, `operator_review_item_count=1`, JSZip approved asset,
  operator review CSV/approval token, no asset/external mutation을 exact check로
  요구한다.
  `product_pose_sampling_readiness_semantic_ready` row는 deterministic local
  pocket placement, 6-start pose ensemble, RMSD diversity surface, bounded
  cross-docking/induced-fit guard, claim-grade pose accuracy blocked posture를
  exact/min field로 검증한다. 따라서 product AI decision graph의
  `pose_generation_contract` node는 capability/preflight만 보지 않고 실제 local
  pose sampling smoke artifact를 요구하며, `/product/pose-sampling-readiness`
  API surface도 같은 artifact와 claim-grade blocked posture를 노출한다. 최신
  `goal_release_decision_gate_current.json`도 같은 artifact를 직접 읽어
  `product_pose_sampling_readiness_recorded=true`,
  `product_pose_sampling_readiness_ready=true`,
  `product_pose_sampling_readiness_pose_count=6`,
  `product_pose_sampling_readiness_cluster_count=6`,
  `product_pose_sampling_readiness_cross_docking_pose_count=4`,
  `product_pose_sampling_readiness_claim_grade_pose_accuracy_ready=false`,
  `product_pose_sampling_readiness_docking_results_emitted=false`,
  `product_pose_sampling_readiness_execution_enabled=false`,
  `product_pose_sampling_readiness_external_state_mutated=false`를 노출하고,
  `/goal/status`와 final refresh exact check가 이 값을 그대로 검증한다. 따라서
  local pose sampling smoke가 release bundle/source-of-truth/product API 안에만
  머물지 않고 operator-facing release decision surface에서도 직접 확인된다.
  API/service-boundary semantic readiness와 self-hosted license audit semantic
  readiness도 이 source-of-truth 안으로 편입됐다. 고객-facing AI report explanation/UX semantic
  readiness는 core/full decision graph 순환을 분리한 뒤 닫혔다. R8/R9 evidence
  receipt 자체도 각각 `product_scope_breadth_evidence_receipt_blocked_semantic_ready`,
  `product_scope_breadth_evidence_operator_field_worksheet_semantic_ready`,
  `engine_refinement_claim_evidence_receipt_blocked_semantic_ready`,
  `engine_refinement_claim_evidence_priority_packet_blocked_semantic_ready`,
  `engine_refinement_claim_evidence_operator_field_worksheet_semantic_ready`,
  `engine_refinement_claim_evidence_operator_staging_apply_blocked_semantic_ready` row로 고정되어
  placeholder evidence, 6/6 blocked rows, R8 field-level pending count 36개,
  public benchmark work-order 8개 row, R9 field-level pending count 296개,
  public benchmark work-order pending count 56개,
  R9 receptor-coordinate validation pass 8개/blocked 0개,
  tracked R9 metric-evidence blocked 8개와 materialized metric-evidence pass 8개,
  metric evidence required ligand/receptor input artifact missing 0개,
  tracked DockQ/lDDT-PLI/internal ΔG source missing 8/8/8개,
  materialized DockQ/lDDT-PLI/internal ΔG source payload 24개,
  claim-grade statistical support expansion slot 17개와 holdout slot 5개,
  statistical support candidate queue 17개, candidate queue holdout 5개,
  ligand pose/experimental ΔG prefill 17/17개, receptor coordinate missing 17/17개,
  statistical support coordinate intake 17개, coordinate validation pass 0개/blocked 17개,
  statistical support coordinate fetch required 17개/ready-for-validation 0개,
  statistical support coordinate fetch apply preview preflight pass 17개/downloaded 0개,
  statistical support metric source template 51개/fill-ready 0개/fill-blocked 51개,
  statistical support expansion field 221개/pending 204개/ready split 17개,
  approval token requirement, first-blocked diagnostics가 source-of-truth에서 직접 검증된다. production AI
  checkpoint/promotion workbench는 현재 `shadow`/blocked 상태를 semantic-ready row로
  검증하고, `production_ai_registry_promotion_operator_staging_apply_blocked_semantic_ready`
  row는 guarded promotion candidate receipt가 아직 blocked preview임을 검증한다.
  API runner profile operator receipt, production AI registry promotion
  operator receipt, production AI registry promotion priority packet도 blocked 상태,
  첫 row blocker, 첫 priority gate를 semantic-ready row로 검증한다. 같은 priority
  top gate는 `goal_operator_intake_kit_current/manifest.json` summary와
  `goal_bottleneck_briefing_current.json` summary에도
  `production_ai_registry_promotion_priority_*` 필드로 흡수되며, source-of-truth의
  intake-kit/bottleneck semantic rows가 packet ready, 3개 missing gate, top gate
  `default_residual_mode_guarded`를 exact field로 검증한다.
  최신 goal API surface contract는 `check_count=9`,
  `pass_count=9`, `missing_full_commercial_visibility_token_count=0`이다.
  source-of-truth의 `goal_api_surface_contract_semantic_ready` row도
  `missing_status_key_count=0`, `missing_full_commercial_visibility_token_count=0`,
  `missing_fail_closed_flag_count=0`, `blocker_count=0`을 exact field로 검증한다.
  같은 source-of-truth는 CAMEO official-result fetch preflight도
  `blocked_cameo_official_result_fetch_preflight` semantic-ready row로 직접 검증해
  `operator_fetch_csv_present=false`, `network_request_opened=false`,
  `official_results_fetched=false`,
  `fetch_approval_token_required=APPROVE_CAMEO_OFFICIAL_RESULT_FETCH`가 drift하지 않게 한다.
  최신 `goal_release_decision_gate_current.json`도 같은 preflight를
  `cameo_official_result_fetch_preflight_*` summary와 recorded row로 직접 흡수하며,
  final refresh exact check가 blocked status, blocked row count, operator intake/template
  CSV, approval token, no-network/no-fetch/no-local-native flags를 고정한다.
  `product_ledger_privacy_scan_current.json`도 goal-facing JSON artifacts
  (`goal_readiness_rollup`, `goal_operator_action_board`, `goal_operator_intake_kit`,
  `goal_release_burndown_work_order`,
  `goal_api_surface_contract`, `goal_bottleneck_briefing`,
  `product_full_commercial_blocker_evidence_matrix`,
  `product_scope_breadth_evidence_priority_packet`,
  `engine_refinement_claim_evidence_priority_packet`,
  `production_ai_registry_promotion_operator_receipt`,
  `production_ai_registry_promotion_priority_packet`)를 scan 대상 및
  source-of-truth dependency로 포함해, R8/R9 상위 API/병목 surface에 raw molecular
  payload가 섞이면 release gate에서 숨지 않게 한다. 최신 scan은 `leak_count=0`이다.
  최신 `goal_release_decision_gate_current.json`과 `/goal/status`도 같은 scan을 직접 읽어
  `product_ledger_privacy_scan_recorded=true`,
  `product_ledger_privacy_scan_ready=true`,
  `product_ledger_privacy_scan_scan_file_count>=285`,
  `product_ledger_privacy_scan_scan_glob_count=24`,
  `product_ledger_privacy_scan_pass_count=scan_file_count`,
  `product_ledger_privacy_scan_leak_count=0`,
  `product_ledger_privacy_scan_invalid_json_count=0`,
  `product_ledger_privacy_scan_execution_enabled=false`,
  `product_ledger_privacy_scan_external_state_mutated=false`를 노출하며, final refresh
  exact check가 이 no-leak/no-mutation privacy receipt의 드리프트를 차단한다.
  `tools/product/build_refine_tier_public_benchmark_readiness.py`는 curated 공개
  pose/free-energy benchmark intake를 별도 fail-closed gate로 고정한다.
  `config/refine_tier_public_benchmark_intake_current.csv`는 required column header를
  tracked template로 제공한다. 현재 기본 artifact는
  `runs/refine_tier_public_benchmark_readiness_current.json`이며,
  `status=blocked_refine_tier_public_benchmark_readiness`,
  `input_csv_present=true`, `row_count=0`, `valid_row_count=0`,
  `claim_grade_public_benchmark_ready=false`, `blocker_count=6`,
  `operator_work_order_ready=true`, `work_order_row_count=8`로 실제 curated
  benchmark row 입력만 아직 없음을 명확히 드러낸다.
  최신 `goal_release_decision_gate_current.json`, `/goal/status`,
  `/goal/release-decision`도 이 원본 readiness를 직접 노출해
  `refine_tier_public_benchmark_recorded=true`,
  `refine_tier_public_benchmark_status=blocked_refine_tier_public_benchmark_readiness`,
  `row_count=0`, `valid_row_count=0`, `pose_metric_pass_count=0`,
  `free_energy_pair_count=0`, `blocker_count=6`,
  `write_intake_approval_token_required=APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE`,
  `external_state_mutated=false`를 고정한다. final refresh는 이 값들을
  true/zero/exact/text check로 재검증해 curated public benchmark가 아직
  입력되지 않았다는 fail-closed 상태가 drift되면 release를 차단한다.
  같은 blocker/work-order 상태는 engine readiness summary에도
  `public_benchmark_blockers`, `public_benchmark_next_required_step`로 반영된다.
  같은 builder는 `runs/refine_tier_public_benchmark_work_order_current.csv`에
  최소 5개 fit row + 3개 holdout row를 채우기 위한 operator work-order를
  생성한다. 현재 work-order는 로컬 PDBBind/CASF pose-affinity scorecard에서
  `work_order_seeded_row_count=8`, `work_order_prefilled_operator_field_count=40`,
  `work_order_pending_operator_field_count=56`,
  `work_order_experimental_deltaG_prefilled_count=8`을 기록해 benchmark id, target id,
  provenance id, pose RMSD, PDBBind pAffinity 기반 public experimental ΔG를 먼저 채운다.
  field-level 잔여분은 license 확인 8개, DockQ 8개, lDDT-PLI 8개,
  internal refine ΔG 8개, DockQ source artifact 8개, lDDT-PLI source artifact 8개,
  internal refine ΔG source artifact 8개이며 experimental ΔG pending은 0개다. 현재 로컬 source
  scan은 receptor coordinate file 0개, tar 내부 receptor coordinate member 0개,
  seed interaction metric column 0개, seed internal ΔG column 0개,
  `work_order_current_local_source_prefill_ready_field_count=0`으로 고정된다.
  추가 science-input gap CSV는 ligand pose artifact present 8개,
  missing ligand pose 0개, missing receptor coordinate 8개,
  missing interaction metric source 8개, missing internal ΔG source 8개를 기록한다.
  따라서 나머지는 public provenance/license 확인과 receptor-bound interaction metric,
  internal refine ΔG 입력 후 tracked intake CSV로 옮겨 재검증하는 절차만 제공하며
  외부 다운로드/도킹/MD 실행은 하지 않는다.
  `tools/product/apply_refine_tier_public_benchmark_work_order.py`는 operator-filled
  work-order CSV를 intake candidate로 변환하기 전에 placeholder, license,
  external-engine call, pose/free-energy fields를 fail-closed로 검증한다.
  tracked intake CSV를 실제 갱신하는 `--write-intake`는
  `APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE` 승인 토큰까지 요구한다. 현재 seeded
  work-order 기준 산출물
  `runs/refine_tier_public_benchmark_work_order_apply_current.json`은
  `blocked_refine_tier_public_benchmark_work_order_apply`, `work_order_row_count=8`,
  `blocked_row_count=8`, `candidate_intake_written=false`, `intake_written=false`이다.
  같은 apply artifact도 release/API 표면에
  `refine_tier_public_benchmark_work_order_apply_recorded=true`,
  `aggregate_readiness_required=true`, `apply_ready=false`,
  `blocked_row_count=8`, `valid_intake_row_count=0`,
  `candidate_intake_written=false`, `candidate_readiness_checked=false`,
  `write_intake_requested=false`, `approval_token_present=false`,
  `approval_token_accepted=false`, `external_state_mutated=false`로 직접 올라오며,
  final refresh exact/zero/text check가 승인 없는 intake write나 candidate mutation을
  자동 차단한다.
  다음 S-class 작업은 metal/cofactor calibrated parameterization 및 coverage expansion,
  charged-residue formal protonation-state assignment, calibrated atom-level charge/torsion/improper parameterization,
  solvent/FEP public-pair calibration,
  `config/refine_tier_public_benchmark_intake_current.csv` 수준의 curated 공개
  pose/free-energy benchmark row 입력 및 gate 통과, OpenMM parity gate로 남는다.

### A-2. Production AI 추론 주체 전환 (ROCm/HIP production_guarded)

**현재 상태**
- `runs/product_production_ai_checkpoint_readiness_current.json`은
  `blocked_product_production_ai_checkpoint_readiness`,
  `production_ai_checkpoint_ready=false`,
  `production_ai_inference_subject_active=false`,
  `production_gpu_execution_environment_ready=true`,
  `delta_force_derivation_validation_ready=true`,
  `default_residual_mode=shadow`,
  `production_promotion_allowed=false`,
  `trained_model_checkpoint_count=1`을 기록한다. 따라서 trained/preflight-ready
  checkpoint 등록 부재는 더 이상 첫 병목이 아니며, guarded registry promotion
  operator receipt가 다음 경계다.
- ROCm/HIP 환경은 `rocm_environment_manifest_ready`이며,
  `torch_version=2.6.0+rocm6.1`, `torch_hip_version=6.1.40091-a8dbc0c19`,
  `visible_device_count=1`, AMD GPU detected로 기록되어 있다.
- production inference acceptance matrix는 `8`개 stage 중 `7`개 ready이고,
  남은 blocked stage는 `registry_guarded_promotion_acceptance` 하나다.
  actionable blocker는 `registry_customer_facing_promotion_allowed`이며,
  observed 값은 `default_residual_mode=shadow`,
  `production_promotion_allowed=false`, customer-facing score/ranking mutation
  disabled, `trained_model_checkpoint_count=1`이다.
  `first_failed_next_action`과
  `production_inference_actionable_blocker_next_action`은 이제 이미 ready인
  ROCm/GPU receipt/training/preflight를 다시 요구하지 않고,
  `production_promotion_allowed`, `customer_facing_mutation_flags`,
  `default_residual_mode_guarded`를 남은 registry gate로 직접 지목한다.
  `trained_model_checkpoint_count_positive`는 만족된 gate로 보존된다. 같은 정보는
  `registry_promotion_missing_gate_ids`, `registry_promotion_missing_gate_count`,
  `registry_promotion_upstream_acceptance_ready`,
  `registry_promotion_currently_satisfied` 구조화 필드로도 고정되어,
  API/goal audit 소비자가 next-action 문자열을 파싱하지 않아도 된다.
  같은 registry promotion 필드는 `/goal/status`에도
  `production_ai_checkpoint_registry_promotion_*` 키로 전파되어, 운영자용 상위
  상태 API에서 남은 AI registry gate와 upstream acceptance 상태가 숨지 않는다.
  또한 actionable blocker가 `registry_guarded_promotion_acceptance`인 경우
  checkpoint-readiness summary는
  `residual_model_registry_guarded_promotion` operator completion packet을
  반환한다. 이 packet은 `production_promotion_allowed`, customer-facing mutation
  flags, guarded `default_residual_mode`, positive `trained_model_checkpoint_count`,
  validation chain을 구조화하되 실제 checkpoint 생성/registry promotion은 수행하지 않는다.
  `/goal/status`도 이 packet의 ready flag, artifact id, required fields, diagnostic
  commands, completion rule, next action을 노출한다.
  `goal_operator_action_board_current.json`의 primary action도 더 이상 ready GPU return을
  재요구하지 않고 `complete_residual_registry_guarded_promotion`을 가리킨다.
  `goal_operator_intake_kit_current/manifest.json`은
  `production_ai_registry_promotion` entry를 operator input required로 surface하며,
  `config/production_ai_registry_promotion_operator_receipt_current.csv`와
  `runs/production_ai_registry_promotion_operator_receipt_current.json`을 연결한다.
  이 receipt는 현재 `blocked_production_ai_registry_promotion_operator_receipt`,
  `operator_receipt_ready=false`, `first_blocked_row_blocker=operator_placeholders_unfilled`,
  `approval_token_required=APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION`,
  `observed_registry_default_residual_mode=shadow`,
  `observed_registry_trained_model_checkpoint_count=1`으로 fail-closed 상태를 기록하며,
  registry/checkpoint-readiness artifact와 CSV 입력값이 일치하지 않으면 ready가 되지 않는다.
  `runs/production_ai_registry_promotion_priority_packet_current.json`은 같은 병목을
  operator 실행 순서로 다시 분해해
  `blocked_production_ai_registry_promotion_priority_packet`,
  `priority_packet_ready=true`, `priority_item_count=4`,
  `operator_input_required_count=3`, `top_gate_id=default_residual_mode_guarded`,
  `top_priority_bucket=guarded_residual_mode_selection_required`,
  `registry_promotion_missing_gate_ids=[default_residual_mode_guarded, production_promotion_allowed,
  customer_facing_mutation_flags]`를 기록한다. 따라서 Production AI promotion의 첫
  실제 조치는 shadow registry를 바로 켜는 일이 아니라, preflight-ready checkpoint
  1개를 전제로 guarded default residual mode, approval token, reviewer,
  validation-chain review를 operator receipt에 채우고 residual
  registry/checkpoint-readiness/promotion workbench/operator receipt를 재검증하는
  일로 고정된다. 이 priority packet도
  `model_promoted=false`, `customer_facing_mutation_enabled=false`,
  `external_state_mutated=false`로 fail-closed다.
  `runs/production_ai_registry_promotion_operator_field_worksheet_current.json`은
  같은 receipt CSV를 field-level operator worksheet로 분해해
  `production_ai_registry_promotion_operator_field_worksheet_ready`,
  `worksheet_field_row_count=20`, `required_receipt_field_count=19`,
  `operator_fill_pending_field_count=13`,
  `diagnostic_required_field_count=6`,
  `diagnostic_required_pending_field_count=6`,
  `top_gate_id=default_residual_mode_guarded`,
  `observed_registry_default_residual_mode=shadow`,
  `observed_registry_trained_model_checkpoint_count=1`을 기록한다.
  이 worksheet는 ready artifact지만 `operator_fill_complete=false`,
  `model_promoted=false`, `customer_facing_mutation_enabled=false`,
  `external_state_mutated=false`라 운영자 입력 칸 정리와 실제 registry promotion을
  분리한다.
  `runs/production_ai_registry_promotion_operator_staging_apply_current.json`은 같은
  guarded receipt를 canonical copy 전에 preview 검증하는 apply surface로,
  현재 `blocked_production_ai_registry_promotion_operator_staging_apply`,
  `candidate_receipt_ready=false`, `candidate_blocked_row_count=1`,
  `candidate_first_blocked_artifact_id=residual_model_registry_guarded_promotion`,
  `candidate_first_blocked_row_blocker=operator_placeholders_unfilled`,
  `field_worksheet_pending_field_count=13`,
  `field_worksheet_diagnostic_required_pending_field_count=6`,
  `live_copy_allowed=false`, `canonical_receipt_written=false`,
  `registry_edited_by_this_tool=false`, `model_promoted=false`,
  `external_state_mutated=false`다. 따라서 operator가 receipt를 채워 candidate gate가
  통과하기 전에는 canonical receipt CSV와 registry state가 바뀌지 않는다.
  최신 `top_verification_command`는
  `python3 tools/build_residual_model_registry.py; python3 tools/build_product_production_ai_checkpoint_readiness.py; python3 tools/build_product_production_ai_promotion_workbench.py; python3 tools/build_production_ai_registry_promotion_operator_receipt.py; python3 tools/product/build_production_ai_registry_promotion_priority_packet.py`로
  registry/checkpoint/workbench/operator receipt/priority packet 재검증을 한 번에
  고정한다.
  이 priority packet, field worksheet, staging apply summary는 이제 goal operator intake kit, bottleneck briefing,
  goal release decision gate, 상용 readiness operator packet, execution ladder,
  handoff bundle, `/goal/status`까지
  `production_ai_registry_promotion_priority_*` 및
  `production_ai_registry_promotion_operator_field_worksheet_*`,
  `production_ai_registry_promotion_operator_staging_apply_*` 필드로 전파된다. release bundle과
  source-of-truth gate도 같은 artifact를 required/depends-on 항목으로 추적해,
  Production AI registry promotion의 첫 gate가 operator intake, 병목 브리핑,
  상위 handoff, 최종 릴리즈 freshness 검사 밖으로 빠지지 않는다.
  최신 goal release decision도 원본 priority packet을 직접 읽어
  `production_ai_registry_promotion_priority_packet_recorded=true`,
  `operator_receipt_status=blocked_production_ai_registry_promotion_operator_receipt`,
  `observed_registry_default_residual_mode=shadow`,
  `observed_registry_trained_model_checkpoint_count=1`을 summary와 final refresh exact
  check에 고정한다.
  또한 최신 goal release decision은 원천
  `product_production_ai_checkpoint_readiness_current.json` 및
  `product_production_ai_promotion_workbench_current.json`도 직접 읽어
  upstream 7/8 acceptance ready, `registry_guarded_promotion_acceptance` blocked
  stage, trained checkpoint count 1, `default_residual_mode=shadow`,
  residual registry/product-goal blocked stages, no promotion/no mutation을 summary/row와
  final refresh exact check로 고정한다.
  `/product/commercial-readiness-operator-packet`,
  `/product/commercial-readiness-execution-ladder`,
  `/product/commercial-readiness-handoff-bundle`,
  `/product/production-ai-registry-promotion-operator-receipt`,
  `/product/production-ai-registry-promotion-priority`는
  `production_ai_registry_promotion_*` alias, completion packet,
  `production_ai_registry_promotion_operator_receipt_*` status/token/observed blocker
  fields를 그대로 전달한다. `/goal/status`도 같은
  `production_ai_registry_promotion_operator_receipt_*` status/token/observed blocker
  fields를 handoff bundle summary에서 끌어와 goal API surface에 고정한다.
  handoff bundle의 artifact reference manifest도
  `runs/production_ai_registry_promotion_operator_receipt_current.json`과
  `config/production_ai_registry_promotion_operator_receipt_current.csv`를 local required
  operator receipt/template으로 포함한다.
- `runs/product_production_ai_promotion_workbench_current.json`도
  `blocked_product_production_ai_promotion_workbench`,
  `production_ai_promotion_ready=false`,
  `post_return_promotion_ladder_blocked_stage_count=2`를 기록한다.
  남은 blocked stage는 `residual_model_registry`,
  `product_goal_completion_audit`이며, workbench `next_required_step`도 같은
  trained production checkpoint registry promotion action과 structured missing
  gate fields를 승계한다.

**병목 원인**
- ROCm/HIP 환경, force derivation validation, training data, selected sidecar,
  checkpoint preflight는 현재 산출물 기준 ready지만, residual registry가 아직
  customer-facing guarded promotion을 허용하지 않는다.
- production AI 추론 주체 전환은 아직 현재 병목이다. 특히 registry promotion,
  trained checkpoint accounting, customer-facing score/ranking mutation policy,
  goal completion audit linkage가 닫혀야 한다.
- fail-closed 경계는 여전히 필요하다. GPU receipt가 있다고 해서 임의 요청이나
  claim 범위 밖 target까지 자동 허용되는 것은 아니다.

**필요 작업**
- `residual_model_registry`를 rebuild/promotion 가능한 상태로 만들기 전까지
  `default_residual_mode=shadow`와 customer-facing mutation disabled를 유지한다.
- 다음은 trained checkpoint count/promotion policy를 실제 guarded checkpoint와
  연결하고, registry guarded promotion acceptance를 통과한 뒤
  `product_goal_completion_audit`을 재검증하는 것이다.
- API validated runner profile evidence/operator approval과 score/ranking mutation
  policy 검증은 registry promotion 이후에도 별도 운영 경계로 유지한다.

### B. CAMEO public benchmark (architecture ready, fetch preflight blocked)

**현재 상태**
- `runs/cameo_architecture_validation_contract_current.json`:
  `status=cameo_architecture_validation_contract_ready`,
  `cameo_architecture_validation_ready=true`,
  `official_cameo_results_used=true`, `public_registration_authorized=true`,
  `ready_lane_count=10`, `blocked_lane_count=0`,
  `approval_required_lane_count=0`이다. 단 이 contract는 등록/메일/웹 fetch를
  실행하지 않으며 `server_registration_mutated=false`,
  `outbound_email_enabled=false`, `external_state_mutated=false`를 유지한다.
- `runs/cameo_api_dependency_readiness_current.json`은
  `status=cameo_api_dependency_ready`, `pass_count=5`,
  `missing_or_unimportable_count=0`, `blocker_count=0`이다.
- `runs/cameo_receiver_smoke_contract_current.json`은
  `status=cameo_receiver_smoke_ready`, POST `/cameo/targets` `200`,
  `ledger_written=true`, `prediction_generation_enabled=false`,
  `outbound_email_enabled=false`, `external_state_mutated=false`를 기록한다.
- `runs/cameo_capability_preflight_current.json`은
  `status=cameo_public_registration_preflight_ready`, `blocker_count=0`,
  `api_dependency_ready=true`, `source_receiver_smoke_status=cameo_receiver_smoke_ready`.
  approval-token metadata가 채워진 별도 운영 검토 기준으로
  `public_registration_requested=true`, `public_registration_allowed=true`이다.
- `betelgeuze_cameo/outbound_email_draft.py`와
  `tools/cameo/build_cameo_outbound_email_draft.py`는 dry-run handoff attachment에서
  local RFC 5322 `.eml` draft를 조립한다. 최신 산출물
  `runs/cameo_outbound_email_draft_current.json`은
  `status=cameo_outbound_email_draft_ready`, `draft_eml_written=true`,
  `attachment_count=1`, `model1_attachment_count=1`,
  `outbound_email_enabled=false`, `email_sent=false`,
  `smtp_connection_opened=false`, `external_state_mutated=false`다.
- `betelgeuze_cameo/outbound_email_send_preflight.py`와
  `tools/cameo/build_cameo_outbound_email_send_preflight.py`는 actual send 직전의
  approval/SMTP metadata를 검사하는 fail-closed preflight다. 최신 산출물
  `runs/cameo_outbound_email_send_preflight_current.json`은
  `status=cameo_outbound_email_send_preflight_ready`, `blocker_count=0`,
  `draft_ready=true`, `draft_eml_present=true`,
  `registration_email_approval_ready=true`, `operator_send_csv_present=true`,
  `authorized_for_separate_operator_send=true`, `email_sent=false`,
  `smtp_connection_opened=false`, `outbound_email_enabled=false`,
  `external_state_mutated=false`다.
- `betelgeuze_cameo/official_result_fetch_preflight.py`와
  `tools/cameo/build_cameo_official_result_fetch_preflight.py`는 official result
  retrieval 직전의 URL/record/approval metadata를 검사하는 fail-closed
  preflight다. 최신 산출물
  `runs/cameo_official_result_fetch_preflight_current.json`은
  `status=blocked_cameo_official_result_fetch_preflight`, `blocker_count=2`,
  `operations_surface_ready=true`, `receiver_smoke_ready=true`,
  `operator_fetch_csv_present=false`,
  `authorized_for_separate_operator_fetch=false`,
  `network_request_opened=false`, `official_results_fetched=false`,
  `native_local_accuracy_used=false`, `external_state_mutated=false`다.
  `runs/goal_operator_intake_kit_current/manifest.json`도
  `cameo_official_result_fetch_preflight` entry를 추가로 노출하며,
  `runs/cameo_official_result_fetch_operator_approval_template_current.csv`를
  kit template으로 복사하고 expected intake
  `runs/cameo_official_result_fetch_operator_approval_intake.csv`와
  `APPROVE_CAMEO_OFFICIAL_RESULT_FETCH` 토큰을 함께 표시한다. `/goal/status`도
  `cameo_official_result_fetch_preflight_*` keys로 preflight status,
  template/intake path, approval token, blocked flags, no-network/no-fetch 상태를
  직접 노출한다. 같은 상태는
  `/product/cameo-official-result-fetch-preflight` API surface에서도 확인된다.
  최신 goal release decision도 이 preflight를 직접 읽어
  `cameo_official_result_fetch_preflight_recorded=true`,
  `blocked_cameo_official_result_fetch_preflight`, approval token, no-network/no-fetch
  상태를 final refresh exact check에 고정한다.
- `runs/cameo_validation_operations_dossier_current.json`은
  `stage_count=10`, `blocked_stage_count=1`, `approval_required_stage_count=1`,
  `official_result_fetch_preflight_ready=false`,
  `outbound_email_draft_ready=true`,
  `outbound_email_send_preflight_ready=true`다. 첫 blocked stage는
  `first_blocked_stage_id=official_result_fetch_preflight`
  (`first_blocked_stage_blocker_count=2`)이고, 첫 approval-required stage는
  `first_approval_required_stage_id=public_registration_and_email`
  (`APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL`)이다.
  따라서 dossier 자체는 `blocked_cameo_validation_operations_dossier` 상태를
  유지하지만, blocked 원인은 공식 결과 fetch preflight 한 곳으로 수렴했다.
- `runs/cameo_architecture_validation_contract_current.json`은 최신 재생성 후
  `local_validation_protocol_ready=true`, `receiver_api_readiness_ready=true`,
  `validation_operations_surface_ready=true`, `ready_lane_count=10`,
  `blocked_lane_count=0`, `approval_required_lane_count=0`이다.
- prediction email sender와 result fetcher는 scaffold가 존재하지만 실제 SMTP send,
  public registration, official-result web fetch는 별도 operator-run action으로
  남아 있고 current artifact는 이를 실행하지 않았다.
- 공식 CAMEO 결과는 operator intake 기준 1건 accepted이며 performance scorecard와
  architecture validation evidence에는 반영됐다. 다만 official-result fetch preflight는
  별도 retrieval approval CSV가 없어 계속 blocked다.

**병목 원인**
- `external_state_mutated=false` / `outbound_email_enabled=false` /
  `server_registration_mutated=false` 같은 fail-closed 플래그로 의도적 차단.
- official-result fetch preflight의 운영자 CSV/승인 토큰
  (`APPROVE_CAMEO_OFFICIAL_RESULT_FETCH`)이 비어 있어 별도 retrieval step을 열 수 없다.
- API dependency profile, local receiver smoke, outbound email draft assembly는
  1차 통과했고 outbound send preflight도 ready다. 하지만 public CAMEO
  registration/email/prediction submission 및 official-result retrieval은 외부 CAMEO
  운영 흐름 없이는 의도적으로 실행되지 않는다.

**필요 작업**
- API dependency profile 설치/활성화와 receiver smoke contract는 1차 완료.
- outbound email draft assembly와 send preflight는 ready. 다음은 실제 SMTP send가
  필요한 경우 separate operator-run action으로만 수행.
- official-result fetch preflight CSV를 채우고
  `APPROVE_CAMEO_OFFICIAL_RESULT_FETCH` 기준의 separate retrieval step을 운영자가
  실행할지 결정.
- public endpoint 등록은 `APPROVE_CAMEO_SERVER_REGISTRATION`,
  `APPROVE_CAMEO_OUTBOUND_EMAIL` approval metadata가 준비된 상태에서 별도 외부
  operator-run action으로만 진행.

### C. GPCR family / router / scorer promotion (shadow-only lock)

**현재 상태**
- rank-rescue 독립 반복의 `ranking_pr_auc_ci_low=0.7612 >= 0.45`로
  현재 tracked CI-low metric blocker는 닫혔다. legacy
  `gpcr_residual_prototype_spec_family_anchor_ci_stability_v3`의
  `ranking_pr_auc_ci_low=0.21 < 0.45`는 diagnostic-only 비교 근거로 남긴다.
- v3~v16, adaptive까지 14+번 반복에도 DRD2 deep inversion 잔존
  (global rank 8562~18923, within-target 5315).
- OPRM1 topology/pose support는 claim-locked frozen shadow replay에서
  `selected_oprm1_target_rank=1`, `selected_oprm1_decoys_above_positive=0`,
  `selected_non_oprm1_regression_count=0`, `selected_top20_positive_count=3`로
  repair evidence ready다.
- `claim_promotion_allowed=false` 강제 — 100k rerun/threshold relaxation/fake pass 금지.
- v3~v5 tombstone, v6/v7 score-only reject, v8/v9 atom-window reject,
  v10/v11 selected-slice green (비-portable), v12~v15 frozen replay improvement,
  v16/adaptive는 best all-basic top20 recovery.
- `gpcr_core_acidic_anchor_overcontact_prior_gate_v4`: `PR-AUC=0.0082`,
  `top20=0.00` (tombstone reject).
- `gpcr_core_family_balanced_rescore_v1` frozen 100k: `PR-AUC=0.5187`,
  `top20=0.25`, but `PR-AUC < 0.55` & `CI-low 0.149 < 0.45` (comparison only).
- Family-held-out scorecard: `pass` (9 positives, 4 distinct targets) — green but
  not claim-promoting.
- `gpcr_broad_claim_review_receipt_current.json`은 target-held-out broad review와
  scorer/router promotion gate 2개 row를 별도 evidence receipt로 요구한다. 현재
  둘 다 placeholder라 `pass_row_count=0`, `blocked_row_count=2`이며,
  metric green이나 guarded input green만으로 broad claim을 승격할 수 없다.

**병목 원인**
- scoring contract가 "valid anchor + close decoy over-anchoring"을 분리 못 함.
- DRD2 positive의 native `Asp114` anchor 거리는 ~3.25 A로 양호,
  그러나 top decoy cluster는 ~2.48 A로 더 가까움.
  → 단순 anchor absence가 아니라 over-anchoring / ligand-physics-prior 분리 미흡.
- OPRM1 pose-collapse는 selected-slice frozen replay에서는 repair evidence가 준비됐고,
  active scorer/claim promotion은 여전히 false로 잠겨 있다.
- v3~v16 모두 데이터/특징 공학 단계의 한계를 노출.

**필요 작업**
- `config/gpcr_broad_claim_review_receipt_current.csv`의 2개 row를 실제 local
  evidence JSON, reviewer, reviewed timestamp, license flag, zero external engine call,
  `APPROVE_GPCR_BROAD_CLAIM_REVIEW` token으로 채운 뒤 broad claim readiness를 재검증.
- target-held-out broad-scope claim review 및 scorer/router promotion gate.
- HTR2A decoy support discrimination.
- Conserved anchor / conditional prior gating.
- 이후 non-leaky positive coverage 확장 + guarded validation prep.
- Threshold relaxation / target identity feature / fake pass 절대 금지.

### D. Transporter AQP1 / GLUT1 (직접 결합 kcal no-claim)

**현재 상태**
- `runs/aqp1_negative_evidence_intake_gate_current.json`:
  `product_scope_evidence_status=product_scope_transporter_negative_quantitative_evidence_ready`,
  `exact_negative_quantitative_row_count=3`, `primary_source_verified_count=3`,
  `transporter_negative_quantitative_evidence_ready=true`이나,
  `authoritative_negative_apply_allowed_count=0`,
  `negative_evidence_closure_allowed=false`, `claim_promotion_allowed=false`.
- `runs/product_scope_breadth_evidence_operator_field_worksheet_current.json`:
  `suggested_evidence_artifact_count=1`로
  `runs/aqp1_negative_evidence_intake_gate_current.json`을
  `exact_negative_quantitative_value_missing` row의 candidate evidence로 노출한다.
  단 `operator_fill_pending_field_count=36`이며 reviewer/timestamp/license/token은
  여전히 수동 확인 대상이라 claim은 자동 승격되지 않는다.
- AQP1은 functional IC50-derived surrogate kcal 3건 (closure allowed),
  `replacement_reference_binding_kcal_mol` blank.
- GLUT1: ChEMBL positive binder context 5건, negative 0건.
- 외부 source (PubMed/BindingDB/ChEMBL) crosscheck:
  AQP1 direct-binding negative 정량 행 0건, AQP1 BindingDB affinity 0건,
  GLUT1 BindingDB affinity 123건 (positive).
- GLUT1 curation queue: `slot_cover=3/3`, `unused_candidate_count=2`,
  `apply_allowed=false`.
- AQP1 first wave, GLUT1 second wave로 분리 운영.

**병목 원인**
- 외부 source에 direct-binding kcal negative/positive reference evidence가
  **존재하지 않음**.
- AQP1 functional no-effect negative quantitative primary-source row 3건은 확보됐지만,
  direct-binding kcal이나 authoritative negative apply/claim promotion으로는 승격하지 않는다.
- direct-binding primary source 또는 internal wetlab 없이는 kcal claim은 계속 막힘.
- GLUT1 positive binder context는 확보되어 있으나,
  negative curation은 정량 reference value 부재.
- R8 scope-breadth receipt는 이제 shallow evidence JSON을 막는다. direct-binding
  row는 primary-source verified count와 claim-safe kcal row count가 1 이상이어야
  하고, functional surrogate를 kcal evidence로 승격했다는 flag가 있으면 blocked다.
  negative row도 exact negative quantitative value와 primary-source verified count가
  필요하다.
- AQP1 direct-binding external intake도 같은 신호를 직접 산출한다.
  `runs/aqp1_direct_binding_external_evidence_intake_current.json`은
  `product_scope_evidence_status`,
  `transporter_direct_binding_evidence_ready`,
  `primary_source_direct_binding_evidence_ready`,
  `claim_safe_direct_binding_kcal_ready`,
  `claim_safe_direct_binding_row_count`,
  `primary_source_verified_count`,
  `source_locator_invalid_count`를 기록한다. 승인 row라도 PMID/DOI/internal
  primary-source locator, Kd/Ki standard type, positive numeric nM, direct method,
  target/direct-assay/validity booleans이 맞지 않으면 claim-safe row로 세지지 않는다.
  따라서 illustrative EXAMPLE PMID나 ChEMBL context를 direct-binding kcal evidence로
  승격하는 경로가 닫혔다.

**필요 작업**
- AQP1/GLUT1에 대한 1차 정량 negative/positive reference 데이터
  (PubMed primary source 또는 internal wetlab).
- current AQP1 negative intake gate의 exact quantitative primary-source evidence를
  R8 receipt에 연결할 때도 direct-binding kcal row와 분리 표기.
- Direct binding kcal vs functional surrogate kcal 분리 표기 유지.

### E. CA2 / PXR packet closure

**현재 상태**
- CA2: `ready_row_count=6/12`, `applied_row_count=6`,
  `blocked_row_count=6`. most_common_missing_field는
  `replacement_reference_binding_kcal_mol`.
- PXR: `pxr_packet_replacement_readiness_ready`,
  `ready_row_count=14`, `blocked_row_count=0`.
- PXR direct-binding replacement candidate/draft는 준비됨:
  selected replacement candidate 6건, first replacement kcal `-6.8212`,
  draft 후 `ready_for_apply_row_count_after_draft=14`.
- 단, PXR draft는 `authoritative_apply_allowed=false`,
  `authoritative_replacement_fields_touched=false`로 claim-safe 경계를 유지한다.
- 두 영역 모두 review-only / prep-only 상태로 delivery claim 밖.

**병목 원인**
- tracked CA2/PXR replacement readiness와 claim-boundary accounting은 green이지만,
  broader/unbounded claim에는 운영자 입력 + 정량 reference 값 외부 의존이 남아 있다.
- PXR은 technical readiness가 올라왔지만, authoritative broader-claim apply는 아직
  운영자/claim 정책으로 잠겨 있다.
- replacement_ligand_id / replacement_reference_binding_kcal_mol /
  replacement_source / replacement_smiles / replacement_scaffold 동기화 triple-edit
  경계는 유지해야 한다.

**필요 작업**
- broader CA2 claim에 필요한 `replacement_*` 필드와 정량 kcal provenance 확정.
- PXR은 draft를 authoritative apply로 승격할지 운영자/claim policy로 결정.
- 동기화 triple-edit (reference/split/meta)와 provenance ledger 검증 유지.

### F. Wetlab prospective translation

**현재 상태**
- PDE atomized parameterization/local-min 7/7 closed, all-atom hard blocks 0.
- 그러나 실제 lab assay/affinity 측정 0건.
- `binding_energy_proxy ≤ -0.55`, `mean_min_distance_A ≤ 3.10`,
  `stability_score ≥ 0.32` 임계치는 simulation-based.
- "wetlab-proven hit"은 명시적으로 out-of-claim.

**병목 원인**
- 실제 lab 작업 + 시간 + 비용 — MD packet quality와 prospective translation은
  다른 차원.
- selected all-atom hard block closure ≠ wetlab-proven hit.

**필요 작업**
- T. cruzi PDE 실제 assay 수행.
- Hit confirmation, affinity measurement.
- Broader PDE chemistry 확장.

### G. Deployment / monitoring / hosting

**현재 상태**
- `deploy/model_registry.py`는 self-hosted filesystem model registry, signed
  artifact manifest, current/previous version pointer, rollback activation을
  제공한다.
- `deploy/upload_model.py`, `deploy/download_model.py`, `deploy/rollback_model.py`,
  `deploy/deploy_pipeline.sh`는 `MODEL_REGISTRY_SIGNING_KEY` 기반 HMAC 서명/검증
  흐름으로 모델 artifact publish/download/rollback smoke를 실행한다.
- `monitoring/prometheus.yml:30-34` — `api-server:8000/metrics` scrape 설정이
  있고, `api/security.py:32-183`은 `prometheus_client` 기반 CollectorRegistry로
  security control gauge, HTTP request counter, blocked request counter,
  audit write failure counter를 노출한다. `/metrics`는 K8s probe/scrape가
  auth token 없이 접근 가능하도록 secret-free endpoint로 유지된다.
- `monitoring/product_api_alerts.yml`은 `micf-api` scrape target down, audit write
  failure, 5xx rate, auth failure spike, rate-limit spike alert를 정의한다.
- `monitoring/alertmanager.yml`은 hardcoded Slack placeholder를 제거하고
  `/etc/alertmanager/paged-webhook-url` 파일 주입 기반 paged webhook receiver를
  사용한다. secret URL은 repo 밖 operator-managed file로 유지.
- `tools/smoke_alert_delivery.py`는 Alertmanager webhook v4 형태의 synthetic alert를
  비밀 URL 출력 없이 POST한다. `--local-receiver-smoke` closed-loop smoke evidence는
  `runs/alert_delivery_smoke_current.json`에 `status=pass`, `received_alert_count=1`로
  기록된다.
- `Dockerfile.product` 존재.
- `deploy/docker-compose.product.yml`은 API server + API worker self-hosted product
  배포 단위를 제공한다.
- `deploy/systemd/micf-api-server.service`와
  `deploy/systemd/api-server.env.example`은 VM/on-prem API server supervisor 단위를
  제공한다. `uvicorn api.main:app`, auth/rate-limit/audit-log/TLS exposure guard,
  queue handoff, shared `/var/lib/micf` data path를 명시한다.
- `deploy/systemd/micf-api-worker.service`와
  `deploy/systemd/api-worker.env.example`은 VM/on-prem worker supervisor 단위를
  제공한다.
- `deploy/k8s/`는 API server + worker + shared PVC K8s rollout skeleton을 제공한다.
- `.github/workflows/product-api-worker.yml`은 API worker/deploy contract CI를 제공하며,
  viewer asset base URL decision과 self-hosted license distribution audit 산출물을
  CI에서 재생성한 뒤 release bundle 테스트를 실행한다.
- `deploy/product_rollback_runbook.md`는 signed model registry pointer rollback,
  verified download, previous image digest/evidence bundle 복구 절차를 기록한다.
- `deploy/product_rollout.py`는 docker build/tag/push, compose up, K8s apply/set-image/
  rollout status 명령을 dry-run plan으로 생성하고, 실제 실행은
  `APPROVE_PRODUCT_ROLLOUT` 승인 토큰 없이는 `blocked_approval_required`로 차단한다.
- `deploy/product_rollout_runbook.md`와 `runs/product_rollout_plan_current.json`은
  Target/Action/Impact/Risk/Rollback/Verification이 포함된 rollout operator plan을
  제공한다.
- `tools/product/build_product_rollout_execution_readiness.py`와
  `runs/product_rollout_execution_readiness_current.json`은 release bundle, rollout
  dry-run plan, security contract, alert smoke가 준비됐는지와 operator execution
  intake가 채워졌는지를 read-only로 검증한다. 최신 상태는
  `product_rollout_execution_readiness_ready`, `release_bundle_ready=true`,
  `rollout_plan_ready=true`, `security_contract_ready=true`, `alert_smoke_ready=true`,
  `operator_csv_present=true`, `authorized_for_separate_operator_execution=true`,
  `blocker_count=0`이다. 이 readiness artifact는 실행 계획/권한/입력 준비만 검증하며,
  실제 rollout 수행 여부는 아래 execution smoke receipt가 별도로 검증한다.
- `tools/product/build_product_rollout_execution_smoke_receipt.py`와
  `runs/product_rollout_execution_smoke_receipt_current.json/.csv/.md`는 위 readiness
  이후 **별도 R4 승인으로 실제 rollout smoke를 수행했다는 운영자 receipt**를 검증한다.
  현재 상태는 `product_rollout_execution_smoke_receipt_ready`,
  `receipt_csv_present=true`, `receipt_row_count=1`, `rollout_executed=true`,
  `external_state_mutated=true`, `target_environment=k8s`다. 이 산출물은 builder 자체가 배포/푸쉬/서비스 재시작을
  실행하지 않고, 실행 후 남겨진 receipt만 read-only로 검증하며
  `/product/rollout-execution-smoke-receipt` API surface에서도 endpoint mutation과
  receipt mutation 사실을 분리해 노출한다.
- `deploy/product_release_bundle.py`와 `runs/product_release_bundle_current.json/.md`는
  security contract, rollout dry-run plan, alert delivery smoke, runner profile
  enablement work order, API runner profile promotion readiness gate/operator template,
  rollback/rollout runbook, Docker/K8s/compose artifact hash, systemd API server/worker
  unit/env example, viewer vendor manifest/notice, viewer asset base URL decision,
  product launch R4 preflight, product quality gate verification receipt,
  product scope-breadth evidence receipt,
  product full-commercial blocker evidence matrix
  artifact를 하나의 release bundle manifest로 묶고 operator promotion policy를
  `operator_approval_required`로 고정한다. 최신 상태는 `artifact_count=34`,
  `check_count=26`, `pass_count=26`, `blocker_count=0`이다.
- `deploy/docker-compose.product.yml`, `deploy/k8s/configmap.yaml`,
  `deploy/systemd/api-server.env.example`, `deploy/systemd/api-worker.env.example`은
  `PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1`을 product deployment default로
  제공한다.
- `api/security.py`는 `PRODUCT_API_HOSTED_EXPOSURE_APPROVED=1`인데
  `PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=0`이면 `/metrics`를 제외한 요청을
  `hosted_tls_termination_not_verified`로 fail-closed 차단한다.
- `api/config.py`의 로컬/dev 기본값은 보수적으로 TLS verified `false`.
- `product_api_hosted_exposure_approved` 기본 `false` (B2B self-host 가드).
- `tools/product/build_product_launch_r4_preflight.py`와
  `runs/product_launch_r4_preflight_current.json/.csv/.md`는 API customer-flow
  evidence, rollout execution readiness, release bundle operator policy,
  commercial-independence/license, third-party license review, restricted engine
  readiness, external mutation guard를 R4 직전 단일 preflight로 묶는다. 최신 상태는
  `product_launch_r4_preflight_ready`, `blocker_count=0`, `check_count=7`,
  `pass_count=7`, `authorized_for_external_mutation=false`,
  `launch_executed=false`, `external_state_mutated=false`이다.
- `tools/run_product_release_current_refresh.py --execute`는 source-of-truth 순서에
  residual shadow/registry, product execution work-order/preflight, core/full AI decision
  graph, local pose sampling readiness, AI report explanation/UX, API/service-boundary contracts, self-hosted
  license audit, third-party review gate, R4 preflight, scope-breadth closure checklist,
  scope-breadth evidence receipt, goal operator intake kit, goal API surface contract, bottleneck briefing,
  commercial readiness operator packet/freshness/execution ladder/handoff,
  최종 release bundle 재생성을 포함하며,
  최신 실행 결과는
  `product_release_current_refresh_verified`, `command_count=118`, `executed_count=118`,
  `failed_count=0`, `timed_out_count=0`, `final_gate_verification_ready=true`,
  `final_gate_count=4`, `final_gate_blocker_count=0`이다.
- `runs/deploy_ops_legal_gap_closure_current.json`은 이제 rollout readiness와 actual
  rollout smoke receipt를 분리한 뒤 `deploy_ops_legal_gap_closure_complete`,
  `closed_gap_count=6`, `open_gap_ids=[]`로 닫혔다.
  `runs/science_claim_promotion_gap_closure_current.json`은 GPCR broad-family boundary와
  restricted OpenMM 2-bead boundary를 모두 closed로 기록해
  `science_claim_promotion_gap_closure_complete`, `open_gap_ids=[]`,
  `closed_gap_count=5`가 됐다. `runs/master_gap_closure_rollup_current.json`도
  `master_gap_closure_rollup_complete`, `open_gap_ids=[]`다. 같은 세부
  closed-gap 상태는 release decision과 `/goal/status`의
  `science_claim_promotion_gap_closure_*` 키로 전파된다.

**병목 원인**
- hosted/상용 SaaS화 자체가 productization roadmap에 없음.
  local delivery + on-prem pilot 가정.
- Dockerfile + security middleware + TLS hosted-exposure fail-closed guard +
  docker-compose/systemd/K8s API server+worker supervisor + CI contract + runtime metrics +
  1차 alert rules/paged webhook receiver + alert delivery closed-loop smoke +
  signed model registry/rollback은 갖춰져 있어 self-hosted B2B pilot의 실행 단위와
  기본 관측성/복구성은 형성됐으나, 운영 환경별 alert threshold 튜닝,
  실제 pager provider secret delivery와 운영 registry/K8s context 기반 실행 smoke는
  아직 부족하다.

**필요 작업**
- docker-compose product manifest는 1차 완료; K8s manifest도 1차 완료.
- systemd API server supervisor unit/env example과 worker supervisor unit/env example은
  1차 완료.
- CI workflow는 API worker/deploy contract와 release bundle local decision artifact
  refresh를 1차 완료; build/push/deploy rollout dry-run/approval gate는 1차 완료.
- Model registry + signed artifact + rollback은 1차 완료; operator promotion
  policy + release bundle linkage, rollout execution readiness gate, R4 launch
  preflight, operator-provided rollout execution smoke receipt 검증은 1차 완료.
  다음은 운영 환경별 pager/TLS/SLO tuning과 R8/R9/ACCURACY full-commercial claim blocker를
  release claim 밖으로 계속 분리해 유지하는 일이다.
- release source-of-truth gate는 R4 preflight, R4 rollout smoke receipt artifact,
  R8 scope-breadth receipt, goal operator intake kit, commercial readiness execution
  ladder, API/bottleneck visibility, local pose sampling readiness, GPCR Phase A/B claim-lock metric readiness,
  active scorer promotion-decision claim-lock metric readiness, GPCR broad claim-scope target-heldout
  input readiness, science accuracy frontier restricted-ready/commercial-parity-blocked accounting, production AI registry promotion operator
  receipt/priority packet/field worksheet/staging apply preview, CAMEO official-result fetch preflight, R8 scope-breadth evidence field worksheet/staging apply preview, R9 engine-refinement claim evidence priority packet/field worksheet/staging apply preview,
  master gap closure rollup 포함 refresh 이후
  `product_release_source_of_truth_gate_ready`, `pass_count=149/149`,
  `blocker_count=0`, `stale_artifact_count=0`,
  `release_refresh_command_count=118`으로 재검증됐다.
- `scripts/check_independent_product_readiness.py`는 현재 release/source-of-truth,
  product readiness, operational quality, commercial-independence, capability surface,
  release bundle, master/science-claim rollup을 read-only로 확인해
  `independent_product_readiness_verified`,
  `independent_restricted_product_ready=true`,
  `full_commercial_claim_promotion_ready=false`,
  `full_commercial_open_gap_ids=[]`,
  `science_accuracy_frontier_status=blocked_science_accuracy_frontier`,
  `science_accuracy_frontier_restricted_ready=true`,
  `science_accuracy_frontier_broad_commercial_blocked=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_ready=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_row_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_missing_row_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count=136`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_download_executed=false`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_present=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready=false`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_source_url_present_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_staging_destination_path_present_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command_present_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count=187`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id=r9_statistical_support_coordinate_fetch_001`,
  `science_accuracy_frontier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker=operator_placeholders_unfilled`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_ready=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_template_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count=17`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_template_metric_name_count=3`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_placeholder_value_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_present=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready=false`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required=true`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count=51`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count=0`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed=false`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id=r9_statistical_support_metric_source_template_001`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name=dockq`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker=operator_placeholders_unfilled`,
  `science_accuracy_frontier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS`,
  `accuracy_parity_ligand_ranking_metric_thresholds_pass=true`,
  `accuracy_parity_ligand_ranking_metric_blocker_count=0`,
  `accuracy_parity_ligand_ranking_claim_scope_lock_only=true`,
  full-commercial blocker는 R8/R9 receipt와 `ACCURACY:ligand_ranking` broad claim lock으로
  남긴다.
- `scripts/verify_quality_gate.py`는 operational quality contract를 메모리에서
  재빌드해 `product_quality_gate_verified`, `quality_gate_ready=true`,
  `blocker_count=0`, execution/results/external mutation/input-payload persistence
  false, production-AI customer-facing mutation flags false를 확인한다. 최신
  `runs/product_quality_gate_verification_current.json`은 release bundle artifact와
  source-of-truth semantic-ready row에 포함되어, 품질 게이트 검증 결과가 operator
  handoff 밖으로 빠지지 않게 한다.
- `prometheus_client` 기반 실제 metrics endpoint는 1차 완료.
- Alert rules + paged webhook receiver + closed-loop alert delivery smoke는 1차 완료;
  다음은 operator webhook secret mount, 실제 pager provider delivery smoke,
  SLO threshold 튜닝.
- TLS termination operator-verified product deployment default on + hosted exposure
  fail-closed guard는 1차 완료; 다음은 실제 ingress/cert-manager 또는 customer
  reverse-proxy smoke.
- Self-hosted B2B license 검증 자동화는 1차 완료
  (`runs/self_hosted_license_distribution_audit_current.json`:
  `hard_blocker_count=0`, `operator_review_item_count=1`).
- release bundle은 systemd API server/worker units와 third-party license review
  gate, API runner profile promotion readiness gate/operator template, rollout
  execution readiness gate, product launch R4 preflight, product quality gate
  verification receipt, product scope-breadth
  evidence receipt, product full-commercial blocker evidence matrix를 포함해
  `artifact_count=34`, `check_count=26`, `pass_count=26`,
  `blocker_count=0` 상태다.

### H. Viewer 외부 의존성

**현재 상태**
- `viewer/index.html`은 Mol*, Plotly, JSZip을 `viewer/vendor/` 로컬 pinned asset에서
  로드한다. Google Fonts runtime 로드는 제거되고 system/Korean font stack을 사용한다.
- `viewer/vendor/manifest.json`은 Molstar 4.5.0, Plotly 2.35.2, JSZip 3.10.1의
  upstream URL, version, size, sha256 provenance를 기록한다.
- `viewer/app.js`의 `127.0.0.1:8765`/`localhost:8765` asset fallback은 제거되어
  self-hosted/offline delivery에서 암묵적 local server 의존성이 사라졌다.
- `tests/unit/test_viewer_self_hosted_assets.py`와 release bundle manifest가 local
  vendor asset hash와 runtime external URL 부재를 검증한다.
- `tools/run_viewer_protein_atom_smoke.py` 브라우저 스모크는 Firefox/Selenium으로
  `viewer/index.html?smoke=protein-motion`을 로드해 self-hosted vendor asset 상태에서
  `smoke_pass=true`를 확인했다.
- `viewer/vendor/THIRD_PARTY_NOTICES.md`와 `viewer/vendor/manifest.json`은 Molstar,
  Plotly, JSZip의 package/version/license/license source URL provenance를 기록한다.
  release bundle은 `viewer_vendor_license_notices_recorded` 체크로 이 NOTICE linkage를
  검증한다.
- `tools/build_viewer_asset_base_url_decision.py`와
  `runs/viewer_asset_base_url_decision_current.json`은 runtime asset 6개가 모두
  document-relative이고 local file로 존재하며, 4개 vendor reference가 manifest에
  포함됨을 확인한다. 표준 bundle(`viewer/index.html`, `style.css`, `app.js`,
  `vendor/`를 같은 directory layout으로 보존)에서는
  `asset_base_url_override_required_for_standard_bundle=false`다.
- release bundle은 `viewer_asset_base_url_decision_recorded` 체크로 이 판단을 검증한다.

**병목 원인**
- local-delivery offline 보장, browser-level smoke, upstream license notice linkage는
  1차 완료됐다.
- 다만 JSZip의 dual-license expression `(MIT OR GPL-3.0-or-later)`은 기록만 된
  상태이며, 상용 redistribution에서 어떤 compatible path를 선택할지는 운영자/법무
  확인이 필요하다.
- `tools/product/build_third_party_license_review_gate.py`와
  `runs/third_party_license_review_gate_current.json`은 JSZip dual-license path를
  operator/legal-review intake로 추적한다. 최신 상태는
  `third_party_license_review_gate_ready`, `expected_review_asset_count=1`,
  `review_csv_present=true`, `approved_review_asset_count=1`,
  `missing_review_asset_count=0`, `blocker_count=0`이다.
  `legal_advice_provided=false`, `asset_modified=false`,
  `external_state_mutated=false`.
- customer reverse proxy/CDN/subpath 배포 중 표준 same-directory bundle은 override
  없이 가능하다고 판정됐다. 단, `index.html`만 별도 위치로 옮기는 relocated-index
  배포는 asset path rewrite 또는 delivery-specific asset base URL이 필요하다.

**필요 작업**
- viewer 자산 vendoring/pinning (CDN 제거)은 1차 완료.
- localhost fallback 제거는 1차 완료.
- browser smoke에서 vendor asset load 확인은 1차 완료.
- upstream license notice bundle과 release bundle linkage는 1차 완료.
- third-party license review gate와 release bundle linkage는 1차 완료.
- delivery bundle별 asset base URL override 필요성 판단은 1차 완료
  (`standard_bundle=false`, `relocated_index=true`).
- 다음은 JSZip dual-license commercial redistribution path의 운영자/법무 확인.

### I. Storage / repo 비대

**현재 상태**
- `tools/product/build_storage_residual_cleanup_status.py`와
  `runs/storage_residual_cleanup_status_current.json`은 selected heavy path 9개를
  read-only로 측정한다. 최신 상태는
  `storage_residual_cleanup_status_ready`, `existing_path_count=6`,
  `resolved_missing_path_count=3`, `operator_action_candidate_count=0`,
  `existing_target_human=50.27 GiB`, `filesystem_used_percent=76.47`이다.
- tracked keep 대상: `runs/` 28.99 GiB, `casp17/` 3.86 GiB,
  `models/` 5.92 GiB, `data/` 11.50 GiB.
- 기존 heavy cleanup 표적 중
  `casp17/massivefold_external_pool_intake`, `rust_engine/target`, `.venv`는
  현재 missing/resolved 상태다.
- `runs/archive`는 79.94 KiB, `runs/local_heavy_runs`는 28.00 KiB로
  `small_residual_review` 상태다.
- `.gitignore`는 generated/sensitive 제외하나 실제 working tree에는 잔존.
- cleanup execution evidence는 일부 과거 cleanup 실행을 기록하지만, 현재 residual
  status builder는 새 delete/archive/externalize를 실행하지 않았다.
  `delete_executed=false`, `archive_executed=false`,
  `externalize_executed=false`, `external_state_mutated=false`.
- 2026-05-02 cleanup: 189 stale `stage2_trajectory_frames` payloads 삭제
  (98125333296 bytes).
- 2026-05-03 follow-up: 12 raw trajectory payloads 삭제 (556010987428 bytes).
- structure-support rerun cleanup: 38346317024 + 51265129536 bytes.
- 현재 residual set 기준 heavy operator-action candidate는 0개다.

**병목 원인**
- CASP17 한시성 산출물 + 반복 trajectory frame 누적은 과거 주요 원인이었으나,
  현재 tracked heavy cleanup 표적은 대부분 missing/resolved다.
- 남은 큰 용량은 `runs/`, `casp17/`, `models/`, `data/`처럼 보존/프로비넌스
  검토가 필요한 keep 대상이다.
- 추가 cleanup 실행은 여전히 operator-approved 별도 계획이 필요하다.

**필요 작업**
- storage residual status는 1차 생성 완료.
- `casp17/massivefold_external_pool_intake`, `rust_engine/target`, `.venv`는
  missing/resolved 상태 확인 완료.
- `runs/archive`, `runs/local_heavy_runs`는 small residual review로 유지.
- Final PDB/mmCIF, top representative, sha256 manifest, viewer index,
  validation report 보존.

### J. Tools 비대 (1,575 top-level wrapper/tool files)

**현재 상태**
- CASP17 일회성 운영 코드, ligand HTVS, wetlab, GPCR replay,
  CAMEO validation, cleanup, goal rollup, product gates가 한 디렉토리에 혼재.
- LDDT-PLI, BiSyRMSD, MassiveFold external rerank 등 비교용 코드는 잔존하나
  더 이상 active claim의 근거가 아님.
- `tools/build_tools_package_separation_work_order.py`와
  `runs/tools_package_separation_work_order_current.json`은 top-level
  `tools/*.py` 1575개를 read-only로 인벤토리화한다.
  `classified_target_package_count=1092`, `other_review_count=483`,
  package counts는 `product=362`, `casp17=296`, `wetlab=288`, `gpcr_replay=73`,
  `cleanup=50`, `cameo=23`이다.
- 현재 work order는 `--include-reference-counts` deep mode로 재생성되어
  `reference_counts_included=true`이며,
  `batch_1_low_reference_count=0`, `batch_2_review_count=149`,
  `batch_3_high_reference_count=1426`로 이동 후보/검토 후보를 더 보수적으로
  나눈다.
  `move_executed=false`, `import_rewrite_executed=false`,
  `external_state_mutated=false`.
- `tools/build_tools_package_migration_plan.py`와
  `runs/tools_package_migration_plan_current.json/.csv/.md`는 deep work order에서
  target package에 속하고 risk/reference/import count가 모두 0인 1차 migration
  batch만 선별한다. 첫 실행 전 plan은 `candidate_pool_count=5`, `selected_count=5`
  였고, exact-token reference counter 보강 후 새로 드러난
  `tools/run_ligand_scaleup_100k_pilot.py` 1개도 product target으로 이동했다.
  실행 receipt 생성 후 최신 plan은 다시 재생성되어
  `blocked_tools_package_migration_plan`, `candidate_pool_count=0`,
  `selected_count=0`, `blocker_count=1`
  (`no_low_reference_candidates`)이다.
- `tools/build_tools_package_migration_receipt.py`와
  `runs/tools_package_migration_receipt_current.json/.csv/.md`는 selected low-reference
  batch가 package target으로 이동됐고 top-level compatibility wrapper가 남아 있음을
  검증한다. 최신 상태는 `tools_package_migration_receipt_ready`,
  `plan_selected_count=2`, `verified_migration_count=2`,
  `blocked_migration_count=0`, `move_executed=true`,
  `compatibility_wrapper_retained=true`, `import_rewrite_executed=false`,
  `external_state_mutated=false`다.
- 1차 이동 완료 target path는
  `tools/casp17/build_casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution.py`,
  `tools/cleanup/archive_ligand_stress_runs.py`,
  `tools/gpcr_replay/build_blind_gpcr_adrb2_chembl_dataset.py`,
  `tools/product/freeze_ca2_target_packet_from_pdb.py`,
  `tools/wetlab/resolve_wetlab_compound_name.py`이며, 후속 low-reference target은
  `tools/product/run_ligand_scaleup_100k_pilot.py`,
  `tools/wetlab/wetlab_run_writer_utils.py`,
  `tools/wetlab/wetlab_stage6_tuning_utils.py`다.
  기존 `tools/*.py` 경로에는 wrapper가 남아 CLI/import 호환성을 유지한다.
- 이전 잔여 `batch_1_low_reference_count=4` row는 모두 `tool_reference_count=1`이어서
  zero-reference 자동 plan에서 제외됐으나, 이후 referenced migration receipt로
  모두 처리되어 최신 deep work order에서는 `batch_1_low_reference_count=0`이다.
- `tools/build_tools_package_reference_review.py`와
  `runs/tools_package_reference_review_current.json/.csv/.md`는 남은 referenced
  batch_1 row의 실제 caller 위치를 resolve한다. 4개 row resolve 후 이동/rewrite가
  완료되어 최신 상태는 `blocked_tools_package_reference_review`,
  `review_candidate_count=0`, `blocker_count=1`
  (`no_referenced_batch_1_rows`)이다.
- 처리 완료된 referenced batch_1 caller map:
  `tools/build_ca2_negative_evidence_capture_intake.py` →
  `tools/run_family_expansion_refresh.py:114`,
  `tools/build_transporter_blocker_capture_intake.py` →
  `tools/run_family_expansion_refresh.py:165`,
  `tools/launch_wetlab_broad_screen_antitarget_watch_loop.py` →
  `tools/run_wetlab_broad_screen_antitarget_runner.py:22`,
  `tools/monitor_wetlab_broad_screen.py` →
  `tools/build_wetlab_broad_screen_precision_monitor.py:562`.
- `tools/build_tools_package_reference_migration_receipt.py`와
  `runs/tools_package_reference_migration_receipt_current.json/.csv/.md`는 이 4개가
  package target으로 이동됐고, top-level wrapper가 남아 있으며, 위 caller line들이
  package path로 rewrite됐음을 검증한다. 최신 상태는
  `tools_package_reference_migration_receipt_ready`, `review_candidate_count=4`,
  `verified_migration_count=4`, `caller_rewrite_verified_count=4`,
  `blocked_migration_count=0`, `move_executed=true`,
  `compatibility_wrapper_retained=true`, `caller_rewrite_executed=true`,
  `external_state_mutated=false`다.
- `tools/build_tools_package_batch2_review_plan.py`와
  `runs/tools_package_batch2_review_plan_current.json/.csv/.md`는
  `batch_2_review_count`를 더 작은 reference class로 분해한다. 첫 slice 실행 전에는
  `batch2_total_count=754`, `first_slice_candidate_count=239`,
  `selected_count=25`였다. batch2 selected slice 10회, 총 244개
  이동/rewrite 후 manual review lane으로 전환했고, 이후 25개 manual slice,
  11개 자동 slice, 1개 자동 slice, 25개 manual slice, 1개 자동 slice,
  25개 manual slice, 25개 manual slice, 25개 manual slice, 25개 manual slice,
  25개 manual slice, 25개 manual slice, 25개 manual slice, 25개 manual slice,
  25개 manual slice, 25개 manual slice, 25개 manual slice, 8개 manual slice,
  13개 internal-import manual slice, 1개 product audit manual slice를
  추가 이동했다. 이어서 `tools/product/ligand_scaleup_surface_helpers.py`와
  `tools/wetlab/wetlab_selected_allatom_canonical.py` 2개 first-slice도
  wrapper-preserving move + recorded reference rewrite로 검증했다. 최신 재계산
  상태는 `blocked_tools_package_batch2_review_plan`,
  `batch2_total_count=149`, `first_slice_raw_candidate_count=1`,
  `first_slice_candidate_count=0`, `selected_count=0`,
  `skipped_existing_target_candidate_count=1`,
  `skipped_missing_reference_candidate_count=0`, `blocker_count=1`
  (`no_batch2_first_slice_candidates_with_exact_references`)이다.
  최신 plan도 아직 move 자체는 수행하지 않는 plan-only 산출물이며
  `move_executed=false`, `caller_or_test_rewrite_executed=false`,
  `external_state_mutated=false`를 유지한다. `run_ligand_scaleup_100k_pilot.py`처럼
  `_current.py` sibling name에 substring으로 걸리는 false-positive reference는
  exact-reference 없는 후보로 skip하도록 plan matcher가 보강됐다.
- `tools/build_tools_package_batch2_migration_receipt.py`는 자동 batch2 selected slice
  1개가 target package (`casp17`)로 이동됐고,
  top-level wrapper가 남아 있으며, 기록된 test/import references가 target package
  import 또는 `tools/<package>/...` 경로로 rewrite됐음을 검증한 바 있다. 당시 상태는
  `tools_package_batch2_migration_receipt_ready`, `plan_selected_count=1`,
  `verified_migration_count=1`, `reference_rewrite_verified_count=1`,
  `cli_main_wrapper_count=1`, `import_only_wrapper_count=0`,
  `blocked_migration_count=0`, `move_executed=true`,
  `compatibility_wrapper_retained=true`, `caller_or_test_rewrite_executed=true`,
  `external_state_mutated=false`다. 해당 자동 1개 관련 targeted unit test는
  `9 passed`였고, 당시 tools package split unit suite는 `28 passed`였다.
- 최신 자동 batch2 first-slice 2개는
  `runs/tools_package_batch2_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=2`, `verified_migration_count=2`,
  `reference_rewrite_verified_count=2`, `blocked_migration_count=0`으로 검증됐다.
- 이어서 최신 manual slice 25개는
  `runs/tools_package_batch2_manual_migration_receipt_current.json/.csv/.md`와
  `runs/tools_package_batch2_manual_migration_executed_plan_current.json`에서
  `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=25`, `verified_migration_count=25`,
  `reference_rewrite_verified_count=25`, `cli_main_wrapper_count=3`,
  `import_only_wrapper_count=22`, `blocked_migration_count=0`으로 검증됐다.
- 마지막 target-package manual tail slice 4개는
  `runs/tools_package_batch2_manual_tail_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=4`, `verified_migration_count=4`,
  `reference_rewrite_verified_count=4`, `import_only_wrapper_count=4`,
  `blocked_migration_count=0`으로 검증됐다.
- `tools/build_tools_package_batch2_manual_review_plan.py`와
  `runs/tools_package_batch2_manual_review_plan_current.json/.csv/.md`는 자동
  first-slice가 고갈되거나 부족해진 뒤의 다음 수동 검토 큐를 생성한다. import-only
  helper module을 정식 wrapper strategy로 기록하도록 보강됐고, 이미 target module이
  존재하는 compatibility wrapper row를 재선택하지 않도록
  `skipped_existing_target_candidate_count`를 기록한다. 최신 manual slice 25개는
  `runs/tools_package_batch2_manual_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=25`, `verified_migration_count=25`,
  `reference_rewrite_verified_count=25`, `cli_main_wrapper_count=24`,
  `import_only_wrapper_count=1`, `blocked_migration_count=0`으로 검증됐다.
  해당 slice targeted unit test는 `56 passed`다.
- 이어서 최신 manual slice 8개는
  `runs/tools_package_batch2_manual_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=8`, `verified_migration_count=8`,
  `reference_rewrite_verified_count=8`, `cli_main_wrapper_count=7`,
  `import_only_wrapper_count=1`, `blocked_migration_count=0`으로 검증됐다.
  해당 slice targeted unit test는 `17 passed`다.
- `internal_import_reference` row는 외부 caller가 아니라 source file 내부의
  `from tools...` / `tools.` dependency line이 migration risk였으므로,
  manual plan과 receipt가 self-internal-import reference location을 기록/검증하도록
  보강했다. 이 보강 후 13개 internal-import manual slice는
  `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=13`, `verified_migration_count=13`,
  `reference_rewrite_verified_count=13`, `cli_main_wrapper_count=12`,
  `import_only_wrapper_count=1`, `blocked_migration_count=0`으로 검증됐다.
  관련 unit suite는 `30 passed`, moved target import smoke는 13/13 통과했다.
- exact-token reference counter와 filename-prefix matcher도 보강해
  `_current.py` sibling 및 `tests/unit/test_*.py` filename false-positive가
  batch2 후보로 남지 않게 했다.
- 이어서 `tools/product/build_self_hosted_license_distribution_audit.py` 1개
  product audit manual slice는 `tools_package_batch2_migration_receipt_ready`,
  `plan_selected_count=1`, `verified_migration_count=1`,
  `reference_rewrite_verified_count=1`, `cli_main_wrapper_count=1`,
  `blocked_migration_count=0`으로 검증됐다.
  관련 unit suite는 `46 passed`, 후속 low-reference migration suite는 `32 passed`다.
- 최신 manual plan은 재생성 후
  `blocked_tools_package_batch2_manual_review_plan`, `batch2_total_count=149`,
  `batch2_target_package_count=62`,
  `batch2_reference_bearing_target_count=62`,
  `batch2_unmigrated_reference_bearing_target_count=0`,
  `candidate_pool_count=0`, `selected_count=0`,
  `skipped_existing_target_candidate_count=62`,
  `skipped_missing_reference_candidate_count=0`, `blocker_count=1`
  (`no_batch2_manual_review_candidates_with_exact_references`)이다.
  선택 가능한 unmigrated target-package exact-reference manual slice는 현재 0개다.
  `tools/bin` 같은 vendored reference-noise tree는 새 manual plan 검색에서 제외해
  실제 프로젝트 참조 위치만 기록한다. 최신 unit 확인은 tools package/refactor
  split suite 기준 `67 passed`다.

**병목 원인**
- 제품/캠페인/벤치마크 코드가 분리되지 않은 채 누적 — 리팩토링 속도 저하.
- zero/low-risk 자동 이동 후보, batch2 first-slice 자동 후보, target-package
  exact-reference manual 후보는 현재 모두 소진됐다.
  최신 batch2 target package 62개는 모두 target module이 존재하고,
  `batch2_unmigrated_reference_bearing_target_count=0`이다.
- batch2 `other_review=101` package classification row는 모두 확정됐다. 55개는
  extended keyword로 자동 재분류됐고, 나머지 46개는 명시 manual decision map으로
  `canonical_owner_review=1`, `product=99`, `gpcr_replay=1` bucket에 기록됐다.
- `main()` 없는 helper module은 기존 CLI-main wrapper receipt를 그대로 적용할 수
  없어서 import-only wrapper strategy를 receipt가 별도 인정하도록 보강했다. 직전
  25개 manual slice는 24개 CLI-main wrapper와 1개 import-only wrapper였고,
  8개 manual slice는 7개 CLI-main wrapper와 1개 import-only wrapper였으며,
  internal-import 13개 slice는 12개 CLI-main wrapper와 1개 import-only wrapper였다.
  이 구분은 유지해야 한다.
- `other_review=483` 중 batch2 `other_review` 101개는 package classification lane에서
  `tools_package_other_review_classification_plan_ready`,
  `classified_count=101`, `unclassified_count=0`, `manual_decision_count=46`로 닫혔다.

**필요 작업**
- `tools/`를 제품별 (product / cameo / casp17 / wetlab / cleanup / gpcr_replay)
  서브패키지로 분리. 1차 work order와 package bucket 산출물, deep reference count
  재생성, 1차 migration plan, 5개 file move + compatibility wrapper receipt,
  referenced 4개 file move + caller rewrite receipt, batch2 decomposition, batch2
  selected slice 10회 총 244개 move + test/import rewrite receipt, batch2 manual
  review plan/receipt 25개, 후속 자동 selected slice 11개, 자동 1개, manual 25개,
  자동 1개, manual 25개, manual 25개, manual 25개, manual 25개, manual 25개,
  manual 25개, manual 25개, manual 25개, manual 25개, manual 25개, manual 25개,
  manual 8개, internal-import manual 13개, product audit manual 1개 이동 및
  latest low-reference 2개, batch2 first-slice 2개, latest manual 25개,
  manual tail 4개 이동 및 receipt는 완료. batch2 누적 이동은 총 636개다.
- batch3 lane_a 첫 실이동 후보 3개
  (`generate_ligand_trajectory_batch.py`, `sweep_neighbor_and_generate_residuals.py`,
  `run_wetlab_wave1_tail_runtime_event.py`)는
  `runs/tools_package_batch3_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=3`,
  `verified_migration_count=3`, `blocked_migration_count=0`으로 검증됐다.
- batch3 lane_a late 실이동 후보 1개
  (`wetlab_broad_screen_watch_utils.py`)도
  `runs/tools_package_batch3_migration_late_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=1`,
  `verified_migration_count=1`, `blocked_migration_count=0`으로 검증됐다.
- batch3 lane_a identity unlock 실이동 후보 1개
  (`run_casp17_competitive_floor_identity_unlock_round.py`)도
  `runs/tools_package_batch3_migration_identity_unlock_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=1`,
  `verified_migration_count=1`, `blocked_migration_count=0`으로 검증됐다.
- batch3 `other_review` reclassified 첫 실이동 후보 3개
  (`ab_test_ai_hip_graph.py`, `benchmark_idp_force_components.py`,
  `benchmark_idp_hbond_prepare_components.py`)는
  `runs/tools_package_batch3_other_review_migration_initial_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=3`,
  `verified_migration_count=3`, `blocked_migration_count=0`으로 검증됐다.
  `build_tools_package_batch3_review_plan.py`는 wrapper import 기반 canonical module
  detection도 수행해 이동 완료 shim을 다시 미분류 migration 후보로 보지 않는다.
- batch3 `other_review` reclassified tail 6개
  (`monitor_ligand_stress_progress.py`, `report_neighbor_force_parity.py`,
  `run_idp_virtual_hbond_rollout_eval.py`, `run_target_tuned_long_stability.py`,
  `sweep_long_stability_tuning.py`, `update_closeout_latest.py`)도
  `runs/tools_package_batch3_other_review_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=6`,
  `verified_migration_count=6`, `blocked_migration_count=0`으로 검증됐다.
- batch3 `other_review` reclassified second slice 10개
  (`run_ligand_stress_validation.py`, `run_ligand_topk_delivery.py`,
  `run_nightly_screening_batch.py`, `run_ood_first_validation_batch.py`,
  `run_rust_native_inference_poc.py`, `run_strict_release_with_regression_gate.py`,
  `stage2_full_report.py`, `sweep_ai_interval_tradeoff.py`,
  `train_idp_branch_model.py`, `validate_accuracy_gate.py`)도
  `runs/tools_package_batch3_other_review_migration_second_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
- 최신 batch3 high-reference lane은 `batch3_total_count=530`,
  `first_slice_raw_candidate_count=462`, `first_slice_candidate_count=0`,
  `skipped_existing_target_candidate_count=458`,
  `skipped_existing_canonical_candidate_count=4`,
  `skipped_unclassified_candidate_count=0`이다. 최신 batch3 `other_review` 후보는
  `runs/tools_package_batch3_other_review_classification_plan_current.json/.csv/.md`에서
  `tools_package_batch3_other_review_classification_plan_ready`,
  `candidate_count=0`, `classified_count=0`, `unclassified_count=0`으로 닫혔다.
- batch3 lane_b 첫 target-move slice 10개
  (`apply_idp_3bead_holdout_archive_first.py`,
  `apply_idp_3bead_release_archive_first.py`,
  `apply_ligand_smiles_bead_archive_first.py`,
  `apply_runs_archive_cleanup_now.py`,
  `apply_runs_cleanup_batch3_archive_first.py`,
  `apply_runs_cleanup_batch4_archive_first.py`,
  `apply_runs_cleanup_batch5_stage_heavy_archive.py`,
  `launch_wetlab_broad_screen_heartbeat_loop.py`,
  `monitor_ca2_expansion.py`, `monitor_pxr_expansion.py`)는
  `runs/tools_package_batch3_lane_b_migration_initial_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  cleanup/wetlab/product target module의 `ROOT = Path(__file__)` 계산은 package
  depth에 맞게 보정했고, 기존 top-level path에는 compatibility wrapper를 남겼다.
- 이어서 lane_b 두 번째 target-move slice 10개
  (`repair_gpcr_drd2_pseudo_allatom_backmapping.py`,
  `run_pxr_expansion_scaffold_check.py`,
  `run_wetlab_broad_screen_actual_append.py`,
  `run_wetlab_broad_screen_antitarget_runner.py`,
  `run_wetlab_broad_screen_antitarget_runtime_event.py`,
  `run_wetlab_broad_screen_antitarget_watcher.py`,
  `run_wetlab_broad_screen_primary_watch.py`,
  `run_wetlab_broad_screen_runtime_event.py`,
  `run_wetlab_cathepsin_k_allatom_refinement.py`,
  `run_wetlab_cathepsin_k_exploratory_retry.py`)도
  `runs/tools_package_batch3_lane_b_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  gpcr_replay/product/wetlab target module의 `ROOT` 계산은 package depth에 맞게
  보정했고, `main()` 없는 wetlab CLI wrappers는 `runpy.run_module`로 기존 script
  실행 경로를 유지한다.
- 이어서 lane_b 세 번째 target-move slice 10개
  (`run_wetlab_dengue_ns2b_ns3_exploratory_retry.py`,
  `run_wetlab_dpre1_exploratory_retry.py`,
  `run_wetlab_final2_runtime_event.py`,
  `run_wetlab_hard_target_rescue_lane.py`,
  `run_wetlab_master_runtime_event.py`,
  `run_wetlab_next3_runtime_event.py`,
  `run_wetlab_plpro_manual_retry.py`,
  `run_wetlab_priority3_runtime_event.py`,
  `run_wetlab_rescue_three_bead_slice.py`,
  `run_wetlab_sarscov2_mpro_allatom_refinement.py`)도
  `runs/tools_package_batch3_lane_b_migration_third_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  wetlab target module의 `ROOT` 계산은 package depth에 맞게 보정했고,
  기존 top-level path에는 module-alias compatibility wrapper를 남겼다.
- 이어서 lane_b 네 번째 target-move slice 10개
  (`run_wetlab_broad_screen_primary_runner.py`,
  `run_wetlab_stk17b_exploratory_followup_retry.py`,
  `run_wetlab_stk17b_manual_retry.py`,
  `run_wetlab_tcruzi_krs1_exploratory_retry.py`,
  `run_wetlab_tcruzi_pde_rescue_only_branch.py`,
  `run_wetlab_wave2_runtime_event.py`,
  `watch_wetlab_broad_screen_primary.py`,
  `wetlab_allatom_refinement_utils.py`,
  `wetlab_broad_screen_antitarget_watcher_state.py`,
  `wetlab_rescue_only_branch_builder.py`)도
  `runs/tools_package_batch3_lane_b_migration_fourth_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  `main()` 없는 primary runner, antitarget watcher state, helper modules는
  module-alias 또는 `runpy.run_module` wrapper로 기존 import/CLI surface를 유지한다.
- 이어서 lane_b 다섯 번째 target-move slice 1개
  (`run_casp17_competitive_floor_evidence_round.py`)도
  `runs/tools_package_batch3_lane_b_migration_fifth_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=1`,
  `verified_migration_count=1`, `blocked_migration_count=0`으로 검증됐다.
  CASP17 target module의 `ROOT` 계산은 package depth에 맞게 보정했고,
  기존 top-level path에는 module-alias compatibility wrapper를 남겼다.
- 이어서 batch3 package-classified migration slice 10개
  (`append_keep_green_lane_history.py`,
  `apply_biorxiv_temporal_idp_item_provenance_facts.py`,
  `apply_verified_binding_sources.py`, `audit_ligand_leakage.py`,
  `bootstrap_real_md_metadata.py`, `builder_json_utils.py`,
  `builder_table_utils.py`, `calibrate_ligand_mmpbsa_proxy.py`,
  `classify_runs_files.py`, `collect_feature_matrix.py`)도
  `runs/tools_package_batch3_package_classification_migration_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  import-only helper wrappers와 CLI wrappers는 module-alias 방식으로 기존
  top-level import surface를 유지한다.
- 이어서 두 번째 batch3 package-classified migration slice 10개
  (`compare_biorxiv_external_validation_runs.py`, `curate_structure_quality.py`,
  `evaluate_ligand_ranking_metrics.py`, `fetch_public_structure_set.py`,
  `generate_openmm_ca_md_references.py`, `generate_perturbed_data.py`,
  `idp_3bead_common.py`, `import_real_md_and_run_gate.py`,
  `monitor_biorxiv_external_validation.py`,
  `monitor_cross_family_locked_decoy_shadow.py`)도
  `runs/tools_package_batch3_package_classification_migration_second_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  `generate_perturbed_data.py`는 `runpy.run_module`, `idp_3bead_common.py`는
  import-only module-alias wrapper로 기존 surface를 유지한다.
- 이어서 세 번째 batch3 package-classified migration slice 10개
  (`monitor_idp_holdout_progress.py`, `native_target_registry.py`,
  `pdb_loader.py`, `postprocess_structure_visuals.py`,
  `promote_biorxiv_external_validation_package.py`,
  `promote_verified_binding_rows_to_workbook.py`, `prune_runs_files.py`,
  `render_readme_molecular_figures.py`, `report_md_gap.py`,
  `report_physics_fidelity.py`)도
  `runs/tools_package_batch3_package_classification_migration_third_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  `native_target_registry.py`, `promote_*`, `render_readme_molecular_figures.py`의
  repo-root 계산은 package depth에 맞게 보정했고, 기존 top-level path에는
  module-alias compatibility wrapper를 남겼다.
- 이어서 네 번째 batch3 package-classified migration slice 10개
  (`report_sparse_checkpoints.py`, `resume_biorxiv_external_validation.py`,
  `run_accuracy_revalidation.py`, `run_active_learning_cycle.py`,
  `run_allatom_claim_readiness.py`, `run_bigdata_curriculum_training.py`,
  `run_biorxiv_external_validation_current.py`,
  `run_biorxiv_robustness_battery_current.py`,
  `run_biorxiv_robustness_current.py`,
  `run_biorxiv_robustness_scenario.py`)도
  `runs/tools_package_batch3_package_classification_migration_fourth_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  biorxiv runner 계열의 repo-root 계산은 package depth에 맞게 보정했고,
  기존 top-level path에는 module-alias compatibility wrapper를 남겼다.
- 이어서 다섯 번째 batch3 package-classified migration slice 10개
  (`run_claim_metric_correction_loop.py`,
  `run_external_validation_blind_sets.py`, `run_family_expansion_refresh.py`,
  `run_idp_3bead_benchmark_gate.py`, `run_idp_3bead_evaluator.py`,
  `run_idp_3bead_holdout_pipeline.py`,
  `run_idp_3bead_release_smoke_current.py`,
  `run_idp_tau_k18_stabilization_trial.py`,
  `run_initial_claim_triplet_gate.py`,
  `run_ligand_backmapping_scoring.py`)도
  `runs/tools_package_batch3_package_classification_migration_fifth_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=10`,
  `verified_migration_count=10`, `blocked_migration_count=0`으로 검증됐다.
  direct script 실행 경로는 top-level compatibility wrapper의 repo-root
  bootstrap으로 유지했고, residual shadow/apply scoring 및 clash-relief batch
  provenance 회귀 테스트를 통과했다.
- 이어서 여섯 번째 batch3 package-classified migration slice 7개
  (`run_live_unseen_protein_learning_loop.py`,
  `run_openmm_2bead_rebench.py`, `run_openmm_2bead_strict_release.py`,
  `run_preflight_gate.py`, `run_strict_md_eval.py`,
  `run_trpv1_sourcing_refresh.py`, `tune_target_neighbor_rebuild.py`)도
  `runs/tools_package_batch3_package_classification_migration_sixth_receipt_current.json/.csv/.md`에서
  `tools_package_batch3_migration_receipt_ready`, `plan_selected_count=7`,
  `verified_migration_count=7`, `blocked_migration_count=0`으로 검증됐다.
  `run_trpv1_sourcing_refresh.py`의 repo-root 계산은 package depth에 맞게 보정했고,
  기존 top-level path에는 module-alias compatibility wrapper를 남겼다.
- `tools/accounting/build_tools_package_batch3_lane_decomposition_plan.py`와
  `runs/tools_package_batch3_lane_decomposition_plan_current.json/.csv/.md`는 남은
  lane_b/c/d 68개를 실행 lane으로 분해한다. 최신 상태는
  `tools_package_batch3_lane_decomposition_plan_ready`,
  `selected_for_next_slice_count=0`, `lane_b_target_move_candidate_count=0`,
  `existing_target_wrapper_verification_count=64`,
  `canonical_owner_review_count=0`,
  `package_classification_required_count=0`,
  `manual_or_reference_review_count=4`이다.
  compatibility wrapper 유지 방식으로 바로 이동 가능한 lane_b target-package
  후보와 package-classification-required 후보는 현재 고갈됐다.
- `tools/accounting/build_tools_package_batch3_package_classification_plan.py`와
  `runs/tools_package_batch3_package_classification_plan_current.json/.csv/.md`는
  남은 `package_classification_required` 후보가 없음을 확인한다.
  최신 상태는 `tools_package_batch3_package_classification_plan_ready`,
  `candidate_count=0`, `classified_count=0`, `unclassified_count=0`,
  `reclassified_package_counts={}`이다. 이 산출물은
  move/rewrite 없는 plan-only이다.
  최근 slice에서 `tools/cameo/` package 추가와 CASP17/cleanup/GPCR/product/wetlab
  build tools의 wrapper-preserving package 이동을 계속 진행했다.
- 한시성 운영 코드와 제품 파이프라인 분리.
- 죽은 코드 (tombstone reject evidence 등)는 별도 archive 디렉토리 이동.

### K. License / legal distribution audit

**현재 상태**
- `LICENSE`는 존재하며 `legal/proprietary-license-betelgeuze.txt`와 sha256이 동일하다
  (`5784208421b9379372ed51596201f78ab2c7157b96667fea7e0fb0bbd077e325`).
- `runs/product_license_decision_gate_current.json`은
  `product_license_decision_gate_ready`, `authorized_for_license_file_creation_review=true`,
  `spdx_license_id=ProprietaryRef-Betelgeuze`,
  `license_text_source=legal/proprietary-license-betelgeuze.txt`를 기록한다.
- `runs/product_license_file_creation_work_order_current.json`은
  `product_license_file_creation_work_order_ready`이며, approved source hash와 target
  `LICENSE` review manifest fingerprint를 갖고 있다.
- `runs/product_commercial_independence_gate_current.json`은 `license_file_present` pass를
  기록한다.
- `tools/product/build_self_hosted_license_distribution_audit.py`와
  `runs/self_hosted_license_distribution_audit_current.json`은 product LICENSE, approved
  source hash, commercial-independence license status, viewer third-party notice linkage를
  read-only로 검증한다.
- `runs/self_hosted_license_distribution_audit_current.json`은
  `self_hosted_license_distribution_audit_recorded`, `hard_blocker_count=0`,
  `operator_review_item_count=1`, `third_party_license_review_gate_status=third_party_license_review_gate_ready`,
  `third_party_license_review_gate_ready=true`,
  `third_party_license_review_gate_blocker_count=0`를 함께 기록한다.
- release bundle은 `self_hosted_license_distribution_audit_recorded` 체크로 이 감사
  산출물을 포함하며, `/product/self-hosted-license-distribution-audit` API surface도
  hard blocker와 operator/legal review 경계를 직접 노출한다.
- 최신 goal release decision은 같은 audit을 직접 summary/row로 승격하고, final
  refresh는 `self_hosted_license_distribution_audit_recorded`,
  `product_license_hash_matches_approved_source=true`,
  `third_party_license_review_gate_ready=true`, `legal_advice_provided=false`,
  `external_state_mutated=false`를 필수 조건으로 검증한다.
- `license_decision.py`의 APPROVAL_TOKEN 기반 write path는 유지된다.
- `license_options.py`가 operator-selectable license path 요약 제공
  (proprietary, source-available, enterprise EULA 등).
- `runs/product_license_decision_packet_current.json`은 이미 승인된 LICENSE가 있는
  현재 상태를 `product_license_decision_packet_ready`, `hard_blocker_count=0`,
  `review_item_count=1`, `commercial_independence_ready=true`,
  `license_decision_gate_ready=true`, `license_present=true`로 기록한다.
  `license_already_present`는 hard blocker가 아니라 별도 LICENSE file-creation
  review item이다.

**병목 원인**
- LICENSE 파일 생성/일관성 검증은 1차 완료됐지만, license 결정의 법적 충분성은
  운영자/법률 자문 영역이다.
- JSZip dual-license expression `(MIT OR GPL-3.0-or-later)`의 commercial
  redistribution path는 audit에 operator review item으로 기록되어 있고,
  현재 third-party license review gate는 operator CSV 기준
  `third_party_license_review_gate_ready`, `blocker_count=0`이다.
  단 `legal_advice_provided=false`라서 최종 법률 판단은 여전히 기술 영역 밖이다.
- final refresh는 JSZip approved asset, allowed license path set, review CSV,
  operator template CSV, `APPROVE_THIRD_PARTY_LICENSE_REVIEW`,
  `asset_modified=false`, `external_state_mutated=false`를 exact check로 요구한다.

**필요 작업**
- product LICENSE와 approved source hash 일치 검증은 1차 완료.
- 결정된 license metadata와 release bundle linkage는 1차 완료.
- third-party license review gate와 release bundle linkage는 1차 완료.
- 다음은 proprietary product license의 법률 최종 확인과 JSZip dual-license
  redistribution path의 operator/legal confirmation 유지.

---

## 3) 완전 독립 상용 제품까지 남은 단계 (영역·순서)

### 우선 작업 (제품 인프라)

1. **API ↔ engine wiring** — 일반 요청 fail-closed 유지 + operator-approved
   validated runner profile adapter, durable job state, idempotent records,
   signed manifests, profile readiness/evidence/hash gate, customer-flow release
   evidence의 live/signed path, bundle validation, R4 preflight는 1차 green이다.
   다음은 restricted scope 안의 운영 SLA/모니터링을 유지하면서 full-commercial
   science claim evidence와 분리하는 일이다.
2. **Production AI 고객 실행 경계** — ROCm/HIP GPU execution environment와
   force derivation validation은 ready지만, product checkpoint/promotion은
   `default_residual_mode=shadow`, `production_promotion_allowed=false`,
   `trained_model_checkpoint_count=1`로 registry guarded promotion에서 멈춰 있다.
   priority packet 기준 첫 조치는 더 이상 checkpoint 등록이 아니라
   `default_residual_mode_guarded`를 만족시키는 guarded promotion operator
   receipt 작성이며, 이후 production promotion policy, customer-facing mutation
   flags를 순서대로 재검증해야 한다. 이 priority
   상태는 commercial readiness handoff, `/goal/status`, release bundle
   source-of-truth dependency에도 고정되어 있다.
3. **License 결정 + LICENSE 파일 작성** — LICENSE/source hash 일치,
   license decision/work-order/commercial gate, self-hosted license audit, release
   bundle linkage는 1차 완료. 다음은 법률 최종 확인과 JSZip dual-license
   redistribution path 확인.
4. **Deployment 실제화** — docker-compose/CI, K8s 또는 systemd,
   operator-approved rollout 실행 smoke. TLS hosted-exposure guard, model
   registry/signed artifact/rollback, build/push/deploy rollout dry-run approval gate,
   release bundle linkage, `/metrics`의 prometheus_client 통합, 1차 alert
   rules/paged webhook receiver, closed-loop alert delivery smoke, R4 launch
   preflight는 완료.
5. **Self-hosted B2B pilot 인프라** — viewer 자산 vendoring/pinning,
   reproducible build, on-prem license 검증. viewer CDN/localhost fallback 제거,
   asset base URL decision, self-hosted license audit는 1차 완료.

### Science 정확도 확장

6. **GPCR broad claim-scope closure** — OPRM1 topology/pose replay,
   conditional prior gate, rank-rescue independent repeat 기준 PR-AUC/CI-low/top20
   metric blocker는 green이다. target-heldout family guardrail과 guarded-100k
   claim-review input도 green으로 분리됐고, 남은 것은 formal broad claim review와
   scorer/router promotion gate approval 없이는 broad GPCR/Schrodinger-class
   claim promote를 열지 않는 일이다. 이 둘은 이제
   `config/gpcr_broad_claim_review_receipt_current.csv`의 2개 evidence row로
   분리되어 `runs/gpcr_broad_claim_review_receipt_current.json`에서
   `blocked_row_count=2`로 추적된다.
7. **Transporter direct-binding evidence** — AQP1/GLUT1 1차 정량
   negative/positive reference 데이터 (PubMed primary source 또는
   internal wetlab).
8. **OpenMM/Schrodinger급 정확도 parity** — internal typed all-atom/GB-SA/explicit-shell/FEP
   scaffold와 common ligand halogen/charged-residue local-chemistry/metal-coordination/structure-interface proxy surface는 green이지만,
   metal/cofactor calibrated parameterization, charged-residue formal protonation, calibrated charge/torsion/improper
   parameterization, solvent/FEP public-pair calibration, curated 공개 pose/free-energy benchmark intake
   (`refine_tier_public_benchmark_readiness_current` 현재 blocked), external MolProbity/OpenStructure,
   native complex/interface benchmark parity가 남아 있다. `science_accuracy_frontier_current`는
   restricted science accuracy를 ready로 보되 broad commercial parity claim은
   GPCR approval, R9 statistical-support coordinate-fetch R4 approval, R9 public
   evidence receipt가 닫히기 전까지 blocked로 고정한다.
9. **Prospective wetlab T. cruzi PDE 검증** — 실제 assay + hit confirmation.

### 확장 (claim boundary 확대)

10. **CA2/PXR broader claim evidence** — tracked replacement readiness/claim-boundary
    accounting은 green이지만, unbounded broader claim에는 추가 정량 reference와
    operator-reviewed evidence receipt가 필요하다.
11. **IDP broader promotion lane** — bounded shadow-safe 단계 통과.
12. **CAMEO public registration** — API dependency 설치, prediction email /
    result fetcher, 운영자 approval token 발급, 공식 CAMEO 결과 입력.

### 정리 / 리팩토링

13. **Storage cleanup 실행** — `casp17/massivefold_external_pool_intake`,
    `runs/archive`, `rust_engine/target`, `.venv` externalize/archive/delete,
    final PDB/mmCIF + manifest + validation report 보존.
14. **Tools/ 패키지 분리** — `tools/`를 제품별 (product / cameo / casp17 /
    wetlab / cleanup / gpcr_replay) 서브패키지로 분리. Deep reference count,
    1차 selected migration plan, 5개 package move + top-level compatibility wrapper
    receipt, 남은 4개 referenced batch_1 move/caller rewrite receipt는 완료;
    batch2 selected slice 10회 총 244개 move + test/import rewrite receipt도 완료.
    이후 manual 25개, 자동 11개, 자동 1개, manual 25개, 자동 1개, manual 25개,
    manual 25개, manual 25개, manual 25개, manual 25개, manual 25개,
    manual 25개, manual 25개, manual 25개, manual 25개, manual 25개,
    manual 8개, internal-import manual 13개, product audit manual 1개를 추가 이동해
    batch2 누적 636개
    move/rewrite까지 완료.
    최신 재생성 기준으로는 `blocked_tools_package_migration_plan`
    (`selected_count=0`), `blocked_tools_package_batch2_review_plan`
    (`selected_count=0`), `blocked_tools_package_batch2_manual_review_plan`
    (`selected_count=0`) 상태다. batch2 `other_review=101` classification은
    `classified_count=101`, `unclassified_count=0`으로 닫혔고, batch3 lane_a
    실이동 후보 `3+1+1`개도 각각 `verified_migration_count=3`,
    `verified_migration_count=1`, `verified_migration_count=1`로 닫혔다. batch3
    `other_review` reclassified 첫 slice 3개도
    `runs/tools_package_batch3_other_review_migration_initial_receipt_current.json`에서
    `verified_migration_count=3`, `blocked_migration_count=0`으로 닫혔다.
    batch3 `other_review` reclassified tail 6개도
    `verified_migration_count=6`, `blocked_migration_count=0`으로 닫혔다.
    batch3 `other_review` reclassified second slice 10개도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔다.
    batch3 lane_b target-move slice 41개도
    `runs/tools_package_batch3_lane_b_migration_initial_receipt_current.json` 및
    `runs/tools_package_batch3_lane_b_migration_receipt_current.json` 및
    `runs/tools_package_batch3_lane_b_migration_third_receipt_current.json` 및
    `runs/tools_package_batch3_lane_b_migration_fourth_receipt_current.json`에서
    각 `verified_migration_count=10`,
    `blocked_migration_count=0`으로 닫혔고,
    `runs/tools_package_batch3_lane_b_migration_fifth_receipt_current.json`에서
    `verified_migration_count=1`, `blocked_migration_count=0`으로 닫혔다.
    package-classified migration slice 57개도
    `runs/tools_package_batch3_package_classification_migration_receipt_current.json`에서
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔고,
    `runs/tools_package_batch3_package_classification_migration_second_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔으며,
    `runs/tools_package_batch3_package_classification_migration_third_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔고,
    `runs/tools_package_batch3_package_classification_migration_fourth_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔으며,
    `runs/tools_package_batch3_package_classification_migration_fifth_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔고,
    `runs/tools_package_batch3_package_classification_migration_sixth_receipt_current.json`에서도
    `verified_migration_count=7`, `blocked_migration_count=0`으로 닫혔다.
    wrapper-aware batch3 plan 재생성 후 최신 `other_review` classification은
    `candidate_count=0`, `classified_count=0`, `unclassified_count=0`이다.
    lane_b/c/d decomposition은 `candidate_count=68`,
    `selected_for_next_slice_count=0`,
    `lane_b_target_move_candidate_count=0`,
    `package_classification_required_count=0`,
    `existing_target_wrapper_verification_count=64`으로 다음 migration slice를 분리했다.
    이어서 batch3 package classification plan은 해당
    `package_classification_required` 후보가 없음을
    `candidate_count=0`, `unclassified_count=0`으로 닫았다.

### 합산 잔여 gap (영역별)

- **제품 인프라** (1~5): 기술 영역, deterministic. 인프라 5개 항목이 닫히면
  "B2B self-hosted/managed 상용 제품"으로 동작 가능.
- **Science 정확도** (6~9): scoring feature engineering, 외부 데이터/실험
  의존. GPCR CI-low는 scorer feature engineering으로 진행 가능하나,
  transporter/wetlab은 외부 의존성.
- **확장** (10~12): 운영자 input + 외부 CAMEO schedule. CA2/PXR는 input만
  채우면 진행, IDP는 bounded lane data, CAMEO는 외부 schedule.
- **정리** (13~14): cleanup approval + 리팩토링. operator-approved 후
  진행 가능.

---

## 4) 병목의 근본 원인 요약

저장소 전체의 병목은 세 가지로 수렴한다.

1. **Fail-closed product design**
   - API/security/license/CAMEO 모두 `external_state_mutated=false`,
     `outbound_email_enabled=false`, `claim_promotion_allowed=false` 같은
     의도적 잠금.
   - 풀려면 운영자 approval token + 별도 review.
   - restricted claim scope (`kinase/gpcr/ion_channel`) 바깥은 모두
     shadow-only / review-only / parked 상태 유지.

2. **Science scoring 한계**
   - tracked science closure 기준에서는 GPCR CI-low, OPRM1 topology/pose replay,
     OpenMM 2-bead 제한 lane, CA2/PXR/AQP1 evidence boundary가 모두 green이다.
   - 다만 broad GPCR/Schrodinger-class 또는 full all-atom commercial-tool parity
     claim은 여전히 잠겨 있다. GPCR target-heldout/guarded-100k input은 green으로
     분리됐지만, formal broad claim review와 scorer/router promotion gate approval
     receipt가 2/2 blocked라 claim promotion이 열리지 않는다.
   - typed all-atom/GB-SA/explicit-shell/FEP internal scaffold와 readiness smoke는 green이나,
     curated 공개 pose/free-energy parity 및 atom typing coverage/charge/torsion/improper
     calibration은 아직 무제한 claim-grade가 아니다.
   - feature/data engineering 병목은 metric blocker에서 claim-scope blocker로 이동했다.
     외부 source (PubMed/wetlab)와 target-held-out public benchmark receipt가 broad
     claim의 다음 병목이다.

3. **Hosted/full-commercial 운영 증거 부재**
   - `core/` physics는 local-only 가정.
   - `docker-compose`/`K8s`/`CI`/`prometheus_client`/alert rules/signed model
     registry/TLS hosted-exposure guard/closed-loop alert smoke/rollout dry-run
     approval gate/release bundle linkage/R4 launch preflight surface는 1차 green이다.
   - 실제 외부 mutation은 여전히 Target/Action/Impact/Risk/Rollback/Verification
     확인과 operator approval 전에는 금지된다.
   - full-commercial release는 R8 full-scope claim closure와 R9 engine refinement
     claim promotion evidence receipt가 operator placeholder 상태라 막혀 있고,
     production AI registry guarded promotion도 shadow 상태다.
   - local delivery + on-prem pilot 가정. hosted SaaS는 별도.

가장 큰 단일 잔여 gap은 이제 **R8/R9 full-commercial science claim evidence
receipt + R9 public benchmark 통계 support 확대 + production AI registry guarded
promotion + operator-approved 실제 실행 증거**다. 특히 R9은 receptor/complex
coordinate validation 자체는 8/8 pass로 닫혔고, materialized DockQ/lDDT-PLI/internal
ΔG source payload도 24개가 schema-valid 입력 artifact까지 묶어 생성됐지만,
현재 8쌍/3 holdout만으로는 claim-grade 통계 support가 부족하다. 따라서
`refine_tier_public_benchmark_statistical_support_work_order_current`의
17개 추가 public benchmark pair, 최소 5개 holdout slot, bootstrap Spearman
p05 >= 0.5 재검증이 R9 승격 전 직접 병목이다. 최신 candidate queue는 이 17개
slot에 들어갈 target/pose 후보를 선별했지만 receptor/complex coordinate artifact가
17/17개 비어 있어 metric source materialization 전 단계에서 멈춘다. 최신 coordinate
intake/validation packet도 이를 `coordinate_validation_pass_row_count=0`,
`coordinate_validation_blocked_row_count=17`로 고정하므로, 다음 직접 작업은 17개
후보별 공개 receptor/complex coordinate를 검토하고 local artifact로 배치하는 것이다.
최신 coordinate fetch/staging plan은 `coordinate_fetch_required_row_count=17`,
`coordinate_fetch_primary_url_row_count=17`,
`coordinate_fetch_staging_destination_row_count=17`,
`coordinate_fetch_ready_for_validation_row_count=0`을 고정해, URL 식별은 닫고
operator-approved fetch/staging과 재검증을 직접 병목으로 남긴다. 최신 apply
preview도 `coordinate_fetch_apply_preflight_pass_row_count=17`,
`coordinate_fetch_apply_downloaded_row_count=0`,
`post_fetch_validation_supported=true`,
`post_fetch_validation_executed=false`,
`approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`로
고정해, 다음 실행은 승인 토큰을 동반한
`--mode execute --run-post-fetch-validation`으로 좁혀졌다.
coordinate fetch R4 preflight도 `r4_row_count=17`,
`ready_for_r4_review_row_count=17`, `blocked_r4_row_count=0`,
`metric_source_template_row_count=51`, `metric_source_template_fill_ready_row_count=0`,
`metric_source_template_fill_blocked_row_count=51`,
`authorized_for_external_download=false`, `download_executed=false`로 준비되어,
남은 직접 병목은 operator가 17개 Target/Action/Impact/Risk/Rollback/Verification
row를 확인하고 승인 토큰 실행을 허용한 뒤 51개 metric source template placeholder를
reviewed payload로 교체하는 것이다.
metric materialization readiness도 `metric_materialization_row_count=17`,
`metric_materialization_candidate_ready_count=0`,
`metric_materialization_candidate_blocked_count=17`,
`metric_materialization_input_artifact_contract_ready=false`,
`required_metric_input_artifact_count=34`,
`present_required_metric_input_artifact_count=17`,
`missing_required_metric_input_artifact_count=17`,
`planned_metric_source_payload_count=51`,
`existing_metric_source_payload_count=0`으로 고정되어, 승인 이후에도 17개 좌표
validation pass가 먼저 닫혀야 DockQ/lDDT-PLI/internal ΔG source payload 생성과
bootstrap Spearman p05 재검증으로 넘어간다.
새 claim-grade gap audit은 이 상태를 `gap_row_count=5`,
`blocked_gap_row_count=5`, `blocker_count=5`,
`minimum_new_pair_count=17`, `minimum_new_holdout_pair_count=5`,
`bootstrap_spearman_p05_deficit=0.6428571428571428`,
`coordinate_validation_deficit=17`,
`metric_source_payload_fill_deficit=51`로 고정해, 통계 support 부족과 좌표/metric
payload materialization 부족을 한 artifact에서 release source-of-truth가 exact-check한다.
tracked current work-order의
DockQ/lDDT-PLI/internal ΔG source field와 R9 evidence receipt도 operator
placeholder 상태라, source evidence는 파일 존재만으로는 부족하고 schema-valid JSON
payload와 payload가 가리키는 로컬 input artifact 존재 확인까지 통과해야 한다.
상용 API, durable worker, validated runner profile, license/legal review,
release bundle, R4 preflight, claim-boundary 정책, source-of-truth gate는 local artifact
기준 1차 green이지만, full-scope/science claim promotion과 production AI 고객-facing
promotion은 아직 막혀 있다. 실제 고객 실행은
Target/Action/Impact/Risk/Rollback/Verification을 제시하고 명시적 R4 확인을 받은 뒤에만
remote/deployment state mutation으로 넘어갈 수 있다.

# 분자동역학 저장소 — 개선사항 및 잔여 작업 (2026-06-06 KST 기준)

본 문서는 restricted local delivery P0가 닫힌 상태에서, 완전한 독립 상용 제품까지
남아 있는 개선 영역과 그 병목 원인을 정리한 것이다. 기간/공정 추정은 제외하고
영역·원인·필요 작업 중심으로 기술한다.

---

## 1) 현재 닫혀 있는 영역 (tracked green)

| 영역 | 상태 | 근거 산출물 |
|---|---|---|
| Restricted local delivery verdict | `delivery_ready=true`, `p0_blocker_count=0` | `runs/local_delivery_verdict_gate_current.json` |
| Restricted claim scope | `kinase, gpcr, ion_channel` 한정 | `docs/local_delivery_claim_policy.md` |
| Tracked commercialization accounting | `closed=true`, `blocked_count=0` | `runs/commercialization_readiness_current.json`, `runs/commercialization_gap_burndown_current.json` |
| Platform gap taxonomy | `platform_accounting_closed=true`, `top_expansion_gap_id=none_tracked_platform_expansion` | `runs/platform_gap_taxonomy_packet_current.json` |
| Transporter/AQP1/CA2/PXR placeholder accounting | `placeholder_driven_rows=0`, `evidence_blocked_placeholder_rows=0` | `runs/transporter_placeholder_burndown_queue_current.json`, `runs/ca2_pxr_review_policy_closure_gate_current.json` |
| Accuracy parity scorecard | `status=green`, `pass_row_count=5/5` (GPCR ranking, pose geometry, OpenMM, structure, wetlab translation) | `runs/accuracy_parity_scorecard_current.json` |
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
| P1 | API runner profile enable + operator approval | CLOSED | `ligand_htvs_pipeline_default.json`, `backmapping_scoring.production.json` + evidence (enabled, reviewed) |
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
| HW-PROF-01 | HTVS profile blind preset + request.json | CLOSED | `ligand_htvs_pipeline_default.json` `--pipeline-preset-json`, `--docking-request-json` |
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
| 8 | OpenMM / accuracy parity restricted lane | CLOSED | `runs/accuracy_parity_scorecard_current.json` `status=green` |
| 9 | Prospective wetlab translation scaffold | CLOSED | simulation packet green, wetlab-proven hit out-of-claim 유지 |
| 10 | CA2/PXR packet replacement | CLOSED | `runs/ca2_packet_replacement_readiness_current.json`, `runs/pxr_packet_replacement_readiness_current.json` |
| 11 | IDP bounded shadow-safe lane | CLOSED | `runs/idp_broader_promotion_resolution_current.json` `wider_shadow_safe_lane_admitted=true` |
| 12 | CAMEO sender/fetch executor scaffold | CLOSED | `betelgeuze_cameo/outbound_email_send_executor.py`, `official_result_fetch_executor.py` |

검증: `tests/unit/test_build_data_science_expansion_gap_closure.py`, `tools/product/ci_contract_fixture_packets.py` `write_data_science_expansion_closure_packets()`.

---

## 1f) 과학 claim 승격 경계 클로저 (2026-06-06) — CLOSED

| ID | 영역 | accounting | 실제 claim 경계 | 상태 |
|---|---|---|---|---|
| SCI-GPCR | GPCR broad family | breadth gate green | CI-low/O PRM1 blocked, `claim_promotion_allowed=false` | CLOSED |
| SCI-TRANS | Transporter | placeholder 0, functional surrogate | direct binding kcal blocked | CLOSED |
| SCI-CA2-PXR | CA2/PXR | readiness fixture green | replacement workbook/sync boundary scaffold | CLOSED |
| SCI-WETLAB | Wetlab | simulation packet green | wetlab-proven hit out-of-claim | CLOSED |
| SCI-OPENMM | OpenMM | 2-bead 11/11 | full all-atom/MM-GBSA/FEP+ unimplemented | CLOSED |

검증: `tests/unit/test_build_science_claim_promotion_gap_closure.py`, `tools/accounting/build_science_claim_promotion_gap_closure.py`, `tools/product/ci_contract_fixture_packets.py` `write_science_claim_promotion_closure_packets()`.

---

## 1g) 배포·운영·법무 경계 클로저 (2026-06-06) — CLOSED

| ID | 항목 | 상태 | 근거 |
|---|---|---|---|
| DEP-ROLLOUT | rollout execution smoke readiness | CLOSED | `runs/product_rollout_execution_readiness_current.json`, operator intake CSV |
| DEP-PAGER | pager/webhook mount confirmation | CLOSED | closed-loop alert smoke + operator mount flag |
| DEP-TLS | ingress/TLS fail-closed guard | CLOSED | `api/security.py` TLS verification guard |
| DEP-JSZIP | JSZip dual-license review | CLOSED | `runs/third_party_license_review_gate_current.json` |
| DEP-LICENSE | LICENSE hash/technical gate | CLOSED | `LICENSE` ↔ `legal/proprietary-license-betelgeuze.txt`; `legal_advice_provided=false` 유지 |

검증: `tests/unit/test_build_deploy_ops_legal_gap_closure.py`, `tools/accounting/build_deploy_ops_legal_gap_closure.py`, `write_deploy_ops_legal_closure_packets()`.

---

## 1h) 정리/리팩토링 경계 클로저 (2026-06-06, 2026-06-12 재확인) — PLANNING CLOSED / MIGRATION QUEUED

| ID | 항목 | 상태 | 근거 |
|---|---|---|---|
| STOR-RESIDUAL | storage residual status | CLOSED | `runs/storage_residual_cleanup_status_current.json`, `operator_action_candidate_count=0` |
| STOR-EXEC | cleanup execution scaffold | CLOSED | `runs/cleanup_completion_gate_current.json`; `delete_executed=false` |
| TOOLS-OTHER | other_review classification lane | CLOSED | `runs/tools_package_other_review_classification_plan_current.json`: `candidate_count=101`, `classified_count=101`, `unclassified_count=0`, `manual_decision_count=46` |
| TOOLS-BATCH3 | batch3 high-reference review lanes | READY / QUEUED | `runs/tools_package_batch3_review_plan_current.json`: `batch3_total_count=530`, `first_slice_raw_candidate_count=471`, `first_slice_candidate_count=1`; `runs/tools_package_batch3_other_review_classification_plan_current.json`: `candidate_count=10`, `classified_count=10`, `unclassified_count=0`; lane_a receipts `3+1` verified; initial/tail reclassified receipts `3+6` verified; lane_b receipts `10+10+10+10` verified; package-classified migration receipts `10+10+10+10+10` verified; `runs/tools_package_batch3_lane_decomposition_plan_current.json`: `candidate_count=59`, `selected_for_next_slice_count=1`, `lane_b_target_move_candidate_count=1`, `package_classification_required_count=7`; `runs/tools_package_batch3_package_classification_plan_current.json`: `candidate_count=7`, `classified_count=7`, `unclassified_count=0` |

검증: `tests/unit/test_build_storage_cleanup_gap_closure.py`, `tests/unit/test_build_tools_refactor_gap_closure.py`, `write_storage_tools_closure_packets()`.
최신 `runs/tools_refactor_gap_closure_current.json`은
`tools_refactor_gap_closure_complete`, `gap_count=5`, `all_gaps_closed=true`,
`open_gap_ids=[]`이며, `TOOLS-BATCH3-PACKAGE-CLASSIFICATION`까지 closed로 포함한다.

---

## 1i) 잔여 상용·AI·CAMEO·master rollup 클로저 (2026-06-06) — CLOSED

| ID | 영역 | 상태 | 근거 |
|---|---|---|---|
| COMMERCIAL | 상용 10-gap accounting | CLOSED | `runs/commercial_gap_closure_status_current.json` `commercial_gap_closure_complete` |
| PRODUCT-AI | Product AI architecture 7-gap | CLOSED | `runs/product_ai_architecture_gap_closure_current.json` `product_ai_architecture_gap_closure_complete` |
| DATA-12 | CAMEO architecture validation (#12) | CLOSED | `runs/cameo_architecture_validation_contract_current.json`, `data_science_expansion_gap_closure_complete` |
| API-RUNNER | Runner profile promotion readiness | CLOSED | `runs/api_runner_profile_promotion_readiness_current.json` `api_runner_profile_promotion_ready` |
| MASTER | Master gap closure rollup | CLOSED | `runs/master_gap_closure_rollup_current.json` `master_gap_closure_rollup_complete` |

검증: `tests/unit/test_build_master_gap_closure_rollup.py`, `tests/unit/test_build_commercial_gap_closure_status.py`, `tests/unit/test_build_product_ai_architecture_gap_closure.py`, `tests/unit/test_build_data_science_expansion_gap_closure.py`, `tools/product/write_full_gap_closure_fixture_packets.py`, `tools/product/bootstrap_api_worker_contract_artifacts.py` post-bootstrap finalize.

**의도적 경계 (accounting closed ≠ operator execution)**
- `goal_readiness_rollup` → `goal_readiness_pending_operator_or_external_results` (`blocked_lane_count=0`)
- `goal_operator_action_board` → `operator_actions_required` (execution/approval/cleanup 토큰은 operator 범위)
- `claim_promotion_allowed=false`, `execution_enabled=false`, `rollout_executed=false` 유지

---

## 2) Operator 경계만 남은 영역 (accounting green, 실행/승인은 fail-closed)

Tracked accounting roll-up은 §1b–§1i 기준으로 닫혔다. 아래는 **실제 실행·승인·외부 결과**가 필요한 operator/external 경계이며, builder artifact가 green이어도 자동으로 닫히지 않는다.

| 영역 | 현재 posture | 다음 operator 단계 |
|---|---|---|
| Product execution / delivery | `operator_approval_pending` | `APPROVE_PRODUCT_DOCKING_EXECUTION` + bundle assembly/validation |
| Transition / ligand-heavy cleanup | `operator_approval_pending` | cleanup approval token + protected policy decision |
| CAMEO official results | `evidence_ready` (local scaffold) | official results intake; outbound send는 별도 승인 |
| Goal operator board | `operator_actions_required` | surfaced action rows를 순서대로 처리 |

### A. API ↔ Engine wiring — P0/P1 갭 클로저 완료 (2026-06-06)

**현재 상태**
- HTVS stage2/3 production config, two-pass 4-bead cascade, topo corrector, stage2 skip router가 상용 경로에 연결됨.
- enabled runner profile 2종 (`ligand_htvs_pipeline_default`, `backmapping_scoring.production`) + evidence reviewed.
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
- 같은 도구는
  `runs/api_runner_profile_promotion_operator_template_current.csv`도 생성한다.
  이 템플릿은 profile별 `operator_decision`, `approval_token`,
  input/output/claim/gate review boolean, `gate_policy_artifact`, `reviewer`,
  `reviewed_at_utc` 입력 칸을 제공하며, release bundle의
  `api_runner_profile_promotion_operator_template_recorded` 체크에 포함된다.
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
- `core/forcefield.py:17`는 단순 LJ 성격, `core/topology.py:45`는 alanine placeholder
  → "restricted analysis engine"이지 OpenMM/Schrodinger급이라고는 못 함.

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
- 다만 실제 상용 profile 승격과 `core/forcefield.py`/`core/topology.py`의 S-class
  physics/topology 확장은 아직 남아 있다.

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
- `core/forcefield.py`/`core/topology.py`의 LJ 단순/alanine placeholder 자산을
  실제 residue/atom-type topology로 확장 (별도 S-class 작업).

### A-2. Production AI 추론 주체 전환 (ROCm/HIP production_guarded)

**현재 상태**
- `runs/product_production_ai_checkpoint_readiness_current.json`은
  `product_production_ai_checkpoint_readiness_ready`,
  `production_ai_checkpoint_ready=true`,
  `production_gpu_execution_environment_ready=true`,
  `default_residual_mode=production_guarded`,
  `production_promotion_allowed=true`를 기록한다.
- ROCm/HIP 환경은 `rocm_environment_manifest_ready`이며,
  `torch_version=2.6.0+rocm6.1`, `torch_hip_version=6.1.40091-a8dbc0c19`,
  `visible_device_count=1`, AMD GPU detected로 기록되어 있다.
- GPU worker handoff/return receipt도 준비되어 있으며,
  `gpu_receipt_operator_verified_true_count=768`,
  `gpu_receipt_manifest_ok_row_count=768`이다.
- production training data, selected sidecar, checkpoint preflight,
  inference acceptance matrix는 모두 ready이고
  `production_inference_acceptance_blocked_stage_count=0`이다.

**병목 원인**
- 추론 주체 전환 자체는 더 이상 현재 병목이 아니다.
- 남은 병목은 production AI가 열린 뒤의 **고객 실행 표면**이다. 즉,
  runner profile evidence/operator approval, customer-facing score/ranking mutation
  정책, release gate linkage를 실제 배포 단위에서 일관되게 잠그는 작업이다.
- fail-closed 경계는 여전히 필요하다. GPU receipt가 있다고 해서 임의 요청이나
  claim 범위 밖 target까지 자동 허용되는 것은 아니다.

**필요 작업**
- GPU/ROCm receipt와 checkpoint promotion chain은 현재 산출물 기준 완료 상태로 유지.
- 다음은 API validated runner profile별 evidence artifact 작성,
  `APPROVE_API_RUNNER_PROFILE_PROMOTION` review, release bundle/rollout smoke에서
  production_guarded 정책이 실제 고객 요청 경로에만 제한적으로 연결되는지 검증.

### B. CAMEO public benchmark (blocked_lane_count=1, approval_required=3)

**현재 상태**
- `runs/cameo_architecture_validation_contract_current.json`:
  `cameo_architecture_validation_ready=false`,
  `official_cameo_results_used=false`, `public_registration_authorized=false`.
- `runs/cameo_api_dependency_readiness_current.json`은
  `status=cameo_api_dependency_ready`, `pass_count=5`,
  `missing_or_unimportable_count=0`, `blocker_count=0`이다.
- `runs/cameo_receiver_smoke_contract_current.json`은
  `status=cameo_receiver_smoke_ready`, POST `/cameo/targets` `200`,
  `ledger_written=true`, `prediction_generation_enabled=false`,
  `outbound_email_enabled=false`, `external_state_mutated=false`를 기록한다.
- `runs/cameo_capability_preflight_current.json`은
  `status=cameo_development_capability_preflight_ready`, `blocker_count=0`,
  `api_dependency_ready=true`, `source_receiver_smoke_status=cameo_receiver_smoke_ready`.
  public registration은 요청되지 않았고 `public_registration_allowed=false`.
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
  `status=blocked_cameo_outbound_email_send_preflight`, `blocker_count=3`,
  `draft_ready=true`, `draft_eml_present=true`,
  `registration_email_approval_ready=false`, `operator_send_csv_present=false`,
  `authorized_for_separate_operator_send=false`, `email_sent=false`,
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
- `runs/cameo_validation_operations_dossier_current.json`은
  `stage_count=10`, `blocked_stage_count=4`, `approval_required_stage_count=0`,
  `official_result_fetch_preflight_ready=false`,
  `outbound_email_draft_ready=true`,
  `outbound_email_send_preflight_ready=false`다. blocked stage는 공식 결과
  fetch preflight, 공식 결과 intake, outbound email send preflight,
  public registration/email approval이며,
  `blocked_cameo_validation_operations_dossier` 상태를 유지한다.
- `runs/cameo_architecture_validation_contract_current.json`은 최신 재생성 후
  `local_validation_protocol_ready=true`, `receiver_api_readiness_ready=true`,
  `validation_operations_surface_ready=true`, `ready_lane_count=6`,
  `blocked_lane_count=1`, `approval_required_lane_count=3`이다.
- actual prediction email sender와 result fetcher는 미구현이다. 단, sender 이전 단계인
  local outbound email `.eml` draft assembly는 ready stage로, actual send 직전
  preflight와 official-result fetch 직전 preflight는 blocked stage로
  operations dossier에 편입됐다.
- 공식 CAMEO 결과 0건 — 외부 web fetch 금지, 운영자 입력만 허용.
- `local_validation_protocol_ready=true` (lane 6/10 ready, 1 blocked, 3 approval-required).
- capability preflight는 development receiver lane 기준 ready지만,
  public registration lane은 registration approval, outbound email approval,
  prediction-generation approval 부재로 계속 잠겨 있다.

**병목 원인**
- `external_state_mutated=false` / `outbound_email_enabled=false` /
  `server_registration_mutated=false` 같은 fail-closed 플래그로 의도적 차단.
- 공식 CAMEO 결과 자체가 외부 의존 — 자체 통제 불가.
- API dependency profile, local receiver smoke, outbound email draft assembly는
  1차 통과했고 outbound send / official-result fetch preflight scaffold도
  생겼지만,
  public CAMEO registration/email/prediction submission은 운영자 approval token과
  외부 CAMEO 운영 흐름 없이는 의도적으로 열리지 않는다.

**필요 작업**
- API dependency profile 설치/활성화와 receiver smoke contract는 1차 완료.
- outbound email draft assembly, send preflight scaffold, official-result fetch
  preflight scaffold는 1차 완료. 다음은 operator-approved actual prediction
  email sender / result fetcher /
  public endpoint 등록.
- 운영자 approval token (`APPROVE_CAMEO_SERVER_REGISTRATION`,
  `APPROVE_CAMEO_OUTBOUND_EMAIL`) 발급.
- 공식 CAMEO 결과 입력 → performance scorecard 활성화.

### C. GPCR family / router / scorer promotion (shadow-only lock)

**현재 상태**
- `gpcr_residual_prototype_spec_family_anchor_ci_stability_v3`의
  `ranking_pr_auc_ci_low=0.21 < 0.45` 임계치 미달.
- v3~v16, adaptive까지 14+번 반복에도 DRD2 deep inversion 잔존
  (global rank 8562~18923, within-target 5315).
- OPRM1 pose collapse 미해결, v15/v16/adaptive에서 `blocked_positive_count=3` 잔존.
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

**병목 원인**
- scoring contract가 "valid anchor + close decoy over-anchoring"을 분리 못 함.
- DRD2 positive의 native `Asp114` anchor 거리는 ~3.25 A로 양호,
  그러나 top decoy cluster는 ~2.48 A로 더 가까움.
  → 단순 anchor absence가 아니라 over-anchoring / ligand-physics-prior 분리 미흡.
- OPRM1 pose collapse는 frozen replay에서도 잔존.
- v3~v16 모두 데이터/특징 공학 단계의 한계를 노출.

**필요 작업**
- OPRM1 pose/anchor alignment evidence (다음 hard blocker).
- HTR2A decoy support discrimination.
- Conserved anchor / conditional prior gating.
- 이후 non-leaky positive coverage 확장 + guarded validation prep.
- Threshold relaxation / target identity feature / fake pass 절대 금지.

### D. Transporter AQP1 / GLUT1 (직접 결합 kcal no-claim)

**현재 상태**
- `runs/aqp1_negative_evidence_intake_gate_current.json`:
  `authoritative_negative_apply_allowed_count=0`.
- AQP1은 functional IC50-derived surrogate kcal 3건 (closure allowed),
  `replacement_reference_binding_kcal_mol` blank.
- GLUT1: ChEMBL positive binder context 5건, negative 0건.
- 외부 source (PubMed/BindingDB/ChEMBL) crosscheck:
  AQP1 직접 negative 정량 행 0건, AQP1 BindingDB affinity 0건,
  GLUT1 BindingDB affinity 123건 (positive).
- GLUT1 curation queue: `slot_cover=3/3`, `unused_candidate_count=2`,
  `apply_allowed=false`.
- AQP1 first wave, GLUT1 second wave로 분리 운영.

**병목 원인**
- 외부 source에 정량 negative evidence가 **존재하지 않음**.
- internal wetlab/primary source 없이는 영원히 막힘.
- GLUT1 positive binder context는 확보되어 있으나,
  negative curation은 정량 reference value 부재.

**필요 작업**
- AQP1/GLUT1에 대한 1차 정량 negative/positive reference 데이터
  (PubMed primary source 또는 internal wetlab).
- intake template (`runs/aqp1_negative_evidence_intake_template_current.csv`)
  운영자 fill 후 intake gate validation.
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
- CA2는 여전히 운영자 입력 + 정량 reference 값 외부 의존이 남아 있다.
- PXR은 technical readiness는 올라왔지만, authoritative apply는 아직 운영자/claim
  정책으로 잠겨 있다.
- replacement_ligand_id / replacement_reference_binding_kcal_mol /
  replacement_source / replacement_smiles / replacement_scaffold 동기화 triple-edit
  경계는 유지해야 한다.

**필요 작업**
- CA2 잔여 6개 blocked row의 `replacement_*` 필드와 정량 kcal provenance 확정.
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
  `blocked_product_rollout_execution_readiness`, `release_bundle_ready=true`,
  `rollout_plan_ready=true`, `security_contract_ready=true`, `alert_smoke_ready=true`,
  `operator_csv_present=false`, `blocker_count=2`
  (`operator_rollout_execution_csv_missing`, `operator_decision_missing`)이다.
  `rollout_executed=false`, `pager_provider_contacted=false`,
  `ingress_certificate_verified_live=false`, `external_state_mutated=false`.
- `deploy/product_release_bundle.py`와 `runs/product_release_bundle_current.json/.md`는
  security contract, rollout dry-run plan, alert delivery smoke, runner profile
  enablement work order, API runner profile promotion readiness gate/operator template,
  rollback/rollout runbook, Docker/K8s/compose artifact hash, systemd API server/worker
  unit/env example, viewer vendor manifest/notice, viewer asset base URL decision
  artifact를 하나의 release bundle manifest로 묶고 operator promotion policy를
  `operator_approval_required`로 고정한다. 최신 상태는 `artifact_count=21`,
  `check_count=14`, `pass_count=14`, `blocker_count=0`이다.
- `deploy/docker-compose.product.yml`, `deploy/k8s/configmap.yaml`,
  `deploy/systemd/api-server.env.example`, `deploy/systemd/api-worker.env.example`은
  `PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1`을 product deployment default로
  제공한다.
- `api/security.py`는 `PRODUCT_API_HOSTED_EXPOSURE_APPROVED=1`인데
  `PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=0`이면 `/metrics`를 제외한 요청을
  `hosted_tls_termination_not_verified`로 fail-closed 차단한다.
- `api/config.py`의 로컬/dev 기본값은 보수적으로 TLS verified `false`.
- `product_api_hosted_exposure_approved` 기본 `false` (B2B self-host 가드).

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
- Model registry + signed artifact + rollback은 1차 완료; 다음은 operator promotion
  policy + release bundle linkage와 rollout execution readiness gate는 1차 완료;
  다음은 operator-approved rollout 실행 smoke.
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
  execution readiness gate를 포함해 `artifact_count=21`, `check_count=14`,
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
  `blocked_third_party_license_review_gate`, `expected_review_asset_count=1`,
  `review_csv_present=false`, `missing_review_asset_count=1`, `blocker_count=2`
  (`operator_review_csv_missing`, `missing_review_row:jszip`)이다.
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
  split suite 기준 `64 passed`다.

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
- 최신 batch3 high-reference lane은 `batch3_total_count=530`,
  `first_slice_raw_candidate_count=471`, `first_slice_candidate_count=1`,
  `skipped_existing_target_candidate_count=456`,
  `skipped_existing_canonical_candidate_count=4`,
  `skipped_unclassified_candidate_count=10`이다. 최신 batch3 `other_review` 후보는
  `runs/tools_package_batch3_other_review_classification_plan_current.json/.csv/.md`에서
  `tools_package_batch3_other_review_classification_plan_ready`,
  `candidate_count=10`, `classified_count=10`, `unclassified_count=0`으로 닫혔다.
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
- `tools/accounting/build_tools_package_batch3_lane_decomposition_plan.py`와
  `runs/tools_package_batch3_lane_decomposition_plan_current.json/.csv/.md`는 남은
  lane_b/c/d 59개를 실행 lane으로 분해한다. 최신 상태는
  `tools_package_batch3_lane_decomposition_plan_ready`,
  `selected_for_next_slice_count=1`, `lane_b_target_move_candidate_count=1`,
  `existing_target_wrapper_verification_count=47`,
  `canonical_owner_review_count=0`,
  `package_classification_required_count=7`,
  `manual_or_reference_review_count=4`이다.
  다음 바로 이동 가능한 lane_b target-package 후보는
  `tools/run_casp17_competitive_floor_evidence_round.py` 1개다.
- `tools/accounting/build_tools_package_batch3_package_classification_plan.py`와
  `runs/tools_package_batch3_package_classification_plan_current.json/.csv/.md`는
  남은 `package_classification_required` 7개를 package bucket으로 분류한다.
  최신 상태는 `tools_package_batch3_package_classification_plan_ready`,
  `candidate_count=7`, `classified_count=7`, `unclassified_count=0`,
  `reclassified_package_counts={'product': 7}`이다. 이 산출물은
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
  `third_party_license_review_gate_status=blocked_third_party_license_review_gate`,
  `third_party_license_review_gate_ready=false`,
  `third_party_license_review_gate_blocker_count=2`를 함께 기록한다.
- release bundle은 `self_hosted_license_distribution_audit_recorded` 체크로 이 감사
  산출물을 포함한다.
- `license_decision.py`의 APPROVAL_TOKEN 기반 write path는 유지된다.
- `license_options.py`가 operator-selectable license path 요약 제공
  (proprietary, source-available, enterprise EULA 등).

**병목 원인**
- LICENSE 파일 생성/일관성 검증은 1차 완료됐지만, license 결정의 법적 충분성은
  운영자/법률 자문 영역이다.
- JSZip dual-license expression `(MIT OR GPL-3.0-or-later)`의 commercial
  redistribution path는 audit에 operator review item으로 기록되어 있고,
  third-party license review gate로 operator CSV/approval token 입력 대기 상태가
  분리됐다. 최종 선택은 기술 영역 밖이다.

**필요 작업**
- product LICENSE와 approved source hash 일치 검증은 1차 완료.
- 결정된 license metadata와 release bundle linkage는 1차 완료.
- third-party license review gate와 release bundle linkage는 1차 완료.
- 다음은 proprietary product license의 법률 최종 확인과 JSZip dual-license
  redistribution path operator/legal review CSV 작성.

---

## 3) 완전 독립 상용 제품까지 남은 단계 (영역·순서)

### 우선 작업 (제품 인프라)

1. **API ↔ engine wiring** — 일반 요청 fail-closed 유지 + operator-approved
   validated runner profile adapter, durable job state, idempotent records,
   signed manifests, profile readiness/evidence/hash gate는 1차 완료. 다음은 실제
   profile별 evidence artifact 작성과 operator approval 승격.
2. **Production AI 고객 실행 경계** — ROCm/HIP GPU execution environment,
   GPU worker return receipt, production guarded checkpoint 승격은 현재 ready.
   다음은 validated runner profile evidence/operator approval과 고객 요청 경로에서의
   score/ranking mutation policy 검증.
3. **License 결정 + LICENSE 파일 작성** — LICENSE/source hash 일치,
   license decision/work-order/commercial gate, self-hosted license audit, release
   bundle linkage는 1차 완료. 다음은 법률 최종 확인과 JSZip dual-license
   redistribution path 확인.
4. **Deployment 실제화** — docker-compose/CI, K8s 또는 systemd,
   operator-approved rollout 실행 smoke. TLS hosted-exposure guard, model
   registry/signed artifact/rollback, build/push/deploy rollout dry-run approval gate,
   release bundle linkage, `/metrics`의 prometheus_client 통합, 1차 alert
   rules/paged webhook receiver, closed-loop alert delivery smoke는 완료.
5. **Self-hosted B2B pilot 인프라** — viewer 자산 vendoring/pinning,
   reproducible build, on-prem license 검증. viewer CDN/localhost fallback 제거,
   asset base URL decision, self-hosted license audit는 1차 완료.

### Science 정확도 확장

6. **GPCR CI-low 안정화** — OPRM1 pose/anchor alignment,
   HTR2A decoy support, conditional prior gating, 100k CI-low ≥ 0.45,
   top20 안정화 → router/scorer deployment claim promote.
7. **Transporter direct-binding evidence** — AQP1/GLUT1 1차 정량
   negative/positive reference 데이터 (PubMed primary source 또는
   internal wetlab).
8. **OpenMM/Schrodinger급 정확도 parity** — full all-atom/solvent force field,
   MM-GBSA/FEP+ 스타일, pose RMSD/LDDT-PLI/DockQ 벤치마크, MolProbity,
   complex/interface coverage.
9. **Prospective wetlab T. cruzi PDE 검증** — 실제 assay + hit confirmation.

### 확장 (claim boundary 확대)

10. **CA2/PXR packet closure** — PXR은 replacement readiness가 ready이고,
    CA2는 잔여 6개 blocked row의 정량 reference/operator fill-in 필요.
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
    실이동 후보 `3+1`개도 각각 `verified_migration_count=3`,
    `verified_migration_count=1`로 닫혔다. batch3
    `other_review` reclassified 첫 slice 3개도
    `runs/tools_package_batch3_other_review_migration_initial_receipt_current.json`에서
    `verified_migration_count=3`, `blocked_migration_count=0`으로 닫혔다.
    batch3 `other_review` reclassified tail 6개도
    `verified_migration_count=6`, `blocked_migration_count=0`으로 닫혔다.
    batch3 lane_b target-move slice 40개도
    `runs/tools_package_batch3_lane_b_migration_initial_receipt_current.json` 및
    `runs/tools_package_batch3_lane_b_migration_receipt_current.json` 및
    `runs/tools_package_batch3_lane_b_migration_third_receipt_current.json` 및
    `runs/tools_package_batch3_lane_b_migration_fourth_receipt_current.json`에서
    각 `verified_migration_count=10`,
    `blocked_migration_count=0`으로 닫혔다.
    package-classified migration slice 50개도
    `runs/tools_package_batch3_package_classification_migration_receipt_current.json`에서
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔고,
    `runs/tools_package_batch3_package_classification_migration_second_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔으며,
    `runs/tools_package_batch3_package_classification_migration_third_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔고,
    `runs/tools_package_batch3_package_classification_migration_fourth_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔으며,
    `runs/tools_package_batch3_package_classification_migration_fifth_receipt_current.json`에서도
    `verified_migration_count=10`, `blocked_migration_count=0`으로 닫혔다.
    wrapper-aware batch3 plan 재생성 후 최신 `other_review` classification은
    `candidate_count=10`, `classified_count=10`, `unclassified_count=0`이다.
    lane_b/c/d decomposition은 `candidate_count=59`,
    `selected_for_next_slice_count=1`,
    `lane_b_target_move_candidate_count=1`,
    `package_classification_required_count=7`,
    `existing_target_wrapper_verification_count=47`으로 다음 migration slice를 분리했다.
    이어서 batch3 package classification plan은 해당
    `package_classification_required` 7개를
    `classified_count=7`, `unclassified_count=0`으로 닫았다.

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
   - GPCR CI-low 0.21 vs 0.45 임계치, OPRM1 pose collapse,
     AQP1 direct-binding/negative evidence 부족, CA2 잔여 정량 reference 부재.
   - feature/data engineering 병목. v3~v16까지 tombstone/selected-slice
     green의 누적.
   - 외부 source (PubMed/wetlab) 의존성.

3. **Hosted infrastructure 부재**
   - `core/` physics는 local-only 가정.
   - `docker-compose`/`K8s`/`CI`/`prometheus_client`/alert rules/signed model
     registry/TLS hosted-exposure guard/closed-loop alert smoke/rollout dry-run
     approval gate/release bundle linkage는 1차 통합됐으나, 실제 pager provider
     delivery/ingress certificate smoke/operator-approved rollout execution smoke는 미완.
   - local delivery + on-prem pilot 가정. hosted SaaS는 별도.

가장 큰 단일 잔여 gap은 **operator-approved product execution surface**다. 상용 API,
durable worker, validated runner profile, production_guarded AI receipt는 갖춰졌지만,
실제 고객 실행은 profile evidence/operator approval, license/legal review,
rollout smoke, claim-boundary 정책이 한 release bundle 안에서 동시에 green이어야 열린다.

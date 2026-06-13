# 완전한 독립 상용 제품(분자동역학 · 단백질분석 · 리간드도킹)까지의 갭 분석

> 작성 범위: 코드 구현 없이, 현재 저장소를 **외부 도킹/MD 엔진 의존 없는 완전한 독립 상용 제품**으로
> 발전시키기 위해 개선·구현해야 할 영역과 대략적 구현 방향을 정리한 설계 문서.
> 기간 추정은 제외하고 **영역 · 근본 원인 · 구현 방향 · 완료 정의** 중심으로 기술한다.
>
> 기존 문서와의 관계: `docs/improvement_items_remaining_work.md`(accounting 관점, 대부분 tracked-green)와
> 달리, 본 문서는 **"상용 제품으로서 실제로 부족한 것"** 을 제품 역량(capability) 관점에서 재구성한다.

---

## 0. 현재 위치 한 줄 요약

- **닫힌 것:** restricted(`gpcr` / `ion_channel` / `kinase`) 로컬 self-hosted 전달 기반, API/service-boundary,
  license/self-hosted distribution audit, local delivery bundle validation, commercial independence gate,
  R4 preflight, operator-provided rollout smoke receipt, 7/7 AI architecture gap, production-guarded promotion accounting.
- **아직 닫히지 않은 것:** full-commercial science claim promotion은 `SCI-CLAIM`으로 남아 있으며,
  세부적으로 GPCR broad-family claim과 OpenMM full all-atom/MM-GBSA/FEP+ claim boundary가 open이다.
- **닫히지 않은 것(제품 역량):** 과학 엔진 정밀도(가장 큰 진짜 갭), hosted/SaaS 운영 성숙도,
  범용 claim 확장, 외부 표준 벤치마크, 제품 UX.
- **핵심 보정:** accounting이 green이라는 것은 "회계상 닫힘 + fail-closed 유지"를 의미하며,
  **"OpenMM/Schrödinger급 정밀도 제품이 완성됐다"는 뜻이 아니다.**

---

## 1. "완전한 독립 상용 제품"의 정의 (목표 명세)

본 문서가 기준으로 삼는 완성 상태는 다음 4축을 동시에 만족하는 제품이다.

| 축 | 목표 |
|---|---|
| **과학적 정밀도** | 외부 엔진 없이, 공개 벤치마크(DockQ/LDDT-PLI/pose RMSD/MM-GBSA 상관)에서 방어 가능한 수치 |
| **기능 완결성** | 구조 입력 → 분석 → 도킹 → 스코어링 → 랭킹 → MD refine → 결과 번들까지 end-to-end 자동 실행 |
| **독립 실행성** | AutoDock/Vina/OpenMM/Schrödinger 등 외부 도킹·MD 엔진 무의존(RDKit 등 informatics는 허용) |
| **상용 운영성** | self-hosted/on-prem 배포, 라이선스, 모니터링, SLA, 멀티테넌시, 결과 재현성 |

---

## 2. 갭 카테고리별 분석

우선순위 표기: **P0**(제품 차단) · **P1**(핵심 정밀도/실행) · **P2**(확장/신뢰) · **P3**(운영 성숙).

---

### A. 과학 엔진 정밀도 — *가장 큰 실제 갭* (P0/P1)

**현황**
- `core/topology.py`: 기본은 claim-safe **placeholder alanine**으로 시작하지만,
  sequence-mapped 2-bead(CA + virtual sidechain)와 CA/SC block-layout residue type
  alignment를 지원한다.
  All-atom 경로(`AdResS`)는 `ADRESS_PRODUCTION_ALLOWED` 환경변수로 게이트되어 사실상 비활성.
- `core/forcefield.py`: fast-tier LJ 계열 힘장에 sequence-mapped residue class별
  coarse sigma/epsilon mixing, screened acidic/basic residue charge proxy,
  restricted CA backbone harmonic bond/angle terms를 더했고, Rust/HIP 비결합 커널은
  단일 파라미터 fast path로 유지된다. `DataGenerator` runtime profile은 coarse
  backbone bond/angle param을 ForceField로 전달하며, trajectory engine CLI/cache key도
  coarse forcefield param surface를 노출한다.
- `core/allatom_forcefield.py`, `core/mm_gbsa.py`, `core/explicit_solvent.py`,
  `core/fep.py`: internal typed united-atom all-atom tier, periodic torsion/improper
  proxy, common ligand halogen(`F/Cl/Br/I`) atom typing coverage surface,
  ionizable/charged-residue local chemistry typing surface,
  formal charge proxy claim guard,
  unsupported metal/cofactor-like element fail-closed reporting,
  metal/cofactor coordination candidate claim guard,
  internal proxy parameter calibration claim guard,
  solvent/FEP calibration claim guard,
  structure-quality/interface proxy claim guard,
  public benchmark blocker linkage guard,
  GB/SA MM-GBSA proxy, TIP3P-like explicit shell recheck, FEP scaffold가 존재한다. 최신
  `runs/engine_refinement_tier_readiness_current.json`은 full refine stack smoke를 포함해
  `check_count=36`, `pass_count=36`, `blocked_count=0`이며,
  `refine_tier_atom_typing_coverage_surface`는
  `supported_elements=H,C,N,O,S,P,F,CL,BR,I`, `default_atom_count=0`,
  `coverage_fraction=1.0`과 summary `atom_typing_coverage_surface_ready=true`를 확인한다.
  `refine_tier_unsupported_metal_fail_closed_surface`는 `Zn/Mg`가 support로
  오인되지 않고 `blocked_atom_typing_coverage`로 노출되는지 확인한다.
  `refine_tier_metal_cofactor_coordination_claim_guard`는 Zn 주변 N/O/S donor
  후보 3개를 coordination surface로 artifact화하지만
  `claim_grade_metal_cofactor_parameterization_ready=false`와
  `metal_cofactor_parameterization_not_supported` blocker로 금속 parameter claim을 막는다.
  `refine_tier_charged_residue_atom_typing_surface`는 carboxylate/basic N/phosphate/
  thiolate-like local chemistry를 타입으로 분리하고
  `charged_residue_atom_typing_surface_ready=true`를 노출하지만,
  `claim_grade_charged_parameterization_ready=false`로 formal protonation 및 calibrated
  charge parameter claim은 열지 않는다.
  `refine_tier_formal_charge_proxy_claim_guard`는 local formal charge hypothesis
  (`formal_charge_proxy_net_e=-2.0`)를 artifact화하지만
  `claim_grade_formal_charge_ready=false`로 protonation/calibration claim을 유지 차단한다.
  `refine_tier_parameter_calibration_claim_guard`는
  `parameter_calibration_status=internal_proxy_uncalibrated`,
  `claim_grade_parameterization_ready=false`를 유지한다.
  `refine_tier_solvent_fep_calibration_claim_guard`는 GB/SA, explicit shell, FEP
  surface가 finite로 계산되는지 확인하지만 `claim_grade_solvent_fep_calibration_ready=false`,
  `explicit_solvent_md_sampling_not_validated`, `fep_holdout_calibration_not_validated`로
  solvent/FEP claim을 막는다.
  `refine_tier_structure_quality_interface_claim_guard`는 MolProbity-like clashscore proxy와
  receptor-ligand interface contact coverage를 계산하지만
  `claim_grade_structure_quality_ready=false`, `external_molprobity_not_available`,
  `native_complex_benchmark_not_ready`로 외부 metric parity claim을 막는다.
  `refine_tier_public_benchmark_blocker_linkage`는 public benchmark gate의
  `blocked_refine_tier_public_benchmark_readiness`, `blocker_count=6`,
  `work_order_row_count=8`을 engine readiness summary에 직접 연결한다.
  pose RMSD/LDDT-PLI/DockQ proxy metric surface와 MM-GBSA calibration claim guard를
  함께 확인한다. `claim_grade_public_benchmark_ready=false`라서 공개 benchmark claim은
  여전히 열지 않는다. 같은 summary는 `claim_promotion_allowed=false`,
  `claim_promotion_blocker_count=6`, `claim_promotion_action_row_count=6`을 노출하며 blocker를
  public benchmark, parameter calibration, metal/cofactor parameterization,
  protonation/charge calibration, solvent/FEP public-pair calibration,
  external structure-quality parity로 고정한다.
  `claim_promotion_action_rows`는 각 blocker별 `required_evidence`,
  `owner_action`, `gate_or_artifact`, `external_dependency`, `claim_boundary`,
  `blocking_signals`를 기계 판독 가능한 action-board로 제공한다. 따라서 현재 병목은
  "무엇이 막혔는가"에서 "각 claim blocker를 닫기 위해 어떤 operator evidence와
  gate artifact가 필요한가"까지 추적 가능하다. CLI 실행 시 같은 내용은
  `runs/engine_refinement_claim_promotion_action_board_current.csv`로도 생성되어
  operator review/work tracking에 바로 사용할 수 있다. 이 CSV는
  `product_launch_r4_preflight` summary와 `deploy/product_release_bundle.py`의
  `engine_refinement_claim_promotion_action_board_recorded` check, 그리고
  `product_release_source_of_truth_gate` freshness artifact spec에도 연결되어
  릴리스 검증 묶음에서 누락되거나 stale 상태로 남지 않는다. 같은 CSV는
  `goal_operator_action_board_current.json`의 `product_engine_refinement` lane과
  `goal_operator_intake_kit_current/manifest.json`의
  `engine_refinement_claim_promotion_action_board` entry에도 노출되어,
  operator-facing 작업판에서 claim blocker evidence 수집 상태를 직접 추적한다.
  `tools/product/build_engine_refinement_claim_evidence_receipt.py`와
  `config/engine_refinement_claim_promotion_evidence_receipt_current.csv`는 action board
  다음 단계인 evidence receipt gate를 제공한다. 현재 기본 template은 6개 blocker row를
  모두 포함하지만 placeholder evidence라
  `runs/engine_refinement_claim_evidence_receipt_current.json`이
  `blocked_engine_refinement_claim_evidence_receipt`,
  `claim_promotion_evidence_receipt_ready=false`, `blocked_row_count=6`으로 남는다.
  이 receipt 상태는 engine readiness, R4 preflight, goal audit, goal operator intake kit,
  operator packet, handoff, release bundle, release source-of-truth freshness에 연결되어
  claim-grade 증거 수집/승인 상태가 숨지 않는다.
  최신 `runs/product_goal_completion_audit_current.json`도 이를
  `R9_engine_refinement_claim_promotion` release blocker로 흡수해,
  scope closure가 green이어도 refine-tier claim promotion evidence가 없으면
  `goal_complete=false`가 유지된다. 최신 audit summary는
  `release_blocker_fail_count=2`,
  `release_blocker_requirement_ids=[R8_full_scope_claim_closure, R9_engine_refinement_claim_promotion]`,
  `primary_release_blocker_requirement_id=R8_full_scope_claim_closure`,
  `primary_release_blocker=full_scope_claim_closure_not_ready`를 노출해,
  legacy upstream bottleneck label과 별개로 현재 full-commercial release blocker를
  직접 판정한다. `runs/goal_operator_action_board_current.json`은 이를
  `primary_release_blocker_action_id=product_scope_expansion:resolve_full_scope_breadth_evidence_receipt`와
  `primary_release_blocker_action_required_input=config/product_scope_breadth_evidence_receipt_current.csv`로
  operator action에 연결한다. `runs/goal_operator_intake_kit_current/manifest.json`과
  README도 같은 `primary_release_blocker_action_*` 필드를 전달해 operator handoff에서
  현재 R8 입력 파일이 숨지 않는다. 이 R9 상태는
  `runs/product_commercial_readiness_operator_packet_current.json`과
  `runs/product_commercial_readiness_handoff_bundle_current.json` summary에도
  `engine_refinement_claim_promotion_*` 필드 및
  `/product/commercial-readiness-operator-packet`,
  `/product/commercial-readiness-handoff-bundle`,
  `/product/engine-refinement-claim-evidence-receipt` API surface로 전파되어, handoff 단계에서도
  claim-grade evidence 병목이 숨지 않는다. handoff bundle artifact reference manifest는
  engine refinement action board, receipt JSON, receipt CSV를
  `local_engine_refinement_claim_*` reference로 추적한다.
  `runs/product_release_bundle_current.json`도
  `product_goal_completion_audit` artifact,
  `product_full_commercial_blocker_evidence_matrix` artifact,
  `product_goal_completion_audit_full_claim_boundary_recorded` check,
  `product_full_commercial_blocker_evidence_matrix_recorded` check를 포함해,
  restricted release bundle review에서도 full commercial science claim 미완료가
  명시적으로 보인다.
- `tools/accounting/build_goal_bottleneck_briefing.py`와 `/goal/status`는 release
  burndown이 clear여도 `product_goal_completion_audit`의 R8/R9 release blockers를
  active 병목으로 우선 노출한다. 따라서 restricted release가 green인 상태에서도
  full-scope transporter evidence와 refine-tier claim-grade calibration/parity
  미완료가 상위 상태 API에서 사라지지 않는다. `/goal/status`는
  `full_commercial_release_blocker_ids`,
  `restricted_release_allowed`, `full_commercial_release_allowed`,
  `full_commercial_release_blocker_visibility_ready`,
  `completion_audit_release_blocker_bottleneck_count`, 그리고
  `commercial_readiness_handoff_bundle_artifact_reference_count=28`를 함께 노출한다.
  또한 `product_goal_primary_release_blocker_requirement_id`,
  `product_goal_primary_release_blocker`, `primary_release_blocker_action_id`,
  `primary_release_blocker_action_required_input`을 goal operator action board/intake
  kit에서 직접 전달해 첫 operator 입력 파일을 `/goal/status`에도 고정한다.
  같은 status surface는
  `full_commercial_blocker_evidence_matrix_*` 요약 키로 matrix status, row count,
  blocked row count, approval token count, 첫 blocked release blocker/evidence row도
  함께 노출한다. 최종 `goal_release_decision_gate_current.json`도 matrix를
  `product_full_commercial_blocker_evidence_matrix_*` summary와
  `product_full_commercial_blocker_evidence_matrix_recorded` row로 노출해,
  restricted release source-of-truth가 green이어도 full commercial R8/R9 receipt
  미완료가 decision packet에서 사라지지 않는다. 같은 decision gate는
  `goal_bottleneck_briefing_current.json`의 `full_commercial_evidence_receipt_*`
  summary도 `goal_bottleneck_briefing_full_commercial_evidence_receipt_*` 키와
  `goal_bottleneck_briefing_full_commercial_receipts_recorded` row로 흡수해,
  operator handoff receipt 묶음 자체가 최종 packet에서 누락되지 않게 한다.
  `tools/run_product_release_current_refresh.py --execute`의 final-gate verification도
  이 decision linkage를 exact field로 요구해 final refresh green 상태에서 해당
  summary가 조용히 빠지는 회귀를 막는다.
  최신 decision summary는
  `release_allowed=true`, `restricted_release_allowed=true`와 별개로
  `full_commercial_release_allowed=false`,
  `full_commercial_release_blocker_ids=[R8_full_scope_claim_closure,
  R9_engine_refinement_claim_promotion, MASTER:SCI-CLAIM]`,
  `primary_full_commercial_release_blocker_id=R8_full_scope_claim_closure`를 노출한다.
  `goal_api_surface_contract_current.json`은 이 R8/R9 + primary release blocker action +
  commercial handoff visibility를
  `goal_full_commercial_bottleneck_visibility_present` check로 고정하며 최신
  `check_count=9`, `pass_count=9`, `missing_full_commercial_visibility_token_count=0`이다.
  source-of-truth의 `goal_api_surface_contract_semantic_ready` row도
  `missing_status_key_count=0`, `missing_full_commercial_visibility_token_count=0`,
  `missing_fail_closed_flag_count=0`, `blocker_count=0`을 exact field로 검증한다.
- `tools/product/build_product_full_commercial_blocker_evidence_matrix.py`는 R8/R9
  release blocker evidence receipt를 한 matrix로 집계한다. 최신
  `runs/product_full_commercial_blocker_evidence_matrix_current.json`은
  `blocked_product_full_commercial_blocker_evidence_matrix`,
  `release_blocker_visibility_ready=true`, `matrix_row_count=12`,
  `blocked_matrix_row_count=12`, `approval_token_count=2`라서 full commercial
  evidence receipt 미충족이 source-of-truth, release bundle, handoff, 그리고
  `/product/full-commercial-blocker-evidence-matrix` API surface에서 한 번 더 드러난다.
- `tools/product/build_product_scope_breadth_evidence_receipt.py`와
  `config/product_scope_breadth_evidence_receipt_current.csv`는 R8 full-scope
  blocker별 operator evidence receipt를 R9 claim-evidence receipt와 같은
  fail-closed 경계로 분리한다. 현재 receipt는 placeholder evidence를 막아
  `blocked_product_scope_breadth_evidence_receipt`,
  `full_scope_evidence_receipt_ready=false`, `blocked_row_count=6`,
  `first_blocked_scope_blocker_id=direct_binding_evidence_missing`,
  `first_blocked_evidence_artifact=OPERATOR_FILL_LOCAL_EVIDENCE_JSON`,
  `most_common_row_blocker=operator_placeholders_unfilled`이다. full-commercial
  blocker matrix와 `/goal/status`도 이 first-blocked diagnostics를
  `full_commercial_blocker_evidence_matrix_first_blocked_*` 및
  `full_commercial_blocker_evidence_matrix_*_most_common_row_blocker` 필드로 전달한다.
  `/goal/status`는 matrix 요약과 별도로
  `product_scope_breadth_evidence_receipt_*` 및
  `engine_refinement_claim_evidence_receipt_*` 직접 필드도 제공해, R8/R9 receipt
  status, CSV, approval token, row counts, first-blocked diagnostics, required
  blocker 목록을 goal API contract 안에 고정한다.
  `product_goal_completion_audit`의 `R8_full_scope_claim_closure` row는 이 receipt를
  evidence artifact와 observed field로 직접 사용하며, `goal_operator_action_board`는
  `resolve_full_scope_breadth_evidence_receipt` action을 노출한다.
  `goal_operator_intake_kit_current/manifest.json`은
  `product_scope_breadth_evidence_receipt` entry와 copied template으로
  `config/product_scope_breadth_evidence_receipt_current.csv`를 operator handoff에
  포함한다. 같은 manifest summary는 R8/R9 receipt 묶음을
  `full_commercial_evidence_receipt_*` 필드로 집계해 entry count 2, template present
  2/2, approval token 2개, source gate statuses, required input CSVs를 직접 노출하고
  `goal_bottleneck_briefing_current.json`도 같은 summary를 흡수해 R8/R9
  completion-audit 병목에서 operator receipt handoff가 누락되지 않게 한다.
  `/goal/status`도 이를 `operator_intake_kit_full_commercial_evidence_receipt_*` 및
  `bottleneck_briefing_full_commercial_evidence_receipt_*` 키로 전달한다.
  같은 R8 receipt 상태는
  `runs/product_commercial_readiness_operator_packet_current.json`과
  `runs/product_commercial_readiness_handoff_bundle_current.json` summary의
  `product_scope_breadth_evidence_receipt_*` 필드 및
  `/product/commercial-readiness-operator-packet`,
  `/product/commercial-readiness-handoff-bundle`,
  `/product/scope-breadth-evidence-receipt` API surface에도 전파된다.
  handoff bundle의 artifact reference manifest는
  `product_scope_breadth_evidence_receipt` JSON과 CSV를 필수 local
  scope-breadth receipt evidence로 추적하며
  `local_missing_artifact_reference_count=0`, `artifact_reference_count=28`이다.
- `product_release_source_of_truth_gate_current.json`은
  `product_api_contract_current.json`,
  `product_service_boundary_contract_current.json`,
  `self_hosted_license_distribution_audit_current.json`,
  `third_party_license_review_gate_current.json`,
  `product_scope_breadth_closure_checklist_current.json`,
  `product_scope_breadth_evidence_receipt_current.json`,
  `goal_operator_intake_kit_current/manifest.json`,
  `product_commercial_readiness_execution_ladder_current.json`,
  `goal_api_surface_contract_current.json`, `goal_bottleneck_briefing_current.json`,
  `product_full_commercial_blocker_evidence_matrix_current.json`,
  `production_ai_registry_promotion_operator_receipt_current.json`,
  `product_pose_sampling_readiness_current.json`,
  `cameo_official_result_fetch_preflight_current.json`,
  `cameo_validation_operations_dossier_current.json`의
  freshness 및 semantic-ready 상태를 함께 검증한다. 최신 full refresh 후
  source-of-truth는 `row_count=84`, `pass_count=84`, `blocker_count=0`,
  `artifact_row_count=57`, `semantic_status_row_count=25`,
  `release_refresh_command_count=70`, `stale_artifact_count=0`,
  `semantic_status_blocker_count=0`, `readme_drift_count=0`이다.
  `/product/self-hosted-license-distribution-audit` API surface도 같은 audit의
  hard blocker/operator review 경계를 직접 노출한다. R8/R9 evidence
  receipt 자체도 `product_scope_breadth_evidence_receipt_blocked_semantic_ready`,
  `engine_refinement_claim_evidence_receipt_blocked_semantic_ready` row로 고정되어
  placeholder evidence, 6/6 blocked rows, approval token requirement, first-blocked
  diagnostics를 source-of-truth에서 직접 검증한다.
  `product_pose_sampling_readiness_semantic_ready` row는 deterministic local
  pocket placement, 6-start pose ensemble, RMSD diversity clustering,
  bounded cross-docking/induced-fit guard, 그리고 claim-grade pose accuracy
  blocked posture를 exact/min field로 검증한다. 따라서 AI decision graph의
  `pose_generation_contract` node가 단순 capability/preflight 문구가 아니라
  실제 local pose sampling smoke artifact에 연결되며,
  `/product/pose-sampling-readiness` API surface도 같은 artifact를 fail-closed
  상태로 노출한다.
  `product_ai_report_explanation_packet_semantic_ready`와
  `product_ai_report_ux_contract_semantic_ready`는 core/full decision graph 순환을
  분리한 뒤 고객-facing AI report semantic readiness 안으로 닫혔다.
- `product_ledger_privacy_scan_current.json`은 product/commercial readiness artifacts뿐
  아니라 `goal_readiness_rollup`, `goal_operator_action_board`,
  `goal_operator_intake_kit`, `goal_release_burndown_work_order`,
  `goal_api_surface_contract`,
  `goal_bottleneck_briefing`, `product_full_commercial_blocker_evidence_matrix`,
  `production_ai_registry_promotion_operator_receipt`
  JSON도 scan 대상과 source-of-truth dependency로 포함한다.
  따라서 R8/R9 상위 API/병목 visibility surface에 raw molecular payload가 섞이면
  release privacy gate에서 fail-closed로 드러난다. 최신 scan은 `leak_count=0`이다.
- `tools/product/build_refine_tier_public_benchmark_readiness.py`: curated 공개
  pose/free-energy benchmark intake를 별도 fail-closed gate로 판정한다.
  `config/refine_tier_public_benchmark_intake_current.csv`는 required column header를
  tracked template로 제공한다. 현재 기본 산출물
  `runs/refine_tier_public_benchmark_readiness_current.json`은
  `blocked_refine_tier_public_benchmark_readiness`, `input_csv_present=true`,
  `row_count=0`, `claim_grade_public_benchmark_ready=false`, `blocker_count=6`,
  `operator_work_order_ready=true`, `work_order_row_count=8`이다.
  같은 상태는 `runs/engine_refinement_tier_readiness_current.json` summary의
  `public_benchmark_gate_status`, `public_benchmark_blockers`,
  `public_benchmark_work_order_row_count=8`,
  `public_benchmark_operator_work_order_ready=true`로도 노출된다.
  `runs/refine_tier_public_benchmark_work_order_current.csv`는 최소 fit/holdout
  split을 갖춘 8개 operator fill template row를 생성해 curated public benchmark
  intake의 다음 수동 단계를 구체화한다.
  `tools/product/apply_refine_tier_public_benchmark_work_order.py`는 채워진 work-order를
  intake candidate로 변환하기 전 placeholder/license/external-engine/metric fields를
  fail-closed로 검증한다. tracked intake CSV를 실제 갱신하는 `--write-intake` 경로는
  `APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE` 승인 토큰 없이는 막힌다.
  현재 placeholder work-order 기준 apply 산출물은
  `blocked_refine_tier_public_benchmark_work_order_apply`, `blocked_row_count=8`,
  `candidate_intake_written=false`, `intake_written=false`이다.
- `core/integrator.py`: Langevin 적분기(2-bead 수준).
- AI 보정(`core/score_residual.py`, `core/onsps_backmap.py`)은 **bounded residual** 로만 사용.

**갭 (근본 원인)**
- product lane은 아직 "조대화(coarse-grained) + internal refine scaffold" 단계이지
  **claim-grade all-atom 정밀 MD/도킹 엔진이 아니다.**
- 남은 미구현/미검증: metal/cofactor calibrated parameterization 및 coverage expansion,
  charged-residue formal protonation-state assignment, calibrated atom-level charge/torsion/improper parameterization,
  solvent/FEP public-pair calibration,
  curated 공개 pose/free-energy benchmark intake row 입력 및 통과, 외부 MolProbity/OpenStructure 구조 품질 검증,
  공개 ΔG benchmark 상관.
- 외부 정밀 엔진 없이 정밀도를 내려면 force field·solvent·sampling을 자체 구현해야 함.

**구현 방향**
1. **Force field 정식화**: internal typed united-atom scaffold를 wider residue/ligand atom typing,
   calibrated charge, torsion/improper, bonded/nonbonded parameter set으로 승격.
2. **Solvent 모델**: GB/SA와 TIP3P-like shell scaffold를 공개 complex set에서 calibration하고,
   이후 explicit TIP3P dynamics 옵션으로 확장.
3. **Sampling/자유에너지**: MM-GBSA end-state 결합 자유에너지 → alchemical FEP/TI scaffold calibration.
4. **정밀도 tier 정책**: `fast(2-bead 스크리닝)` → `refine(internal all-atom/GB-SA/FEP scaffold)` 2-tier를
   HTVS 파이프라인의 stage 정책으로 명시하고, curated public benchmark 통과 전 claim은 restricted로 유지.
5. **Rust/HIP 커널 결합**: nonbonded 정밀 커널을 native backend에 실제 결합(`rust_hip_backend.py` 확장),
   `FORCE_RUST_HIP` 요구 모드를 정밀 tier 기본값으로.

**완료 정의**: 공개 복합체 셋에서 pose RMSD/DockQ/LDDT-PLI 수치 산출 + MM-GBSA가 실험 ΔG와
상관(Spearman) 보고, 외부 엔진 호출 0건.

---

### B. 리간드 도킹 파이프라인 완결성 (P0/P1)

**현황**
- HTVS stage2/3 + two-pass(rank → top-K 4-bead) + topo corrector + stage2 skip router 연결됨
  (`tools/run_ligand_htvs_pipeline.py`, `run_ligand_backmapping_scoring.py`).
- composite v7 스코어 + force-residual shortlist hook 존재.
- `tools/product/build_product_pose_sampling_readiness.py`는 `core/pose_generation.py`와
  `core/pocket_detection.py`를 실제로 호출해 ligand-guided pocket detection,
  deterministic 6-start local pose ensemble, RMSD clustering, bounded
  cross-docking/induced-fit guard를 smoke-test한다. 최신
  `runs/product_pose_sampling_readiness_current.json`은
  `product_pose_sampling_readiness_ready`, `check_count=6`, `pass_count=6`,
  `blocker_count=0`, `pose_count=6`, `cluster_count=6`,
  `cross_docking_pose_count=4`이며, 동시에
  `claim_grade_pose_accuracy_ready=false`,
  `claim_grade_induced_fit_ready=false`,
  `claim_grade_cross_docking_ready=false`를 유지한다.
  이 artifact는 product AI decision graph의 `pose_generation_contract` node,
  product release bundle의 `product_pose_sampling_readiness_recorded` check,
  source-of-truth freshness/semantic row, 그리고
  `/product/pose-sampling-readiness` API surface에 연결된다.
- API runner profile promotion readiness는 green이지만, operator promotion decision은
  별도 receipt로 fail-closed 추적한다. `tools/product/build_api_runner_profile_promotion_operator_receipt.py`는
  `runs/api_runner_profile_promotion_operator_template_current.csv`의 decision/token/review
  fields를 검증하고, 현재 빈 template 기준
  `blocked_api_runner_profile_promotion_operator_receipt`,
  `operator_receipt_ready=false`, `blocked_row_count=4`,
  `first_blocked_profile_id=backmapping_scoring.example`,
  `most_common_row_blocker=operator_decision_missing`으로 남겨 실제 profile edit/runner execution과 readiness
  accounting을 분리한다. release bundle, source-of-truth, goal operator intake kit,
  `/product/api-runner-profile-promotion-operator-receipt` API surface는 이 receipt를
  필수 산출물로 기록한다.

**갭**
- **포즈 생성(pose sampling)** 단계는 이제 local deterministic smoke와 release
  source-of-truth 연결은 생겼지만, 아직 공개 pose RMSD/LDDT-PLI/DockQ benchmark
  parity나 validated induced-fit/cross-target docking claim은 없다. 즉
  컨포머 생성, 결합 포켓 탐색, 유연 도킹(side-chain/backbone flexibility),
  포즈 다양성/클러스터링 표준화의 "기능 surface"는 보강됐고,
  "정밀도 claim"은 계속 차단되어 있다.
- **포켓 검출(binding site detection)** 자동화: 현재 AQP1 등에서 pocket centroid placeholder 흔적.
- **스코어 함수 보정(calibration)**: 점수 → 결합친화도(kcal/mol) 변환의 물리적 근거/보정셋.

**구현 방향**
1. 컨포머/포즈 생성기 표준화(RDKit ETKDG + 자체 포즈 옵티마이저), 포즈 클러스터링.
2. 포켓 검출 모듈(기하/에너지 기반) → target metadata pocket fingerprint 자동 채움.
3. 스코어→ΔG 보정: 공개 결합친화도 데이터로 calibration curve 학습 + claim-safe 변환 정책.
4. 유연 도킹: 활성부위 side-chain rotamer 샘플링(우선), backbone는 ensemble docking.

**완료 정의**: 입력 SMILES + 타깃 구조 → 포즈 앙상블 + 보정된 ΔG + 신뢰구간을 외부 엔진 없이 산출.

---

### C. AI Residual / Production 추론 주체 전환 (P1)

**현황**
- ROCm/HIP execution environment, force derivation validation, training data,
  checkpoint sidecar/preflight는 ready이고, checkpoint-readiness acceptance matrix는
  `8`개 stage 중 `7`개 ready다.
- production AI 자체는 아직 `default_residual_mode=shadow`,
  `production_promotion_allowed=false`, `trained_model_checkpoint_count=0`으로
  registry guarded promotion에서 blocked다.
- checkpoint readiness와 promotion workbench의 next-action은 이 상태를
  `production_promotion_allowed`, `customer_facing_mutation_flags`,
  `default_residual_mode_guarded`, `trained_model_checkpoint_count_positive`가
  남은 registry gate라는 형태로 노출한다. ROCm/GPU receipt/training/preflight는
  현재 ready인 하위 gate로 남고, operator-facing 다음 행동은 trained production
  checkpoint를 registry에 등록/승격한 뒤 registry와 checkpoint-readiness gate를
  재실행하는 것이다. 이 정보는
  `registry_promotion_missing_gate_ids` 및
  `production_ai_checkpoint_registry_promotion_missing_gate_ids`로도 노출되어
  product API contract, goal completion audit, `/goal/status`에서 구조화된 병목으로
  추적된다. 현재 registry blocker에는
  `residual_model_registry_guarded_promotion` operator completion packet도 붙어 있어,
  필요한 registry fields와 validation chain은 product API, goal completion audit,
  `/goal/status`에서 보이지만 실제 checkpoint 생성·registry promotion은 여전히
  실행하지 않는다. `goal_operator_action_board_current.json`의 primary action은
  ready GPU return을 다시 요구하지 않고
  `complete_residual_registry_guarded_promotion`을 가리키며,
  `goal_operator_intake_kit_current/manifest.json`은
  `production_ai_registry_promotion` entry를 operator input required로 노출한다.
  이 entry는 이제 `config/production_ai_registry_promotion_operator_receipt_current.csv`
  template/intake와 `runs/production_ai_registry_promotion_operator_receipt_current.json`
  source gate를 갖는다. receipt는
  `blocked_production_ai_registry_promotion_operator_receipt`,
  `first_blocked_row_blocker=operator_placeholders_unfilled`,
  `approval_token_required=APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION`,
  `observed_registry_default_residual_mode=shadow`,
  `observed_registry_trained_model_checkpoint_count=0`을 기록하며,
  CSV 값과 residual registry/checkpoint-readiness artifact가 어긋나면 ready가 되지 않는다.
  `/product/commercial-readiness-operator-packet`,
  `/product/commercial-readiness-execution-ladder`,
  `/product/commercial-readiness-handoff-bundle`,
  `/product/production-ai-registry-promotion-operator-receipt`도
  `production_ai_registry_promotion_*` alias, completion packet,
  `production_ai_registry_promotion_operator_receipt_*` status/token/observed blocker
  fields를 전달한다. `/goal/status`도 같은
  `production_ai_registry_promotion_operator_receipt_*` status/token/observed blocker
  fields를 handoff bundle summary에서 끌어와 goal API surface에 고정한다.
  handoff bundle artifact reference manifest에는
  `runs/production_ai_registry_promotion_operator_receipt_current.json`과
  `config/production_ai_registry_promotion_operator_receipt_current.csv`가 local required
  receipt/template으로 포함된다.

**갭**
- `residual_model_registry`가 customer-facing guarded promotion을 허용하지 않고,
  product goal completion audit도 여전히 blocked다.
- trained checkpoint accounting과 score/ranking mutation policy가 실제 고객 요청 경로에
  연결되기 전까지 production AI는 shadow-only다.
- residual이 **물리 코어 위 bounded corrector** 라는 경계는 유지되어야 함(정밀도 갭을 AI로 덮지 않기).

**구현 방향**
1. residual registry guarded promotion 조건을 trained checkpoint/promotion policy와 연결.
2. customer-facing score/ranking mutation disabled 경계를 유지하면서 operator-approved
   promotion path만 허용.
3. shadow → assist → production_guarded 승격 시 **abstention/uncertainty 게이트**를 제품 SLA에 노출.

**완료 정의**: 정밀 tier 라벨로 학습된 residual이 production_guarded로 고객 노출 가능,
abstention 사유가 결과 번들에 명시.

---

### D. 단백질 구조 분석 surface (P1/P2)

**현황**
- structure deterministic CA true-metric backend pass, CASP17 atlas 조직화.
- product capability surface: structure analysis report ready(accounting).

**갭**
- 구조 품질 지표(MolProbity, clash score, Ramachandran), 인터페이스/복합체 커버리지,
  구조 비교(superposition, TM-score/LDDT) 제품 surface 표준화.
- 입력 다양성: PDB/mmCIF, 멀티체인, 막단백질(membrane) 전처리.

**구현 방향**
1. 구조 품질 리포트 모듈(clash/rotamer/Ramachandran/LDDT) — 공개 기준 재현.
2. 구조 정렬/비교 API(TM-score/LDDT-PLI) 표준화.
3. 막단백질·멀티체인 전처리 파이프라인(이미 transporter membrane readiness 흔적 존재).

**완료 정의**: 임의 PDB 입력 → 품질 리포트 + 정렬/비교 지표를 표준 포맷으로 산출.

---

### E. API ↔ Engine 실행 wiring (P0)

**현황 (가장 빠르게 풀 수 있는 차단 갭)**
- 상용 API surface + security middleware + SQLite job store + signed result manifest 존재.
- 일반 `/simulate` 요청은 **의도적 fail-closed**, `runner_profile_id` + operator-approved validated runner profile만 실행.
- `core/forcefield.py:17`, `core/topology.py:38`이 restricted analysis engine임을 명시.
- `runs/api_customer_flow_release_evidence_current.json`은 현재
  `api_customer_flow_release_evidence_ready`, `formal_release_evidence_ready=true`,
  `clean_install_flow_ready=true`, `bundle_validation_ready=true`, `blocker_count=0`이다.
  `runs/product_launch_r4_preflight_current.json`도 `product_launch_r4_preflight_ready`,
  `check_count=7`, `pass_count=7`, `blocker_count=0`이다. 단, preflight 자체는
  `authorized_for_external_mutation=false`, `launch_executed=false`,
  `external_state_mutated=false`로 실제 mutation과 분리된다.
- `runs/product_rollout_execution_smoke_receipt_current.json`은 preflight 이후의 별도
  R4-approved operator 실행 receipt를 read-only로 검증하며 현재
  `product_rollout_execution_smoke_receipt_ready`, `receipt_csv_present=true`,
  `rollout_executed=true`, `external_state_mutated=true`다.
  `/product/rollout-execution-smoke-receipt`는 이 receipt를 endpoint mutation과
  분리해 직접 노출한다. 따라서
  `deploy_ops_legal_gap_closure_current.json`은 `deploy_ops_legal_gap_closure_complete`,
  `open_gap_ids=[]`이고, `master_gap_closure_rollup_current.json`의 open gap은
  `SCI-CLAIM` 하나다.

**갭**
- 실제 docking/MD 실행과 future rollout mutation은 여전히 explicit operator approval
  token과 R4 확인에 묶여 있어, 배포/remote mutation이 자동으로 열리지는 않는다.

**구현 방향**
1. 완료된 R4 preflight와 rollout execution smoke receipt를 release evidence로 유지하고,
   future rollout마다 Target/Action/Impact/Risk/Rollback/Verification과 explicit
   operator approval을 다시 요구한다.
2. fail-closed 정책은 유지하되, **restricted scope 안에서는** profile 기반 무인 실행 경로를 SLA로 보장.
3. dispatch worker(`api/docking_dispatch.py`, `run_api_docking_dispatch_worker.py`) 상시 운영화 + 모니터링.

**완료 정의**: restricted scope 타깃에 대해 인증된 클라이언트가 API로 도킹 작업 제출 →
durable queue → worker 실행 → signed 결과 번들 회수까지 무인 동작.

---

### F. Hosted / 배포 / 운영 인프라 (P1/P3)

**현황**
- `deploy/`: docker-compose, systemd, k8s manifest, model registry, rollout/rollback runbook 1차 존재.
- monitoring/`: `/metrics`, alert rules, closed-loop alert smoke 1차 통합.
- R4 launch preflight는 현재 `product_launch_r4_preflight_ready`,
  `check_count=7`, `pass_count=7`, `blocker_count=0`이다. preflight는 여전히
  `authorized_for_external_mutation=false`, `launch_executed=false`,
  `external_state_mutated=false`라서 실행 권한과 분리된다.
- actual rollout execution smoke receipt는 operator-provided receipt 기준
  `product_rollout_execution_smoke_receipt_ready`이며,
  `/product/rollout-execution-smoke-receipt`로도 조회된다. deploy/ops/legal rollup은 닫혔다.
  master full-commercial rollup은 GPCR broad-family와 OpenMM full all-atom/MM-GBSA/FEP+
  science claim promotion(`SCI-CLAIM`) 때문에 pending이다.

**갭**
- 실제 pager provider delivery, ingress certificate(TLS) smoke, operator-approved rollout
  receipt는 1차 검증됐다. 남은 운영 갭은 반복 가능한 환경별 SLO tuning, DR/backup,
  멀티테넌시 격리·쿼터, 작업 영속성/재시도의 운영 검증이다.

**구현 방향**
1. 실배포 smoke: TLS 인증서 + ingress, pager 실연동, rollout 실행 후 health/rollback 검증.
2. 멀티테넌시: tenant별 쿼터/격리(이미 tenant header/rate limit 존재) 운영 정책화.
3. 관측성: SLI/SLO 정의(작업 지연, 성공률, GPU 활용), 대시보드.

**완료 정의**: on-prem/self-hosted 1-command 배포 + TLS + 모니터링/알림 + rollback이 실배포에서 검증.

---

### G. Scope / Claim 확장 (P2)

**현황**
- 허용 family: `gpcr` / `ion_channel` / `kinase`. 차단: `transporter_domain_promotion`,
  `general_protein_ligand_platform`.
- primary backlog: `scope_breadth.transporter.AQP1.core_non_binder_01`(deferred 12건, release-blocker 아님).

**갭**
- transporter(AQP1/GLUT1) **exact 정량 negative/positive binding kcal** 근거 부재 → review-only/parked.
- breadth domain floor(CA2/PXR/IDP/all-atom) + capability surface 충족 후에만 범용 platform claim 가능.

**구현 방향**
1. transporter P0 슬롯을 **operator 정량 근거 입력**(PubMed primary / 자체 wetlab)으로 클로즈
   (워크시트: `transporter_negative_control_operator_worksheet`).
2. CA2/PXR replacement workbook 정량 reference 채우기, IDP bounded promotion lane 통과.
3. 모든 breadth domain green + capability surface 명시 플래그 후 general platform claim 승격.

**완료 정의**: 차단 claim scope 0건, 허용 family ≥ 6, general platform 플래그 명시.

---

### H. 외부 표준 벤치마크/검증 (P1/P2)

**현황**
- 자체 accuracy parity scorecard green(5/5), GPCR A1 independent repeat 양호.
- GPCR CI-low(scaleup) 0.21 vs 0.45 임계치 미달 → claim promotion blocked.

**갭**
- 공개 표준 셋(PDBbind/CASF, DockQ, CAMEO 공식 결과) 기준의 **외부 방어 가능 수치** 부재.
- GPCR CI-low 안정화(OPRM1 pose collapse, HTR2A decoy, conditional prior gating).

**구현 방향**
1. 공개 벤치마크 하니스(CASF-2016 scoring/ranking/docking power, PDBbind core set) 연결.
2. CAMEO 공식 결과 intake(외부 schedule 의존, operator approval 토큰). 현재
   `goal_operator_intake_kit_current/manifest.json`은
   `cameo_official_result_fetch_preflight` entry로
   `runs/cameo_official_result_fetch_operator_approval_template_current.csv`,
   `runs/cameo_official_result_fetch_operator_approval_intake.csv`,
   `APPROVE_CAMEO_OFFICIAL_RESULT_FETCH`를 operator handoff에 노출한다. 같은
   preflight status/template/intake/token/no-network flags는 `/goal/status`의
   `cameo_official_result_fetch_preflight_*` keys와
   `/product/cameo-official-result-fetch-preflight`에서도 확인된다.
3. GPCR CI-low: feature/data engineering + 100k 재실행으로 ≥ 0.45 + top20 안정화.

**완료 정의**: 공개 표준에서 재현 가능한 수치 리포트 + CI-low 임계치 통과로 scorer/router claim 승격.

---

### I. 제품 UX / 결과 전달 (P2)

**현황**
- viewer(자산 vendoring/pinning), result bundle 생성 계약, report UX 6/6 블록 ready(accounting).

**갭**
- 비전문가용 결과 해석(랭킹 근거, 신뢰도, abstention 사유)의 제품화된 리포트/뷰어 UX.
- 작업 진행 상태·로그·재현 정보의 고객 노출 표준화.

**구현 방향**
1. 결과 리포트: 포즈 시각화 + ΔG/신뢰구간 + 근거 evidence 링크 + claim boundary 명시.
2. 뷰어: 궤적/포즈/품질지표 인터랙티브(이미 viewer 자산 존재) + 보고서 export.

**완료 정의**: 고객이 도킹/분석 결과를 근거·신뢰도와 함께 자체적으로 해석 가능한 리포트/뷰어.

---

### J. 법무 / 라이선스 / 정리 (P3)

**현황**
- LICENSE ↔ proprietary license hash 일치, third-party(JSZip dual-license) review gate, `legal_advice_provided=false` 유지.
- storage cleanup scaffold(`delete_executed=false`), tools/ 서브패키지 리팩토링 batch2 완료.

**갭**
- 법률 최종 확인(전문가 영역), redistribution path 최종 결정.
- cleanup 실행 승인, tools/ batch3 high-reference lane 분리.

**구현 방향**
1. 라이선스 법률 검토(외부) + redistribution 결정 문서화.
2. operator-approved cleanup 실행, 패키지 분리 마무리.

**완료 정의**: 라이선스/재배포 결정 확정, 저장소 정리 완료.

---

## 3. 우선순위 로드맵 (제품 완성 경로)

```
[현재] restricted 독립 전달 (gpcr/ion_channel/kinase, accounting green)
   │
   ├─ P0  E. API↔Engine 무인 실행 wiring (restricted scope)      ← 가장 빠른 상용화 스위치
   │
   ├─ P0/P1  A. 과학 엔진 정밀도 (typed all-atom calibration + GB-SA/FEP benchmarks)  ← 가장 큰 실제 갭
   │           └─ B. 도킹 포즈 생성/포켓 검출/ΔG 보정
   │           └─ C. residual을 정밀 tier 라벨로 재학습
   │
   ├─ P1  H. 외부 표준 벤치마크(CASF/DockQ) + GPCR CI-low ≥ 0.45
   │       D. 구조 분석 surface(MolProbity/LDDT/TM-score)
   │       F. hosted 배포 실검증(TLS/pager/rollout)
   │
   ├─ P2  G. scope 확장(transporter→general platform)
   │       I. 제품 결과 UX/뷰어
   │
   └─ P3  J. 법무/라이선스/정리, 운영 성숙(멀티테넌시/DR/SLO)
```

**전략적 분리**
- **빠른 상용화(restricted):** E(실행 wiring) + F(배포 실검증)만으로 **restricted scope 상용 파일럿** 즉시 가능.
- **완전한 제품(범용·정밀):** A/B/C/H가 핵심 — 이것이 "OpenMM/Schrödinger 대체 독립 엔진"의 본질이며
  가장 큰 투자 영역.

---

## 4. 제품 완성 측정 지표 (Definition of Done)

| 영역 | 측정 지표 | 목표 |
|---|---|---|
| 정밀도 | DockQ / pose RMSD / LDDT-PLI (공개 셋) | 외부 엔진 대비 방어 가능 |
| 자유에너지 | MM-GBSA ΔG vs 실험 ΔG Spearman | 유의미한 상관 + claim-safe 변환 |
| 독립성 | 외부 도킹/MD 엔진 호출 수 | 0 |
| 실행 | restricted scope 무인 end-to-end | API→queue→worker→번들 |
| 벤치마크 | CASF-2016 scoring/ranking/docking power | 보고 가능 수치 |
| GPCR | scaleup CI-low | ≥ 0.45, top20 안정 |
| 운영 | 배포 smoke(TLS/pager/rollout/rollback) | 실배포 통과 |
| Scope | 차단 claim scope 수 | 0 (general platform 승격) |
| 신뢰성 | abstention/uncertainty 결과 노출 | 리포트/뷰어 표준화 |

---

## 5. 핵심 결론

1. **회계상 닫힘 ≠ 제품 완성.** 현재 green은 "restricted scope + fail-closed 유지"의 정직한 경계이며,
   범용 정밀 제품 완성을 의미하지 않는다.
2. **가장 빠른 상용 스위치는 R4/operator-approved rollout smoke receipt.** restricted scope의
   local evidence와 preflight는 green이므로, 명시 승인 후 실행 검증과 receipt 기록이
   self-hosted 파일럿 전환점이다.
3. **가장 큰 실제 갭은 A(과학 엔진 정밀도).** internal typed all-atom/GB-SA/explicit-shell/FEP scaffold,
   common ligand halogen/charged-residue local-chemistry/metal-coordination coverage surface, proxy benchmark metric surface는 green이지만,
   metal/cofactor parameterization·formal protonation·charge/torsion/improper calibration·curated 공개 pose/free-energy benchmark intake를 통과해야
   "외부 엔진 무의존 완전 상용 제품"이라는 claim이 성립한다.
4. **AI는 정밀도 갭을 덮는 용도가 아니라** 물리 코어 위 bounded residual로 유지해야 하며(C),
   학습 라벨이 자체 정밀 tier(A)에서 나와야 일관성이 생긴다.
5. **scope 확장(G)·외부 벤치마크(H)** 는 정밀도(A) 위에서만 방어 가능하므로, A를 선행 투자로 본다.

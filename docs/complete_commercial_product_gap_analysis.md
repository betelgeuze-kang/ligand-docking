# 완전한 독립 상용 제품(분자동역학 · 단백질분석 · 리간드도킹)까지의 갭 분석

> 작성 범위: 코드 구현 없이, 현재 저장소를 **외부 도킹/MD 엔진 의존 없는 완전한 독립 상용 제품**으로
> 발전시키기 위해 개선·구현해야 할 영역과 대략적 구현 방향을 정리한 설계 문서.
> 기간 추정은 제외하고 **영역 · 근본 원인 · 구현 방향 · 완료 정의** 중심으로 기술한다.
>
> 기존 문서와의 관계: `docs/improvement_items_remaining_work.md`(accounting 관점, 대부분 tracked-green)와
> 달리, 본 문서는 **"상용 제품으로서 실제로 부족한 것"** 을 제품 역량(capability) 관점에서 재구성한다.

---

## 0. 현재 위치 한 줄 요약

- **닫힌 것:** restricted(`gpcr` / `ion_channel` / `kinase`) 로컬 self-hosted 전달, commercial independence gate,
  7/7 AI architecture gap, production-guarded promotion accounting — 모두 artifact green.
- **닫히지 않은 것(제품 역량):** 과학 엔진 정밀도(가장 큰 진짜 갭), 실제 R4/operator-approved rollout smoke,
  hosted 인프라, 범용 claim 확장, 외부 표준 벤치마크, 제품 UX.
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
  `claim_promotion_blocker_count=6`을 노출하며 blocker를
  public benchmark, parameter calibration, metal/cofactor parameterization,
  protonation/charge calibration, solvent/FEP public-pair calibration,
  external structure-quality parity로 고정한다.
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

**갭**
- **포즈 생성(pose sampling)** 단계가 명시적으로 약함: 컨포머 생성, 결합 포켓 탐색,
  유연 도킹(side-chain/backbone flexibility), 포즈 다양성/클러스터링 표준화 필요.
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
- residual model registry `production_guarded` 승격 accounting green, checkpoint/sidecar 7/7 output head 준비.
- delta_force 라벨은 GPU worker return receipt(operator-transfer) 기반으로 충족 처리됨.

**갭**
- `production_gpu_execution_environment_ready` 의 실제 ROCm/HIP GPU 노드 또는 영속 worker 부재 시,
  full regeneration은 operator-transfer 의존.
- residual이 **물리 코어 위 bounded corrector** 라는 경계는 유지되어야 함(정밀도 갭을 AI로 덮지 않기).

**구현 방향**
1. ROCm/HIP GPU 노드 상시화 또는 GPU worker 영속 큐(이미 SQLite lease/heartbeat primitive 존재) 운영화.
2. residual 학습 데이터의 **물리 라벨 출처 명확화**(force/energy 라벨이 자체 정밀 tier에서 나오도록 — A와 연동).
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
- `runs/api_customer_flow_release_evidence_current.json`과
  `runs/product_launch_r4_preflight_current.json`은 restricted customer-flow evidence와
  R4 직전 preflight를 local artifact 기준 green으로 묶는다.

**갭**
- 실제 docking/MD 실행과 rollout smoke는 여전히 explicit operator approval token과
  R4 확인에 묶여 있어, 배포/remote mutation이 자동으로 열리지는 않는다.

**구현 방향**
1. R4 preflight 산출물을 기반으로 Target/Action/Impact/Risk/Rollback/Verification을
   제시하고 explicit operator approval을 받은 뒤 실행 smoke를 분리 수행.
2. fail-closed 정책은 유지하되, **restricted scope 안에서는** profile 기반 무인 실행 경로를 SLA로 보장.
3. dispatch worker(`api/docking_dispatch.py`, `run_api_docking_dispatch_worker.py`) 상시 운영화 + 모니터링.

**완료 정의**: restricted scope 타깃에 대해 인증된 클라이언트가 API로 도킹 작업 제출 →
durable queue → worker 실행 → signed 결과 번들 회수까지 무인 동작.

---

### F. Hosted / 배포 / 운영 인프라 (P1/P3)

**현황**
- `deploy/`: docker-compose, systemd, k8s manifest, model registry, rollout/rollback runbook 1차 존재.
- monitoring/`: `/metrics`, alert rules, closed-loop alert smoke 1차 통합.
- R4 launch preflight는 `7/7 pass`, `authorized_for_external_mutation=false`,
  `launch_executed=false`로 실제 실행 전 상태를 명시한다.

**갭**
- 실제 pager provider delivery, ingress certificate(TLS) smoke, operator-approved rollout **실행** smoke 미완.
- 멀티테넌시 격리·쿼터, 작업 영속성/재시도의 운영 검증, 백업/DR.

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
2. CAMEO 공식 결과 intake(외부 schedule 의존, operator approval 토큰).
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
2. **가장 빠른 상용 스위치는 R4/operator-approved rollout smoke.** restricted scope의
   local evidence와 preflight는 green이므로, 명시 승인 후 실행 검증이 self-hosted 파일럿 전환점이다.
3. **가장 큰 실제 갭은 A(과학 엔진 정밀도).** internal typed all-atom/GB-SA/explicit-shell/FEP scaffold,
   common ligand halogen/charged-residue local-chemistry/metal-coordination coverage surface, proxy benchmark metric surface는 green이지만,
   metal/cofactor parameterization·formal protonation·charge/torsion/improper calibration·curated 공개 pose/free-energy benchmark intake를 통과해야
   "외부 엔진 무의존 완전 상용 제품"이라는 claim이 성립한다.
4. **AI는 정밀도 갭을 덮는 용도가 아니라** 물리 코어 위 bounded residual로 유지해야 하며(C),
   학습 라벨이 자체 정밀 tier(A)에서 나와야 일관성이 생긴다.
5. **scope 확장(G)·외부 벤치마크(H)** 는 정밀도(A) 위에서만 방어 가능하므로, A를 선행 투자로 본다.

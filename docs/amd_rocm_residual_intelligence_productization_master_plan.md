# AMD ROCm/HIP 독립 상용제품화 + Residual Intelligence Layer 마스터 플랜

## 문서 목적

이 문서는 Betelgeuze를 완전한 독립기능 상용제품 수준으로 올리기 위한 제품화 작업을 결정 완료 형태로 정리한다. 목표 제품은 외부 SaaS runtime dependency 없이 로컬/자체 서버에서 구조해석, 리간드 도킹, 점수화, 랭킹, 결과 bundle, benchmark evidence를 생성하는 AMD ROCm/HIP 중심 제품이다.

이 문서는 실행 명령이나 외부 제출을 승인하지 않는다. 모델 학습, 벤치마크 실행, 다운로드, 삭제, 업로드, CAMEO 등록, 이메일 발송은 별도 approval token 없이는 수행하지 않는다.

## Source Documents

이 마스터 문서는 기존 문서를 폐기하지 않고 상위 통합한다.

- `docs/global_residual_correction_target_list.md`
- `docs/cross_family_residual_shadow_layer_plan.md`
- `docs/topk_cascade_architecture_plan.md`
- `docs/gpcr_residual_prototype_plan.md`
- `docs/commercialization_productization_gap_audit_2026-05-06.md`

## 1. 제품 비전

제품명/포지션은 다음으로 고정한다.

`Betelgeuze AMD-native private molecular docking and validation appliance`

상용 제품 목표는 다음이다.

- 로컬/자체 서버에서 protein structure analysis, ligand docking, scoring, ranking, report bundle 생성
- AMD ROCm/HIP 환경에서 계산 PC와 서버 PC를 표준화
- 외부 SaaS runtime dependency 0 유지
- 공개 benchmark 기반으로 성능과 정확도를 지속 증명
- raw baseline output과 corrected output을 모두 보존하는 auditable product
- CAMEO는 optional/live validation channel로 유지하되 제품 릴리스 차단 조건으로 사용하지 않음

제품 차별점은 단일 docking score가 아니라 다음 조합이다.

- AMD ROCm/HIP native compute profile
- benchmark-driven residual correction
- raw/corrected/provenance/report가 한 bundle로 묶이는 evidence-first workflow
- public benchmark regression gate로 성능 하락을 조기에 차단
- approval token 기반 외부 상태 변경 통제

## 2. 현재 상태 요약

현재 제품 아키텍처와 릴리스 증거는 다음 상태를 기준으로 한다.

- `product_architecture_contract_ready`
- `product_goal_completion_audit_pass`
- `goal_release_ready`
- public benchmark 5 suite ready
- commercial independence gate ready
- local/self-hosted operation ready
- external SaaS runtime dependency count 0
- CAMEO optional/live validation 유지

현재 상태는 연구 코드 수준을 넘어 제품 아키텍처 릴리스 게이트를 통과한 상태다. 다음 단계는 실제 AMD hardware profile, residual shadow A/B, throughput/accuracy regression evidence를 쌓아 상용 alpha package로 고정하는 것이다.

## 3. Target Product Architecture

### AMD Runtime Layer

역할:

- AMD GPU/ROCm/HIP/PyTorch ROCm 상태를 제품 실행 전에 검증
- CPU fallback은 유지하되 상용 주력 경로는 ROCm/HIP로 명시
- 계산 PC와 서버 PC를 AMD Workstation Profile / AMD Server Profile로 표준화

필수 산출물:

- `runs/rocm_environment_manifest_current.json`
- `runs/rocm_environment_manifest_current.md`
- `runs/amd_hardware_throughput_scorecard_current.json`
- `runs/amd_hardware_throughput_scorecard_current.md`

### Input Preparation Layer

역할:

- protein PDB/mmCIF ingest
- ligand SDF/SMILES ingest
- chain/pocket/ligand validation
- salt/tautomer/protonation/conformer policy 기록
- failed input을 조용히 넘기지 않고 report에 기록

필수 출력:

- normalized protein artifact
- normalized ligand artifact
- pocket definition
- input hash
- preparation warning/error list

### Docking Execution Layer

역할:

- smoke docking
- production docking
- ensemble docking
- optional pose refinement
- ROCm/HIP batch execution

필수 출력:

- pose set
- raw docking score
- runtime profile
- seed/version/environment hash
- execution provenance

### Scoring / Ranking Layer

역할:

- physics score
- geometric/contact score
- ML/residual score
- consensus rank
- confidence/uncertainty

필수 출력:

- `raw_score`
- `corrected_score`
- `rank`
- `confidence`
- `score_components`
- `abstention_reason`

### Residual Intelligence Layer

역할:

- raw docking / MD / scoring output의 오차만 제한적으로 보정
- hard-decoy false positive를 줄임
- expensive stage2 사용량을 줄이는 routing signal 제공
- uncertainty high/OOD에서는 abstain

기본 정책:

- 기본값은 `residual_mode=shadow`
- `assist`/`production` 승격은 benchmark evidence 없이는 금지

### Benchmark Engine

역할:

- public benchmark와 hardware benchmark를 모두 수행
- 성능 개선과 성능 하락을 같은 기준에서 기록

필수 public benchmark suite:

- LIT-PCBA
- DUDE-Z
- PDBbind/CASF
- protein-protein docking benchmark v5 / BM5
- CASP archive

필수 hardware benchmark:

- ligands/hour
- poses/sec
- score evaluations/sec
- VRAM per 1k ligands
- CPU vs ROCm speedup
- failure rate
- reproducibility under fixed seed

### Evidence / Report Layer

역할:

- 모든 결과를 customer-facing bundle로 정리
- raw baseline output과 corrected output을 함께 보존
- provenance 없는 결과는 commercial output으로 승격하지 않음

필수 bundle:

- HTML report
- CSV score/rank table
- JSON provenance
- environment manifest
- benchmark scorecard

### Commercial API/CLI Surface

예정 CLI 표면:

- `betelgeuze-product benchmark rocm`
- `betelgeuze-product residual shadow`
- `betelgeuze-product residual compare`
- `betelgeuze-product report bundle`

예정 API 표면:

- ROCm environment status
- residual mode status
- benchmark regression status
- docking job submit/status/result/download
- report bundle download

## 4. ROCm/HIP 제품화 작업

### ROCm Environment Manifest

`rocm_environment_manifest_current.json`은 다음 필드를 기록해야 한다.

- OS name/version
- kernel version
- AMD GPU model
- GPU architecture / gfx target
- VRAM total/free
- ROCm version
- HIP version
- `hipcc --version`
- `rocminfo` availability
- `rocm-smi` availability
- PyTorch version
- PyTorch HIP version
- `torch.cuda.is_available()` result for ROCm build
- visible device count
- runtime env vars relevant to ROCm/HIP
- manifest generation command

### Requirements Profiles

제품 의존성 profile은 다음으로 분리한다.

- `requirements-rocm.txt`: AMD ROCm/HIP production runtime
- `requirements-cpu.txt`: CPU fallback runtime
- `requirements-dev.txt`: tests, docs, developer tooling

CUDA/NVIDIA 관련 의존성은 기본 제품 runtime에 포함하지 않는다. 필요한 경우 optional profile로만 둔다.

### AMD Workstation Profile

목표:

- 단일 사용자 또는 소규모 연구팀이 로컬로 실행
- smoke benchmark와 small/medium docking workload를 안정적으로 수행

문서화 항목:

- supported AMD GPU family
- recommended VRAM
- recommended RAM
- storage requirement
- ROCm version
- OS/kernel profile
- expected smoke benchmark runtime

### AMD Server Profile

목표:

- 내부 서버 또는 납품형 계산 서버로 batch docking 수행
- 장시간 benchmark/regression loop 가능

문서화 항목:

- supported multi-GPU topology
- queue/job persistence requirement
- thermal/power monitoring
- storage layout
- result bundle retention policy
- customer handoff policy

## 5. Residual Intelligence Layer

내부 기능명은 다음으로 고정한다.

`Betelgeuze Residual Intelligence Layer`

### 구성 요소

`TopoGraph Corrector`

- covalent bond graph
- protein-ligand contact graph
- residue-ligand interaction graph
- pocket spatial graph
- trajectory temporal graph

`Equivariant Residual Energy/Force Model`

- T-GNN을 E(3)/SE(3)-equivariant graph model로 확장
- 회전/병진 대칭을 보존
- 가능하면 `ΔE`를 예측하고 `ΔF = -∇ΔE`로 force correction 생성
- 직접 `delta_force` 예측은 fallback 또는 auxiliary head로 제한

`Physics Guard`

- PINN을 메인 모델이 아니라 physics constraint/loss/gate로 사용
- bond/angle/clash/energy drift violation을 보정 적용 전에 검사
- correction이 물리 제약을 깨면 shrink 또는 abstain

`Hard-Decoy Rank Corrector`

- GPCR hard-decoy intrusion 감소가 첫 증명 대상
- prior-favorable but weak-contact decoy를 penalty
- active binder top-k retention을 보존

`Stage Router`

- expensive stage2 사용 여부를 결정
- throughput 개선의 핵심 레이어
- uncertain/high-value candidate는 frozen expensive path로 보냄

`Uncertainty Abstainer`

- router uncertainty
- residual head uncertainty
- OOD score
- correction magnitude
- baseline/corrected disagreement

위 신호가 위험하면 corrected output을 적용하지 않고 raw baseline output을 유지한다.

### Residual Outputs

필수 출력 필드는 다음이다.

- `delta_score`
- `corrected_score`
- `delta_energy`
- `delta_force`
- `uncertainty`
- `abstention_reason`
- `stage2_route_decision`

### Training / Loss Direction

학습 방향은 다음과 같이 고정한다.

- primary: residual score/rank correction
- secondary: residual potential energy / force correction
- tertiary: stage2 routing/cost reduction

권장 loss 구성:

- `L_score`
- `L_rank`
- `L_force_residual`
- `L_energy_drift`
- `L_pose_rmsd`
- `L_bond_angle_violation`
- `L_clash_penalty`
- `L_uncertainty_abstention`
- `L_stage2_budget`

## 6. Residual Mode 정책

`off`

- 잔차보정 비활성
- raw baseline output만 사용

`shadow`

- 예측과 report만 기록
- ranking/score에는 반영하지 않음
- 기본값: `residual_mode=shadow`

`assist`

- low-risk 후보에만 제한적으로 corrected score 반영
- uncertainty high/OOD에서는 raw baseline으로 fallback
- benchmark gate 통과 전에는 customer-facing default로 사용 금지

`production`

- benchmark gate 통과 후 기본 ranking에 반영
- rollback 가능한 config로만 배포
- raw baseline output은 항상 보존

승격 규칙:

- `shadow -> assist`: GPCR hard-decoy A/B에서 pass->fail regression 0, correction magnitude cap 준수
- `assist -> production`: public benchmark suite 전체에서 정확도 악화 없음, ROCm throughput 손실 허용범위 내
- 어떤 승격도 수동 선언만으로 허용하지 않고 JSON/CSV/MD evidence와 tests로 증명

## 7. Benchmark/Productization Roadmap

### Phase 0: 문서/계약 정리

목표:

- 제품화 master plan 저장
- residual mode policy 확정
- ROCm/HIP profile 요구사항 확정

산출물:

- `docs/amd_rocm_residual_intelligence_productization_master_plan.md`

### Phase 1: ROCm Manifest + Hardware Smoke Benchmark

목표:

- AMD hardware environment를 재현 가능하게 기록
- CPU fallback과 ROCm path를 비교

산출물:

- `runs/rocm_environment_manifest_current.json`
- `runs/amd_hardware_smoke_benchmark_current.json`
- `runs/amd_hardware_throughput_scorecard_current.json`

Acceptance:

- supported AMD GPU detected
- PyTorch ROCm usable
- fixed seed smoke run success
- hardware scorecard contains CPU vs ROCm speedup

### Phase 2: Residual Shadow A/B Scaffold

목표:

- residual prediction을 ranking 미반영 상태로 기록
- raw vs shadow comparison artifact 생성

산출물:

- `runs/residual_shadow_ab_current.json`
- `runs/residual_shadow_ab_current.csv`
- `runs/residual_shadow_ab_current.md`

Acceptance:

- raw baseline preserved
- corrected prediction recorded
- no customer-facing ranking change
- abstention fields present

### Phase 3: GPCR Hard-Decoy Slice Residual Proof

목표:

- 첫 증명 대상을 measured GPCR hard-decoy failure slice로 제한
- decoy intrusion 감소와 binder retention을 동시에 확인

Acceptance:

- GPCR top-k hard-decoy intrusion 감소
- first binder retention 유지
- pass->fail regression 0
- correction norm cap 준수

### Phase 4: Public Benchmark Regression Gate

목표:

- public benchmark 5 suite 전체에 residual shadow/assist 영향을 검증

필수 suite:

- LIT-PCBA
- DUDE-Z
- PDBbind/CASF
- BM5
- CASP archive

Acceptance:

- LIT-PCBA/DUDE-Z AUROC 개선 또는 유지
- EF1%, EF5%, BEDROC 개선 또는 유지
- PDBbind/CASF pose success 악화 없음
- BM5/CASP archive regression 없음

### Phase 5: AMD Workstation/Server Packaging

목표:

- 검증된 AMD profile을 고객 납품 가능한 package로 고정

산출물:

- AMD Workstation Profile
- AMD Server Profile
- install guide
- smoke benchmark guide
- report bundle guide

### Phase 6: Customer-Facing Alpha Bundle

목표:

- customer-facing alpha package 생성
- report bundle과 benchmark evidence를 함께 납품

Acceptance:

- local install succeeds
- ROCm smoke benchmark succeeds
- docking job succeeds
- report bundle generated
- no external state mutation without approval token

## 8. 승격 기준

Residual Intelligence Layer가 `assist` 또는 `production`으로 승격되려면 다음을 만족해야 한다.

- GPCR hard-decoy intrusion 감소
- active binder top-k retention 유지
- LIT-PCBA AUROC/EF1%/EF5%/BEDROC 개선 또는 유지
- DUDE-Z AUROC/EF1%/EF5%/BEDROC 개선 또는 유지
- PDBbind/CASF pose success 악화 없음
- BM5 regression 없음
- CASP archive regression 없음
- ROCm throughput 손실 허용범위 내
- uncertainty high/OOD는 abstain
- pass->fail regression 0
- raw baseline output과 corrected output provenance 모두 존재

하나라도 실패하면 승격하지 않고 `shadow` 또는 `off`로 유지한다.

## 9. 상용 안전 정책

다음 작업은 approval token 없이는 수행하지 않는다.

- 외부 제출
- CAMEO 등록
- 이메일 발송
- 파일 삭제
- 파일 archive/externalize/upload
- 공개 서버 등록
- customer-facing delivery claim 변경

필수 보존 정책:

- raw baseline output은 항상 보존
- corrected output은 provenance와 함께 저장
- residual correction은 hidden heuristic이 아니라 auditable layer로 유지
- benchmark gate 없는 corrected ranking은 customer-facing claim에 사용 금지

상용 문구는 다음 조건에서만 허용한다.

- product release evidence ready
- commercial independence gate ready
- ROCm/HIP environment manifest present
- public benchmark evidence present
- residual mode와 correction status가 명시됨

## 10. 향후 인터페이스 계약

### CLI 예정 명령

- `betelgeuze-product benchmark rocm`
- `betelgeuze-product residual shadow`
- `betelgeuze-product residual compare`
- `betelgeuze-product report bundle`

### API 예정 표면

- ROCm environment status
- residual mode status
- benchmark regression status
- residual A/B comparison status
- hardware throughput scorecard status

### Artifact 예정 표면

- `runs/rocm_environment_manifest_current.json`
- `runs/amd_hardware_throughput_scorecard_current.json`
- `runs/residual_shadow_ab_current.json`
- `runs/residual_shadow_ab_current.csv`
- `runs/residual_shadow_ab_current.md`
- `runs/public_benchmark_regression_gate_current.json`
- `runs/customer_alpha_bundle_manifest_current.json`

## 11. 구현 기본값

- 문서 본문 언어: Korean
- technical identifier: English
- residual default: `residual_mode=shadow`
- first implementation priority: `ROCm/HIP platform proof + residual shadow A/B`
- CAMEO: optional/live validation
- CPU fallback: enabled
- commercial compute default: ROCm/HIP
- raw baseline preservation: required
- corrected output provenance: required
- no approval token, no external mutation

## 12. 다음 작업 큐

1. `rocm_environment_manifest_current.json` builder 설계
2. `amd_hardware_throughput_scorecard_current.json` builder 설계
3. `residual_shadow_ab_current.*` artifact 설계
4. GPCR hard-decoy slice residual proof gate 설계
5. public benchmark regression gate에 residual raw/shadow/assist comparison 추가
6. product API/CLI에 ROCm/residual status surface 추가
7. AMD Workstation Profile / AMD Server Profile 문서화
8. customer alpha bundle manifest 설계

## 13. 완료 기준

이 마스터 문서 자체의 완료 기준은 다음이다.

- 파일 경로: `docs/amd_rocm_residual_intelligence_productization_master_plan.md`
- `residual_mode=shadow` 포함
- `ROCm/HIP` 포함
- `E(3)/SE(3)` 포함
- `PINN` 포함
- `AMD Workstation Profile` 포함
- `public benchmark` 포함

이후 구현 완료 기준은 별도 phase별 artifact와 tests에서 판단한다.

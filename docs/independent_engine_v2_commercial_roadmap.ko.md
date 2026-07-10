# Independent Engine v2 독립 상용화 장기 로드맵

기준일: 2026-07-10

문서 상태: 장기 개발 참고 기준선·비실행 문서·비주장 문서

현재 구현 단계: V2-0 독립 CPU 스캐폴드

적용 범위: 단백질·리간드 구조분석, 도킹, 분자동역학, AI 보정, ROCm/HIP, 로컬 제품화

이 문서는 현재 구현을 상용 제품으로 선언하는 자료가 아니다. 앞으로 무엇을
어떤 순서로 구현하고, 어떤 증거를 확보해야 독립 기능을 하나씩 출시할 수
있는지를 정하는 참고 로드맵이다. 실제 capability 상태와 출시 가능 여부는
[`../config/independent_engine_v2_capabilities.yaml`](../config/independent_engine_v2_capabilities.yaml)의
fail-closed 정책을 따른다.

이번 문서 변경은 개발 지시 실행이나 capability 승격을 의미하지 않는다.
소스코드, 외부 실행 상태와 과학·제품 claim은 변경하지 않는다. 문서와 실제
상태가 충돌하면 다음 우선순위를 적용한다.

1. 실행 코드와 검증 테스트
2. machine-readable capability blocker
3. non-empty row-level benchmark·release evidence
4. 이 로드맵과 기타 narrative 문서

기존 `product_full_implementation_plan.md`와 `PRODUCT_VISION_CURRENT.md`는
legacy/restricted 제품 운영 lane을 설명한다. 해당 lane의 green 상태를 독립
V2 과학 엔진의 완료로 합산하지 않는다. 이 문서는 V2 장기 전략, 단계 의존성과
capability 승격 기준을 정리하는 canonical reference다.

## 1. 최종 목표

최종 목표는 고객 실행 경로에서 외부 분자 솔버를 호출하지 않는 완전한 로컬·
오프라인 단백질·분자구조 분석 프로그램을 구축하는 것이다.

완성 제품이 독립적으로 제공해야 할 기능은 다음과 같다.

- 단백질·리간드 all-atom 입력, 정규화, 전처리 및 화학 적용범위 판정
- 구조 품질, 결합 포켓, 인터페이스, 상호작용, 변이 영향 분석
- 독립 힘장, 에너지·힘 계산, 구조 최소화 및 국소 refinement
- torsion-aware ligand docking, 다양한 top-k pose와 재점수화
- PBC, 명시적 용매·이온, 장거리 정전기와 NVE/NVT/NPT 분자동역학
- 물리 기반 에너지에 결합되는 독자 residual-energy AI
- 불확실성 보정, 적용범위 판정과 OOD 입력 거부
- capability별 재현 가능한 benchmark와 signed evidence
- AMD ROCm/HIP 가속과 CPU 기준 구현의 수치적 동등성
- 설치, 업데이트, 작업 재개, 3D 시각화, 보고서와 데이터 격리를 포함한 제품 기능

Vina, GNINA, Smina, OpenMM, AMBER, GROMACS 또는 다른 분자 솔버는 개발 중
offline reference oracle과 비교 실험에만 사용할 수 있다. 이 도구의 계산을
v2 결과로 표시하거나 고객 실행의 숨은 의존성으로 사용할 수 없다. PyTorch,
Rust, ROCm과 일반 파일·UI·보안 라이브러리는 구현 인프라로 사용할 수 있지만,
과학적 에너지·힘·도킹·MD 판단은 v2가 소유하고 검증해야 한다.

RDKit과 같은 cheminformatics 라이브러리는 파일 ingest·개발 비교용 adapter로
사용할 수 있지만, canonical molecular state와 지원 chemistry 판정은 v2
contract가 다시 검증해야 한다. 독립 엔진 코드, 독립 parameter, 학습 dataset,
model IP와 각 artifact의 license는 서로 별개의 증거 트랙으로 관리한다.

## 2. 현재 기준점과 완료되지 않은 영역

V2-0은 완성된 분자구조 해석 제품이 아니라 독립 엔진을 만들기 위한 실행
가능한 CPU 기준선이다.

| 구분 | 현재 확보한 기반 | 현재 차단된 주장 또는 기능 |
| --- | --- | --- |
| 계약 | 버전형 all-atom 상태, 결합, isotope, R/S·E/Z, provenance, legacy adapter | 완전한 PDB/mmCIF/SDF/SMILES parser coverage와 canonical round-trip |
| 기하 | bounded cell-list, sparse radius graph, 고정 capacity와 overflow 차단 | release-scale occupancy·memory evidence와 periodic AI gradient |
| AI | non-attention parity-aware local energy, exact force VJP, torsion·temporal GNN, PINN gate | 학습된 production checkpoint, calibration, OOD 및 공개 holdout evidence |
| 수학 | matrix-free 고정 rank 직교사영과 adjoint | 광범위한 constraint·coordinate-dependent basis 검증 |
| 실행 | fail-closed 내부 CPU orchestrator와 버전형 checkpoint 의미론 | 독립 힘장, docking, 장거리 물리, MD와 고객 실행 route |
| 검증 | focused CPU tests, wheel, Python 3.10/3.11 CI | 과학 benchmark, 실제 ROCm parity, 고객 shadow evidence |

따라서 현재 상태에서 허용되는 표현은 “V2-0 독립 엔진 스캐폴드”까지다.
독립 상용 솔버, 검증된 도킹 정확도, all-atom MD, GPU 가속, 단백질 구조 예측,
결합 자유에너지 또는 고객 사용 가능 상태라고 표현해서는 안 된다.

여기서 “구조분석”은 제공된 실험·예측 구조를 입력으로 quality, pocket,
interface, interaction과 mutation 영향을 분석하는 기능이다. sequence에서 3D
구조를 생성하는 de novo structure prediction은 별도의 대형 연구 lane이며
구조분석·도킹·MD 상용화의 필수 선행조건으로 두지 않는다.

## 3. 고정 설계 원칙

### 3.1 물리 엔진과 AI의 역할

독립 물리 엔진이 기준 에너지를 계산하고 AI는 제한된 residual energy를
보정한다.

`E_total = E_independent_physics + sum_i delta_e_i`

AI가 보존력을 직접 주장하는 force vector를 출력하지 않는다. 힘은 전체 scalar
energy의 정확한 역방향 미분으로 정의한다.

`F_i = -dE_total / dr_i`

AI 성능이 부족하거나 OOD가 감지되면 residual을 비활성화하거나 결과를
abstain한다. 독립 물리 기반이 없는 상태에서 AI만으로 상용 분자해석 엔진을
주장하지 않는다.

### 3.2 비어텐션·비트랜스포머 경계

v2 실행 경로에는 full attention, Transformer, dense `[N,N]` learned weight,
global pair tensor를 두지 않는다. 모든 메시지는 bounded sparse graph를 통해
전달한다. 이 선택은 속도만을 위한 것이 아니라 메모리 상한과 실패 동작을
명시하기 위한 제품 계약이다.

### 3.3 E(3), SE(3), parity와 chirality

계획 단계의 “E(3) GNN”은 Euclidean geometric message passing이라는 넓은
방향을 뜻한다. 실제 구현 계약은 다음과 같이 더 엄밀하게 표현한다.

- translation과 proper rotation에 대한 scalar energy invariance
- proper rotation에 대한 force equivariance
- 허용된 atom permutation에 대한 일관성
- R/S, E/Z와 pseudoscalar channel을 통한 명시적 parity·chirality 처리
- 거울상 분자를 동일하게 만드는 distance-only 표현의 금지

현재 parity-aware local-vector·signed-triple-product 구현을 완전한 모든 차수의
E(3) irreducible-representation stack이라고 과장하지 않는다.

### 3.4 T-GNN 명칭 분리

두 종류의 GNN은 목적과 복잡도 증거를 분리한다.

- `TorsionTopologyGNN`: 정적 bond/torsion tree에서 한 번의 topology 전파와
  forward kinematics·reverse adjoint를 수행한다.
- `TemporalStateGNN`: MD 또는 refinement step 사이에서 bounded recurrent
  state를 전달한다.

torsion마다 모든 자손 원자를 재탐색하는 구현은 최악의 경우 `O(N^2)`이므로
금지한다. Temporal full-history 학습은 `O(TN)`이며 고정 메모리 주장에 포함하지
않는다.

### 3.5 PINN의 위치

PINN은 수치 솔버가 아니라 학습 objective와 release gate다. 다음 항목을
검사할 수 있다.

- energy·force supervision과 finite-difference 일치
- 이동·회전·순열·parity 일관성
- net force·net torque residual
- bond·angle·virial·pressure residual
- short-rollout stability
- uncertainty calibration과 OOD abstention

PINN loss가 낮다는 사실만으로 force field, integrator, ensemble 또는 MD가
과학적으로 검증됐다고 판단하지 않는다.

### 3.6 직교사영 순전파·역전파

고정 rank basis `B`에 대해 다음 연산을 직접 적용한다.

`P(v) = B solve(B^T B, B^T v)`

`Q(v) = v - P(v)`

`D x D` projector를 만들지 않는다. rank는 현재 최대 16으로 고정하며 rank
부족과 ill-conditioning은 fail-closed 처리한다. 좌표 의존 basis의 정확한
gradient가 필요할 때 `B`를 detach하지 않으며 finite difference로 basis
gradient를 검증한다.

## 4. 조건부 O(N) 계약

단거리 forward와 reverse가 atom count `N`에 대해 `O(N)`이 되려면 다음
조건을 모두 만족해야 한다.

1. 물리 밀도와 cutoff가 고정돼 directed edge 수 `E <= K*N`을 유지한다.
2. `K`는 `N`과 독립이고 hard cap 256 이하이다.
3. cell occupancy는 hard cap 256 이하이며 overflow는 all-pairs fallback 대신
   실행 차단으로 처리한다.
4. layer 수는 최대 16, local hidden width는 최대 512이며 radial basis,
   channel, irrep order가 `N`과 함께 증가하지 않는다.
5. projection rank는 최대 16이고 dense projector를 만들지 않는다.
6. temporal window, docking candidate budget과 refinement step이 고정된다.
7. `torch.cdist`, dense adjacency, full attention, full Hessian·Jacobian,
   global QR/SVD를 제품 경로에서 사용하지 않는다.

이 조건에서는 sparse forward와 동일한 계산 graph를 역으로 순회하는 force
VJP가 모두 `O(N)`이다. 이는 알고리즘 계약이며 아직 실제 하드웨어 성능
주장이 아니다. 다음 작업은 별도로 정직하게 표기한다.

| 범위 | 복잡도 표기 원칙 |
| --- | --- |
| 고정-window temporal training | `O(WN)` |
| 전체 temporal history | `O(TN)` |
| PME long-range electrostatics | `O(N log N)` |
| FMM | 고정 error tolerance·order·bounded tree에서만 expected `O(N)` |
| docking 전체 | 후보 수와 반복 수를 포함해 보고하며 자동으로 `O(N)`이라 하지 않음 |
| free-energy ensemble | atom 수 외에 lambda·replica·sampling budget을 함께 보고 |

## 5. 기존 구조의 재사용·교체 정책

| 처리 | 재사용 가능한 영역 | 필수 조건 |
| --- | --- | --- |
| 재사용 | claim·provenance·abstention 계약, SoA·zero-copy 개념, compact buffer, Rust/HIP build·FFI, job 상태·경로 격리·복구, evidence·signed report 형식 | v2 소유 interface 뒤에서 dtype·device·lifetime·보안·schema 재검증 |
| 임시 adapter | compact-neighbor 값, legacy `[B,N,K]` training/evaluator 형태, schema 2.1 checkpoint consumer, 구버전 결과 reader | adapted provenance를 기록하고 native v2 과학 결과로 승격하지 않음 |
| 독자 구현으로 교체 | all-atom parser·preparation, heuristic force field, solvent, integrator, pose search, scoring, structure metric, MM/GBSA·FEP, frame-dependent AI correction | 독립 parameter·algorithm·validation·applicability 계약 필요 |
| 보관 | dense attention, proxy score와 공식 metric 명칭을 공유하는 코드, zero-output specialist, 정적 endpoint FEP, 근거 없는 MM/GBSA proxy | v2 runtime에서 접근 불가; 역사적 재현 용도로만 유지 |

자세한 파일별 처리는
[`independent_engine_v2_migration_matrix.md`](independent_engine_v2_migration_matrix.md)를
따른다.

## 6. 목표 제품 아키텍처

```text
입력·전처리 계층
  PDB/mmCIF/SDF/SMILES → canonical all-atom state → chemistry coverage gate
                              │
희소 기하·런타임 계층         ▼
  cell list / Verlet / PBC image shifts / compact buffers / CPU-HIP backend
                              │
독립 물리 계층                ▼
  bonded + nonbonded + long-range + solvent + constraints + integrators
                              │
AI 보정 계층                  ▼
  sparse parity-aware energy + torsion GNN + temporal GNN + PINN + uncertainty
                              │
분석·탐색 계층                ▼
  structure quality / pocket / interface / mutation / docking / MD / free energy
                              │
검증·제품 계층                ▼
  public holdout / evidence / capability gate / local UI·API / report / recovery
```

과학 core와 제품 layer를 분리한다. 제품 UI/API가 존재한다는 이유로 과학
capability가 활성화되지 않으며, 과학 gate를 통과한 capability만 product
dispatch allowlist에 들어갈 수 있다.

## 7. 단계별 개발 로드맵

| 단계 | 핵심 목표 | 선행 의존성 | 종료 시 허용되는 범위 |
| --- | --- | --- | --- |
| V2-0 | 독립 계약·희소 기하·AI 수학 primitive·CPU reference | 없음 | 내부 스캐폴드 실행만 허용 |
| V2-1 | 완전한 all-atom I/O·preparation | V2-0 contracts | 지원 chemistry의 canonical ingest |
| V2-2 | 독립 CPU 단거리 힘장·최소화 | V2-1 identity·coverage | 검증된 chemistry 범위 내 energy·force·minimization |
| V2-3 | 구조분석·torsion-aware docking·scoring | V2-1, V2-2 | 통과한 분석·pose capability의 내부 beta |
| V2-4 | PBC·장거리 물리·용매·constraints·MD | V2-2 | 검증된 ensemble별 내부 MD beta |
| V2-5 | production residual AI와 물리 결합 | V2-2~V2-4 evidence | calibration·OOD gate가 있는 AI 보정 |
| V2-6 | ROCm/HIP 가속 | CPU reference freeze | CPU와 parity가 증명된 AMD 실행 |
| V2-7 | 독립 상용 로컬 제품 | capability별 과학·benchmark·GPU gate | 승인된 capability만 고객 활성화 |

### V2-0 — 독립 엔진 기반

현재 확보한 산출물:

- `betelgeuze_engine_v2/` package와 versioned contracts
- all-atom identity·stereo shell과 explicit legacy adapter
- bounded sparse geometry와 hard capacity
- parity-aware energy, torsion·temporal GNN, PINN, projection primitive
- fail-closed CPU orchestrator
- runtime-input·checkpoint 의미론과 CPU CI

종료 기준:

- CPU compile, focused unit tests와 wheel import가 통과한다.
- covered primitive가 dense all-pairs·dense projector에 의존하지 않는다.
- periodic, scientific, benchmark, GPU, product claim blocker를 유지한다.
- 기존 고객 route를 v2로 자동 전환하지 않는다.

현재 판단: 스캐폴드 기준 완료. 이후 단계의 과학 기능을 대신하지 않는다.

### V2-1 — All-atom I/O와 preparation

주요 산출물:

- PDB·mmCIF·SDF·SMILES 입력과 canonical serialization
- biological assembly, altloc, insertion code, missing atom·residue 정책
- hydrogen, protonation, tautomer, aromaticity와 formal charge
- R/S·E/Z, isotope, water, ion, metal, cofactor와 modified residue
- ligand atom mapping, topology hash, source·변환 provenance
- 지원·미지원 chemistry와 parameterability report

종료 기준:

- round-trip에서 원자·결합·전하·stereo·residue·chain이 조용히 손실되지 않는다.
- supported corpus와 의도적으로 실패하는 failure corpus를 함께 유지한다.
- 미지원 화학을 carbon·alanine·generic bead로 바꾸지 않고 blocker로 반환한다.
- 동일 입력의 canonical hash와 atom order가 재현된다.

### V2-2 — 독립 CPU 힘장과 최소화

주요 산출물:

- bond, angle, proper torsion, improper와 constraint schema
- vdW, short-range electrostatics와 초기 implicit-solvation 범위
- atom typing, charge·parameter provenance와 applicability domain
- 독립 parameter fitting·versioning pipeline
- deterministic steepest-descent/L-BFGS 계열 최소화와 checkpoint/restart
- 항별 energy·force·virial diagnostics

종료 기준:

- 단위와 translation·rotation·permutation invariance가 검증된다.
- analytic/autograd force가 finite difference와 사전 선언 tolerance에서 일치한다.
- supported chemistry의 parameter coverage가 사전 선언 기준을 충족한다.
- minimization이 정의된 조건에서 energy를 감소시키고 실패 원인을 기록한다.
- 외부 솔버 비교는 oracle-labelled evidence로만 저장한다.

### V2-3 — 독립 구조분석·도킹·scoring

구조분석 산출물:

- 원자 충돌, 결합 geometry, Ramachandran·rotamer 등 정확한 정의의 quality metric
- pocket geometry·physicochemical profile과 ligandability evidence
- protein–protein·protein–ligand interface와 interaction network
- mutation 전후 local environment·stability·interaction 변화와 uncertainty
- 구조 정렬, RMSD 계열, contact·secondary-structure metric의 검증된 구현

도킹 산출물:

- ligand conformer와 rotatable-bond tree
- torsion-aware global search와 gradient local refinement
- diverse top-k, symmetry-aware clustering과 pose validity
- constraints, flexible side chain, ensemble receptor 정책
- water·metal·cofactor interaction policy
- 독립 physics score와 제한된 AI residual score

종료 기준:

- pose validity, recovery, ranking을 사전 고정한 public holdout protocol로 실행한다.
- aggregate 점수뿐 아니라 모든 row와 실패 row를 보존한다.
- 구조분석 metric을 공식 정의 또는 독립 reference implementation과 교차 검증한다.
- uncertainty와 failure domain을 결과에 포함한다.
- 임계치를 정한 후 benchmark를 실행하고 결과를 본 뒤 기준을 바꾸지 않는다.

### V2-4 — PBC·장거리 물리·용매·MD

주요 산출물:

- differentiable periodic image-shift를 energy·force 경로 끝까지 전달
- topology-aware explicit water·ion과 box preparation
- validated PME `O(N log N)` 또는 조건이 명시된 FMM
- SHAKE/RATTLE 계열 bounded constraint solver 또는 독립 대안
- NVE, NVT, NPT integrator와 thermostat·barostat
- trajectory, checkpoint/restart, seed와 environment provenance
- drift, temperature, pressure, density, distribution diagnostics

종료 기준:

- unit-cell 경계를 통과하는 energy·force finite-difference test가 통과한다.
- NVE energy drift와 momentum behavior가 사전 선언 기준을 충족한다.
- NVT temperature, NPT pressure·density 분포와 restart 일관성을 검증한다.
- long-range method와 실제 복잡도를 결과에 정확히 기록한다.
- 직접 Coulomb all-pairs는 tiny reference test 밖에서 금지한다.

### V2-5 — Production AI와 물리 결합

주요 산출물:

- license·source·split provenance가 있는 energy·force·pose dataset
- physics residual-energy SE(3) model과 parity·chirality channel
- `TorsionTopologyGNN` 기반 pose refinement
- `TemporalStateGNN` 기반 fixed-window short-rollout correction
- PINN objective와 science release gate
- ensemble uncertainty, calibration, OOD·chemistry abstention
- signed model card, runtime schema와 production checkpoint

종료 기준:

- protein family, ligand scaffold, target와 time leakage를 통제한 split을 고정한다.
- physics-only baseline 대비 AI의 개선과 실패를 모두 보고한다.
- energy, torsion, temporal, PINN, projection 요소별 ablation을 수행한다.
- equivariance, chirality, exact gradient와 long-rollout stability를 검증한다.
- calibration과 OOD 기준을 통과하지 못하면 AI capability를 비활성화한다.
- checkpoint의 code·feature·neighbor·parameter schema가 runtime과 완전히 일치한다.

### V2-6 — ROCm/HIP 가속

주요 산출물:

- cell-list, sparse message, force, projection, constraint, integrator HIP kernel
- frozen CPU golden reference와 kernel별 parity harness
- compact memory pool, zero-copy/SoA lifetime 계약과 overflow diagnostics
- deterministic mode와 high-throughput mode의 분리
- 로컬 AMD 설치·진단·fallback package

종료 기준:

- 실제 AMD GPU에서 CPU/ROCm energy, force, gradient와 docking ranking이 일치한다.
- capacity overflow와 fail-closed 동작도 CPU와 동일하다.
- determinism, peak memory, scaling과 장시간 soak evidence를 확보한다.
- 정확도 저하가 있는 mixed precision은 별도 capability로 표시한다.
- GPU가 없는 현재 모바일 환경에서는 이 단계의 gate를 닫지 않는다.

### V2-7 — 독립 상용 로컬 제품

주요 산출물:

- clean-machine installer와 완전한 offline execution bundle
- protein·ligand preparation wizard와 3D viewer
- structure analysis, docking, minimization, MD workflow와 job queue
- 중단·재시작, checkpoint, rollback, crash recovery와 resource limits
- 결과 table·3D pose·trajectory·uncertainty·provenance report
- tenant·path·secret 격리, signed manifest와 audit ledger
- capability별 enable/disable, license와 version migration 정책

종료 기준:

- clean installation, upgrade·rollback과 장시간 작업 복구가 통과한다.
- 데이터 격리, 악성 입력, path traversal과 resource-exhaustion test를 통과한다.
- blind customer-shadow 평가와 operator acceptance가 승인된다.
- 지원 chemistry·정확도·실패 범위를 UI와 보고서에서 명확히 알린다.
- 과학·benchmark·GPU·제품 gate를 모두 통과한 capability만 고객에게 활성화한다.

## 8. 병렬 capability lane과 의존관계

| Lane | 주요 범위 | 시작 가능 시점 | 다른 lane에 제공하는 계약 |
| --- | --- | --- | --- |
| Molecular | parser, preparation, canonical topology, chemistry coverage | V2-0 이후 즉시 | 모든 physics·AI·docking 입력의 identity |
| Physics | force field, minimizer, PBC, solvent, MD | V2-1 schema 안정 후 | AI baseline과 docking refinement energy |
| Structure | quality, pocket, interface, mutation, exact metrics | V2-1 parser와 함께 | 제품의 초기 독립 분석 capability |
| Docking | conformer, global search, local refinement, scoring | V2-2 energy 안정 후 | pose·ranking·interaction results |
| AI | residual energy, torsion, temporal, PINN, uncertainty | V2-2 reference와 dataset 후 | 제한된 정확도·효율 개선 |
| Runtime | Rust/HIP kernels, memory, determinism | CPU algorithm freeze 후 | 동일 science의 가속 실행 |
| Validation | corpus, oracle comparison, public holdout, evidence | 모든 단계와 병행 | capability 승격 결정 |
| Product | UI/API, jobs, reports, security, installer | contracts부터 병행 | 통과 capability의 안전한 전달 |

AI 학습과 GPU 최적화는 독립 CPU 물리 기준선보다 앞서지 않는다. CPU 결과가
계속 변하는 상태에서 GPU parity를 맞추거나, 불안정한 proxy force를 대규모로
학습시키면 검증 비용만 증가한다.

## 9. 검증과 승격 게이트

모든 capability는 서로 독립적인 다음 게이트를 통과해야 한다.

1. **계약 게이트:** schema, unit, atom identity, provenance, canonical hash,
   fail-closed.
2. **수학 게이트:** sparse bound, invariance·equivariance, parity,
   finite-difference force, projection adjoint.
3. **과학 게이트:** parameter coverage, conservation, ensemble, pose validity,
   structure metric, uncertainty.
4. **Benchmark 게이트:** 고정 public holdout, row-level evidence, failure row,
   baseline과 confidence interval.
5. **GPU 게이트:** 실제 CPU/ROCm value·gradient·ranking·memory·scaling parity.
6. **제품 게이트:** 설치, 복구, 보안, 보고서, 지원범위 표시와 customer shadow.

모든 release evidence에는 최소한 다음 정보를 포함한다.

- 원본 입력과 결과 SHA-256
- 실행 명령, random seed, Git commit와 software environment
- dataset·split·parameter·baseline·checkpoint version
- aggregate뿐 아니라 개별 결과 row와 실패 row
- benchmark 실행 전에 고정한 threshold
- uncertainty, confidence interval과 적용범위
- 자동 gate 결과와 최종 사람 승인 기록

## 10. 제품 성숙도 단계

| 제품 상태 | 진입 조건 | 외부 제공 정책 |
| --- | --- | --- |
| Scaffold | contract·unit test만 존재 | 개발자 내부 참고만 허용 |
| Internal alpha | capability의 수학 gate 통과 | 내부 synthetic·curated 입력만 허용 |
| Scientific beta | 과학 gate와 고정 benchmark evidence 통과 | 제한된 평가자에게 claim 범위를 명시해 제공 |
| Customer shadow | 실제 고객 입력을 결과 의사결정 없이 병렬 평가 | 결과는 검토용이며 자동 업무 사용 금지 |
| Release candidate | 보안·설치·복구·성능 gate까지 통과 | 명시된 chemistry·hardware 범위에서 pilot 허용 |
| Commercial release | capability별 승인과 운영 책임자 sign-off | 승인 capability만 제품 UI/API에서 활성화 |

하나의 기능이 commercial release라고 해서 전체 플랫폼이 자동으로 상용
승격되는 것은 아니다. 예를 들어 구조 품질 분석은 출시 가능하지만 FEP는
계속 차단된 상태가 될 수 있다.

## 11. 데이터·모델·파라미터 관리

- 원시 dataset, split manifest, parameter와 model checkpoint를 서로 다른
  versioned artifact로 관리한다.
- protein family, sequence identity, ligand scaffold, target, assay와 시간
  leakage를 가능한 범위에서 모두 통제한다.
- dataset license와 고객 데이터 사용 권한을 artifact에 기록한다.
- failure와 rejected chemistry를 삭제하지 않고 applicability evidence로 남긴다.
- model은 code commit, feature schema, neighbor schema, parameter version,
  dtype와 device policy를 함께 fingerprint한다.
- partial·shape/type/dtype mismatch, NaN/Inf 또는 legacy semantics checkpoint는
  production에서 fail-closed 처리한다.
- benchmark를 본 뒤 test split, threshold 또는 metric 정의를 변경하면 새
  protocol version과 독립된 재평가가 필요하다.

## 12. 핵심 위험과 대응

| 위험 | 잘못된 결과 | 대응 원칙 |
| --- | --- | --- |
| 조건부 `O(N)`을 무조건적 성능으로 표현 | 실제 density·candidate·long-range 비용 은폐 | hard cap, overflow row, scaling·memory evidence와 범위별 복잡도 표기 |
| parser의 조용한 chemistry 손실 | 잘못된 원자·전하·stereo로 전체 계산 오염 | canonical round-trip과 failure corpus, generic fallback 금지 |
| heuristic force field의 조기 제품 승격 | 그럴듯하지만 과학적으로 무의미한 energy·force | parameter coverage와 finite-difference·conservation gate 선행 |
| 학습 데이터 leakage | 공개 benchmark 성능 과대평가 | family·scaffold·target·time split와 immutable manifest |
| PBC image-shift gradient 오류 | 경계 통과 시 energy·force 불연속 | differentiable image shift와 boundary finite-difference test |
| 금속·cofactor·protonation 미지원 | 실제 표적에서 잘못된 pose·score | chemistry별 capability와 abstention, 단계적 coverage 확장 |
| AI direct-force drift | MD 장시간 불안정과 비보존력 | scalar residual energy와 exact VJP, rollout gate |
| CPU와 HIP kernel 불일치 | GPU에서만 ranking·trajectory 변화 | frozen CPU oracle와 kernel별 value·gradient parity |
| proxy metric의 공식 명칭 사용 | 고객이 정확도를 오해 | 정확한 정의 구현 또는 proxy 이름·claim 완전 분리 |
| 단독 개발 범위 과대화 | 모든 기능이 미완성 상태로 장기 정체 | critical path와 capability별 독립 출시, gate 미통과 기능 비활성화 |

## 13. 권장 critical path

개발을 재개할 때의 우선순위는 다음과 같다.

1. V2-0 contract와 CPU 결과를 안정화하고 불필요한 legacy import를 늘리지 않는다.
2. V2-1 parser·preparation과 supported-chemistry 표를 먼저 완성한다.
3. V2-2 독립 CPU force field의 작은 chemistry 범위를 정확하게 닫는다.
4. 정확한 structure-quality·pocket 분석을 초기 독립 capability로 만든다.
5. 안정된 energy·gradient 위에서 torsion-aware docking을 구현한다.
6. PBC·long-range·solvent·integrator를 닫아 MD capability를 분리 승격한다.
7. 충분한 reference data와 physics baseline을 확보한 뒤 production AI를 학습한다.
8. CPU algorithm·tolerance를 freeze한 다음 실제 로컬 AMD GPU에서 HIP parity를
   검증한다.
9. 마지막에 통과 capability만 제품 route와 UI에서 활성화한다.

GPU 없이 진행 가능한 단계는 V2-1, V2-2 CPU reference의 대부분, V2-3의
알고리즘·작은 benchmark, V2-4 CPU 정확성, V2-5 dataset·loss·CPU 검증,
문서·보안·제품 계약이다. 실제 ROCm 성능·메모리·determinism·soak와 GPU
제품 gate는 로컬 AMD 환경에서 별도로 닫아야 한다.

## 14. 장기 확장 항목

다음 항목은 핵심 V2 상용화 critical path를 닫은 뒤 별도 capability로 다룬다.

- sampled lambda ensemble 기반 독립 FEP와 BAR/MBAR
- protein conformational ensemble와 enhanced sampling
- de novo protein structure prediction 또는 sequence design
- covalent docking, metalloprotein, membrane protein 전용 chemistry
- wet-lab active learning과 자동 실험 설계
- multi-GPU·distributed execution

이 기능은 이름만 먼저 제품에 노출하지 않는다. 각 기능에 별도의 데이터,
과학, benchmark, GPU와 제품 gate가 필요하다.

MM/GBSA, FEP, `Delta G`, wet-lab hit, de novo structure prediction 또는
AlphaFold·Schrodinger·OpenMM 계열과의 parity는 non-empty blind row, 실패 row,
고정 protocol과 confidence interval이 확보되기 전까지 claim하지 않는다.

## 15. 결정 기록

현재 고정된 핵심 결정은 다음과 같다.

- 외부 molecular solver는 customer runtime이 아니라 offline oracle이다.
- v2 과학 core는 `betelgeuze_engine_v2/`에서 독립적으로 발전시킨다.
- AI는 non-attention·non-Transformer sparse residual-energy 구조를 기본으로 한다.
- force는 scalar energy의 exact reverse-mode gradient로 정의한다.
- TorsionTopologyGNN과 TemporalStateGNN을 혼합된 “T-GNN”으로 부르지 않는다.
- PINN은 solver가 아니라 objective와 release gate다.
- projection은 matrix-free·fixed-rank이며 dense `N x N` operator를 만들지 않는다.
- `O(N)`은 hard-cap·fixed-budget 조건부 계약이고 PME·ensemble 비용을 숨기지 않는다.
- CPU reference를 먼저 안정화하고 GPU parity는 실제 ROCm 장비에서 증명한다.
- 과학 gate를 통과하지 못한 capability는 제품에서 기본 비활성화한다.

다음 항목은 각 단계 착수 전에 다시 결정해야 한다.

- 최초 commercial chemistry coverage와 atom-typing 범위
- 첫 구조분석·도킹 benchmark protocol과 threshold
- PME와 FMM 중 첫 production long-range 방식
- 첫 AMD 지원 GPU·ROCm version matrix
- 로컬 GUI 기술과 offline installer 형식
- 상업 license, 공개 범위와 parameter·model 배포 정책

## 16. 관련 참고문서

- [Independent Engine v2 Architecture](independent_engine_v2_architecture.md):
  수학·AI·희소 기하·복잡도와 claim boundary
- [Independent Engine v2 Migration Matrix](independent_engine_v2_migration_matrix.md):
  기존 파일별 reuse·adapt·replace·archive 결정
- [`independent_engine_v2_capabilities.yaml`](../config/independent_engine_v2_capabilities.yaml):
  현재 capability 상태와 machine-readable blocker
- [Target Bioscience Architecture](target_bioscience_architecture.md):
  최종 workflow와 result contract 목표
- [Release Claim Evidence Ladder](release_claim_evidence_ladder.md)와
  [Benchmark Ledger](BENCHMARK_LEDGER_CURRENT.md): claim 승격 증거 규칙
- [Product Vision](PRODUCT_VISION_CURRENT.md)과
  [Legacy Product Implementation Plan](product_full_implementation_plan.md):
  기존 restricted 제품·운영 lane이며 V2 과학 완료 상태와 분리
- [Complete Commercial Product Gap Analysis](complete_commercial_product_gap_analysis.md):
  과거 시점별 상세 gap·receipt 참고자료이며 현재 전략의 source of truth는 아님
- [README 한국어](../README.ko.md): 저장소 운영·산출물·로컬 실행 개요

이 문서의 phase 완료 표시는 구현 코드, 테스트, row-level evidence와 capability
gate가 함께 변경될 때만 갱신한다. 계획 문구만으로 phase를 완료 처리하지 않는다.

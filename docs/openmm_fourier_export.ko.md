# OpenMM NoCutoff 리간드 → 기존 Fourier 매개변수 변환

이 추가 모듈은 준비된 힘장 값을 기존 자체 엔진 형식으로 옮긴다. 분자의
전하·양성자화 상태·힘장을 생성하지 않으며, 단백질 준비·도킹·실행 자격을
부여하지 않는다. 기존 `betelgeuze_engine_v2`와 CPU/Fourier 평가 코드는 수정하지 않는다.

## 제품과 연구 도구의 분리

제품 `betelgeuze_product.openmm_fourier_export.export_ligand`는 중립 snapshot
데이터만 받아 변환하며 표준 라이브러리만 사용한다. 외부 엔진이나 연구
adapter를 import하거나 호출하지 않는다.

네이티브 관측 함수는
`benchmarks.oracles.ligand_preparation.openmm_capture.capture_openmm_ligand`에
분리되어 있다. 별도 승인·제한된 연구 worker에서만 명시적으로 호출하는
도구이며 제품 기본 CLI나 oracle pack의 pinned-child 자격을 갖춘 실행기가
아니다. 기존 위치에 호환용 네이티브 wrapper를 남기지 않는다. 아래 실제
수치 증거는 이전 배치의 기록이며, 이동된 진입점은 별도 재실행으로 검증한다.

## 사용 경계

- 연구 관측 입력: OpenMM 8.4.0의 실제 `System`과 준비자가 보존한 원자 ID/결합 그래프,
  proper/improper 할당 근거. `capture_openmm_ligand`는 실제 API를 읽고
  직렬화 System 해시와 각 Force 행 수를 기록한다. 기대 해시는 원본을 읽어
  다시 직렬화한 정확한 UTF-8 artifact와 일치해야 하며, 원래 XML 파일이
  다른 형식이면 별도 원본·파생 provenance로 보존한다. 함수 호출 전에는 OpenMM을
  import하지 않는다. Context나 E/F는 생성하지 않는다.
- 변환: `export_ligand`가 `openmm_ligand_parameter_snapshot/1.0.0`을 받아
  기존 `cpu_prepared_fourier_parameters/1.0.0` 문서와 변환 영수증을 반환한다.
- 허용 Force: HarmonicBondForce, HarmonicAngleForce, PeriodicTorsionForce,
  NonbondedForce 각각 정확히 한 인스턴스. 미지원 Force를 조용히 제거하지 않는다.
- nonperiodic NoCutoff, constraint/virtual site/global parameter/offset 없음,
  direct-space 활성만 지원한다. periodic bonded/exception도 거부한다.
- 최대 256원자. 180° 선형각은 별도 기존 경로의 대상이므로 여기서는 거부한다.
- 준비자가 제공한 원자 ID와 hash는 대응 선언이다. 화학 상태/원자 대응의 진실성은
  별도 준비 단계가 검증해야 한다. 실행 전 기존 canonical topology hash와
  매개변수 로더/평가기 applicability 검사를 통과해야 한다.

## 손실 없는 항 변환과 거부 조건

| 원본 항 | 변환 |
|---|---|
| nm 거리 | Å = nm × 10 |
| kJ/mol 에너지 | kcal/mol = kJ/mol ÷ 4.184 |
| harmonic bond k | kJ/(mol nm²) ÷ 418.4; 양쪽 모두 ½ k Δr² |
| harmonic angle k | kJ/(mol rad²) ÷ 4.184; 양쪽 모두 ½ k Δθ² |
| periodic proper/improper | k ÷ 4.184; n·phase·ordered tuple 보존 |
| 원자 charge/LJ | 원래 q, σ, ε 보존; 0σ는 0ε일 때만 허용 |

proper/improper를 결합 그래프만 보고 추측하지 않는다. 실제 준비자의 할당
sidecar에는 Force/term index, 정확한 ordered tuple, kind, improper star center가
있어야 한다. 동일 proper path의 완전 역순은 동일 torsion angle이므로
정규화할 수 있지만 improper tuple은 재정렬하지 않는다. 정확히 같은
ordered definition/n/phase의 반복 Fourier 항은 진폭을 합치고 모든 원본
term ID를 보존한다. 서로 다른 위상은 합치지 않는다.

기존 평가기는 모든 그래프 각도/proper 경로의 명시적 항을 요구한다.
본 버전은 원본 할당에서 빠진 경로를 임의 0으로 만들지 않고 거부한다.
원본이 명시한 0 진폭 항은 유지한다. 완전한 원본 System이 입증하는
의도적 0 항을 별도로 표현할 필요가 있다면 후속의 명시적 계약이 필요하다.

## NoCutoff를 유지하는 전체 pair 표현

기존 ordinary nonbonded는 LJ와 Coulomb 양쪽을 switch한다. 따라서 OpenMM
NoCutoff를 ordinary pair로 직접 바꾸면 같은 모델이 아니다.

본 변환은 모든 n(n−1)/2 ordinary pair를 excluded로 지정하고, 각 활성
pair를 기존 **unswitched listed pair**로 정확히 한 번 기록한다. ordinary
pair는 Lorentz–Berthelot mixing과 원래 q를 사용하며, exception은 원래
pair별 σ/ε/charge product를 사용한다. 완전히 0인 exception만 excluded-only로
남는다. 최대 32,640 pair이고 성능 향상 주장이나 GPU 기본값 변경은 없다.

listed Coulomb가 q_i·q_j·scale 형식이므로 원본 exception의 비율이 [0,1]
밖이거나 q_i·q_j=0인데 원본 charge product가 0이 아니면 표현 불가로 거부한다.
원본 전하를 조정하거나 scale을 clipping하지 않는다. 원본 exception charge
product와 원본 전체 snapshot hash를 남긴다.

OpenMM 8.4 CODATA 상수 138.93545764438198 kJ nm/(mol e²)는
332.06371329919216 kcal Å/(mol e²)로 변환된다. 기존 엔진 상수는
332.063713299이며 차이는 약 −1.92×10⁻¹⁰이다. 이를 영수증에 기록하고
원본 전하·힘장 값을 맞춰 바꾸지 않는다. 따라서 비트 단위 동일성이나
실험 없는 수치 동등성을 주장하지 않는다.

전체 pair 표현은 기존 minimum-distance/기하 applicability 영역 안에서의
정적 리간드 내부 모델이다. 단백질 내부 에너지, ligand–receptor cross의
cutoff/용매 정책, MD의 질량·constraint·periodic 조건을 함께 변환하는 기능은 아니다.

## 증거와 비증거

테스트는 단위 변환, 전체 pair 보존, exception 표현 불가 거부, signed/중복
Fourier 항, ordered improper, source inventory, periodic/offset/constraint
거부를 검사한다. 표준 라이브러리 API double은 capture 제어 흐름 검사이지
실제 OpenMM 실행 증거가 아니다. 실제 E/F 비교는 별도 승인된 환경에서
동일 source System/좌표/원자 대응으로 수행해야 한다.

항상 `engine_admission_performed=false`, `source_equivalence_verified=false`,
`energy_force_evaluations=0`을 출력한다. 이는 변환기가 평가기를 실행하지
않았다는 뜻이며, 향후 별도 수치 비교 결과는 별도 증거로 관리한다.

## 한 공개 리간드의 실제 정적 수치 점검 (2026-10-27)

공식 PoseBusters 자료의 6YQW_82I 시작 리간드(19원자)를 별도 환경에서
Sage/AM1-BCC로 매개변수화한 실제 OpenMM 8.4.0 System을 읽었다. 원본
73개 periodic 항(55 proper + 18 improper), 31개 angle, 83개 exception을
변환했으며 기존 Fourier 로더를 통과했다. 누락 항 0 채우기는 없었다.

시작 구조와 정해진 좌표 교란에서 실제 자체 엔진 E/F 56회, OpenMM state
조회 66회를 수행한 별도 기록은 다음을 보였다.

- 최대 직접 에너지 차이: 2.14×10⁻¹¹ kcal/mol.
- 최대 직접 힘 성분 차이: 3.94×10⁻¹² kcal/(mol Å).
- 사전 지정 18개 유한차분 판정의 최대 오차: 1.74×10⁻⁸ kcal/(mol Å).
- 원본/파생 System의 별도 정적 E/F 대조 2회에서 차이 0.
- 결과 후 허용오차 변경 없음. 수용체 계산 0회, 도킹 0회.

이는 한 리간드의 지정된 모델·좌표 표본에 대한 변환 수치 증거다.
모든 화학종의 매개변수화, 모든 좌표의 미분 검증, 결합 포즈 정확도,
도킹 성공률, 전체 단백질 준비나 제품/상용 성능을 입증하지 않는다.
공식 원본 자료: https://zenodo.org/records/8278563


## Relocated-entrypoint validation (2026-10-27)

The actual research-package preparation and capture entry points, followed by the
stdlib-only product conversion, were rerun successfully using genuine pinned-main
parent packages. On the same one public 19-atom ligand, 120 direct comparison
channels passed: maximum energy residual 2.141575805580942e-11 kcal/mol and force
residual 3.375077994860476e-12 kcal/(mol angstrom). Original/derived E/F deltas
were zero; one own E/F call, six source queries and two capture/control queries
were used, without new finite-difference evaluations. Independent recomputation
confirmed these comparisons. This is not 120 independent molecules.

An initial preparation returned valid artifacts but its harness subsequently
failed while recording imports; that failed attempt is retained. A harness-only
recorder correction and clean retry completed successfully: two fresh AM1-BCC
preparations on the same molecule, not broader chemical coverage. Source code,
chemistry invariants and tolerances were unchanged. The original PR architecture
check failure is also retained; this relocation fixes placement rather than
weakening the unchanged guard. Local architecture checks are sparse, not full-repo
proof; exact-head hosted CI supplies the full-repository check. Research helpers
are not production-native integration or qualified contained-oracle execution.
No receptor, docking, optimization, accuracy or commercial claim is added.

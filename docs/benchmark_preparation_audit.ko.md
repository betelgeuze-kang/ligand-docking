# 공개 벤치마크 입력의 준비 공백 진단

`betelgeuze_product.benchmark_preparation_audit`는 좌표를 받지 않는 표준
라이브러리 진단이다. 원자·결합 관측으로 유일한 결합/각도/4원자 경로를
열거하고, 제공된 매개변수 문서의 **원자 인덱스 목록만** 비교한다.
매개변수를 생성하거나, 수소를 보완하거나, 화학 상태를 결정하거나,
엔진 입력·실행을 승인하지 않는다. `indices_match`도 값·단위·물리 모델의
적절성이나 실행 적격성을 뜻하지 않는다.

## 인터페이스

`graph_demands(topology)` 및
`audit_preparation(topology, receptor_atom_count=..., base_parameters=None,
receptor_parameters=None)`을 제공한다.

`topology`는 다음 필드를 정확히 가진 관측 문서다.

- `schema_id`: `benchmark_ligand_topology_observation/1.0.0`
- `source_sha256`: 관측한 원본 파일의 실제 SHA-256
- `elements`: 원본 원자 순서의 원소 문자열 목록
- `bonds`: 0부터 시작하는 원자 인덱스 두 개의 목록
- `hydrogen_state`: `unverified` 또는 `declared_all_explicit`

두 번째 수소 상태도 호출자 선언일 뿐이다. 출력의
`hydrogen_completeness_verified`는 항상 false다. 해시는 전달된 관측의
동일성이지 파서 정확도·원본 인증의 증명이 아니다. 이 함수는 SDF/PDB를
직접 해석하지 않으며 기존의 별도로 검증된 파서 관측을 받는다.

`base_parameters`의 `atom_parameters`, `bonds`, `angles`, `torsions` 배열과
수용체 원자 배열에서 관련 인덱스만 읽는다. 배열 없음과 빈 배열을
구분한다. 원자/결합/각도 중복은 인덱스 불일치로 기록한다. 하나의 proper
경로에 여러 Fourier 항이 있는 것은 허용하되 반복 경로를 보고한다.
파라미터 값이나 중복 Fourier 계수의 적절성은 검사하지 않는다.

모든 graph path가 물리적으로 0이 아닌 항을 요구한다는 뜻은 아니다.
특히 proper 경로 수와 실제 Fourier 항 수는 다르며, 소스 힘장의 0항·고리
정책을 별도로 확인해야 한다. shortest-path pair counts 역시 제외/1–4
스케일 정책을 생성하지 않는다. improper는 그래프만으로 생성하지 않는다.

## 실제 개발 입력에서 확인한 공백

공식 PoseBusters 논문 308개 ID 목록에 속하는 `6YQW_82I`를 개발 사례로
선택했다. 이는 대표 성능 표본이나 잠금 평가 자료가 아니다. 공식 배포는
원래 428개이며 논문은 별도의 308개 부분집합을 사용한다.

- 공식 설명: https://zenodo.org/records/8278563
- 시작 구조: 공식 `6YQW_82I_ligand_start_conf.sdf`
- 시작 파일 SHA-256:
  `43ff3d67c41ed93fc69e3734ec0061fbb79c7d570b7340e8041dc83268559624`
- 19개 원자(11개 중원자, 8개 명시적 H), 19개 결합,
  그래프상 각도 31개, 유일한 4원자 proper 경로 36개.
- 수용체의 정적 ATOM/HETATM 관측 수는 821개이며 별도 평가기 파서에서도
  821개 원자·명시적 H 0개를 확인했다. 수소 추가·잔기 상태 결정 후의
  준비된 수용체 원자 수라고 주장하지 않는다.
- 제공된 공개 구조에는 현재 자체 엔진이 사용할 완전한 ligand atom/bond/
  angle/proper 매개변수와 receptor nonbonded 매개변수가 없다.
- all-zero 형식전하 관측을 원자별 부분전하로 대체하지 않는다.
- 원자에 붙은 입체화학 표시가 없다는 텍스트 관측만으로 stereo identity를
  승인하지 않는다. 파서·sanitize·그래프 대응 검증이 별도로 필요하다.

공식 README가 설명한 시작 구조의 ETKDGv3+UFF 생성은 upstream 준비다.
자체 제품에서 conformer를 생성했다는 증거가 아니다. 별도 결정 리간드
좌표는 평가 전용이며, 파일 해시가 다른 사실만으로 시작 구조의 독립성을
입증하지 않는다. 알려진 포켓의 정의와 출처도 따로 잠가야 한다.

위 실제 사례 관측은 graph audit가 실행되었다는 증거다. 도킹·최적화·
PoseBusters 통과·정확도 검증이나 완전한 입력 준비를 뜻하지 않는다.
원본 파일 및 실행 산출물은 이 변경에 포함하지 않는다.

## 기존 자체 엔진 경로를 구분해야 하는 이유

현재 소스의 구조 보존 fixed-receptor provider는
`ReferenceForceFieldV2Parameters`를 받는다. 여기에는 비음수 proper amplitude,
양수 sigma 및 harmonic out-of-plane improper라는 제한이 있다.
이를 맞추려고 signed/periodic/zero-LJ 소스 항을 버리거나 몰래 바꾸면 안 된다.

다른 기존 경로인 `cpu_refinement_fourier_v1`는 signed proper Fourier,
원래 순서를 유지하는 periodic improper와 star center, sigma=0/epsilon=0,
명시적 listed pair LJ·정전기 항을 지원한다. `cpu_refinement_linear_angle_v1`는
선형각을 별도로 다룬다. 따라서 첫 실분자 실행은 적합한 기존 자체 엔진
경로를 명시적으로 선택하면 되며, 모든 입력을 새 provider에 강제할 필요는 없다.

현재 `prepared_gromacs_input`은 원본 topology sections와 원자별 nonbonded
항을 보존하지만 스스로 화학 매개변수를 생성하지 않는다. 명시적으로
cross-only 범위이며 intramolecular gen-pairs/fudge가 적용됐다는 증거도 아니다.
원본 sections가 존재하는 것과 완전한 bonded parameter export는 다르다.

## 다음 실제 기능 개발

1. 공개 시작 SDF의 같은 화학 상태와 원자 대응을 유지하는 검증된 ligand
   parameterizer 출력을 확보한다. 후보는 OpenFF toolkit+명시적 charge backend,
   또는 GAFF/AmberTools다. 수용체는 별도의 잔기·결손·H 정책 및 protein
   force-field assignment가 필요하다. RDKit conformer 생성이나 UFF 최적화만으로
   이 요구가 충족되지는 않는다.
2. 해당 출력에 대해 기존 Fourier 모델로 표현 가능한지 전 항목을 대조한다.
   변환 범위는 atom order, 단위, harmonic factor, proper/improper 순서·phase,
   exclusions, explicit 1–4 pairs와 스케일, combining rule, zero-LJ 처리다.
   적용하는 cutoff/switch는 원래 시뮬레이션 Hamiltonian과 구분한다.
3. 소스에 없는 항을 기본값으로 채우지 않고 미지원 형식을 실패로 남기는
   좁은 exporter를 작성한다. source force-field별 model-equivalence 검산 후
   실제 엔진의 canonical loader와 topology admission을 통과시킨다.
4. 그 뒤에만 자체 엔진의 첫 단일 CPU 계산과 SDF 출력 roundtrip을 실행한다.

오래된 DRD2 전용 조사 도구는 ChimeraX 내 AmberTools·GAFF·OpenMM 경로와
특정 단백질 복구 정책을 가정하며 일부 경로에 neutral-charge fallback이
있다. 이를 일반 공개 벤치마크 준비기로 그대로 호출하거나 복제하지 않는다.

이 변경은 frozen engine/cpu_refinement 소스를 수정하지 않으며 실행 게이트,
기존 HOLD/UNKNOWN, 물리 모델 또는 평가 기준을 완화하지 않는다.

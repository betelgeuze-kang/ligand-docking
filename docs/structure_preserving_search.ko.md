# 구조 보존 국소 탐색: 강체·bridge torsion 갱신

## 목적과 현재 상태

`betelgeuze_product/structure_preserving.py`는 **명시적으로 선택하는
연구용 수치 구성요소**다. 전체 원자 Cartesian 좌표를 자유롭게 움직이는 대신
분자 전체 이동, 강체 회전, 허용된 단일 결합 비틀림으로 같은 목적함수를
낮추는 bounded local refinement를 제공한다.

기존 강체 제안 생성, Torch forest forward kinematics, V3–V8 접촉/충돌 정제,
고정 mixed64 allocation, 기본 CLI/정책은 바꾸지 않는다. 기존 일반 torsion
기능을 처음 구현한 것이 아니다. 이 추가분은 **외부 E/F 평가기를 사용한
현재 상태의 일반화 힘과 구조 보존 retraction을 연결**하는 별도 선택 경로다.

이 코드는 기존 Scorer의 동결된 engine source manifest를 변경하지 않는
**product 소유 source-checkout 확장**이다. 같은 자체 엔진의 기존 계약을
사용하며 다른 도킹 엔진으로 대체하지 않는다. 기존 manifest를 다시 봉인하거나
기존 `betelgeuze_product/__init__.py`를 변경하지 않는다. isolated Engine v2
wheel에 이 product 확장이 포함되거나 설치된 것으로 간주하면 안 된다.

도킹 정확도, 힘장 타당성, CPU/HIP parity, 상용/제품/고객 자격은 승격하지
않는다. 화학 입력 준비 또는 native 실행에 대한 기존 HOLD/UNKNOWN은 유지한다.
전체 포켓 탐색이나 정답 좌표와 독립적인 시작점 생성기 자체가 아니며,
나쁜 초기 포즈에서 정답을 찾는다는 보장도 없다.

## 입력과 보호 범위

- 좌표는 Å, 물리적 힘은 평가기의 energy 단위/Å, 회전·비틀림은 rad다.
  하나의 실행에서 평가기의 energy 단위와 모델은 고정되어야 한다.
- 최대 512 원자, 128 rotor, 원자 수의 4배 이내 결합을 갖는 **하나의
  연결된 covalent graph**만 받는다. 복수 fragment는 별도 정책 전까지 거절한다.
- 결합 종류는 single/double/triple/aromatic/amide/other로 명시한다.
  single이라고 자동 rotor로 삼지 않는다. 호출자가 화학/authority 계약에서
  허용한 방향성 rotor `(a, b)`를 별도로 제공해야 한다.
- rotor는 single edge여야 하며 그 edge를 지운 뒤 `b`에서 `a`에 도달하면
  고리 결합이므로 거절한다. 움직이는 집합은 `b` 쪽 **전체 연결 성분**이다.
  부분 mask나 forest만 보고 ring closure를 끊는 방식은 허용하지 않는다.
- topology가 참이라는 것을 그래프 검사만으로 인증하지 않는다. 잘못된
  결합 종류/원자 대응/화학 상태 선언을 고치는 chemistry perception 기능은 없다.
- 강체 proper rotation과 bridge 회전은 정확 산술에서 bond length와 local
  bond angle, local signed stereochemical volume을 보존한다. 후자는 새 stereo
  perception이나 절대 CIP label 검사가 아니다. 모호/누락 stereo를 지원한다고
  해석하지 않는다. 전후 covalent distance의 수치 drift도 검사한다.
- 고리 내부 rotor는 거절하지만, 비회전 ring이 bridge 한쪽에 포함된 경우에는
  ring 전체가 강체로 움직인다. receptor clash/self-clash/허용 포켓/QC는 별도다.
- 비유한 값, 1e6 Å를 넘는 좌표 성분, 1e-10 Å 이하 covalent/rotor 축은
  수치 지원 범위를 벗어나므로 거절한다.

## 일반화 힘과 알고리즘

평가기의 **raw physical force** `F = -dE/dx`를 사용한다. Cartesian tangent
projection된 힘을 다시 사용하면 다른 목적의 미분이 될 수 있다.

- 이동: `sum(F_i)`
- 현재 centroid를 지나는 world 회전: `sum((x_i-c) cross F_i)`
- 현재 `(a→b)` 축의 rotor: 움직이는 원자에서
  `sum(F_i dot (axis cross (x_i-x_a)))`; 정확 고정된 축 원자 `b`는 제외한다.

회전 torque는 **현재 상태를 원점으로 하는 국소 증분의 음의 미분**이다.
비영 회전 chart 좌표에 대한 미분과 동일하다고 주장하지 않는다. 수락할 때마다
현재 centroid·axis·힘을 다시 계산하며, nested rotor 축도 앞선 움직임을 반영한다.

각 iteration은 설정한 이동/회전/rotor step bound에서 일차 감소 예상량이
가장 큰 block을 선택한다. 동점은 이동, 회전, 명시한 rotor 순서로 고정한다.
해당 block의 힘이 그 단위의 정지성 허용오차 이하이면 후보에서 제외한다.
다른 rotor의 예산 소진 후 roundoff 수준 강체 힘을 계속 쫓지 않는다.
같은 현재 상태에서 step을 절반씩 줄여 Armijo 감소를 검사하고, 엄격한 에너지
감소가 관측된 경우만 수락한다. 후보가 다르지 않거나 보존 검사가 실패하면
평가기로 보내지 않는다. 가장 유리해 보인 block이 막히면 line-search 실패로
종료할 수 있으므로 전역 탐색/일반 수렴 또는 다른 방법보다 우월함을 보장하지 않는다.

회전·비틀림은 유한 Rodrigues 회전이다. 혼합 단위의 힘 norm 하나를 수렴
지표로 만들지 않는다. 이동 기준과 angular 기준을 따로 적용한다.
`projected_stationary`는 **허용한 자유도에 대한 정지성**이다. 이때 Cartesian
힘이 클 수 있으며 최소점·정답 포즈·모든 원자 힘 수렴을 뜻하지 않는다.

## 예산과 상태

`SearchConfig`는 수락 step 수, 평가 callback 호출 수, backtrack 수와 각
step 크기를 제한한다. 추가로 수락된 이동 거리의 합, 회전 각 크기의 합,
각 rotor 각 크기의 합을 각각 제한한다. 이들은 **누적 경로 길이**이지
순이동·최종 orientation·순 torsion angle·최대 원자 변위가 아니다.

초기/수락/거절/예외/잘못된 출력 callback 모두 invocation 예산을 소비한다.
`evaluation_attempts = successful_evaluations + failed_evaluations`이며
성공 호출에는 line-search에서 거절된 결과도 포함된다. 숨겨진 마지막 재평가가 없다.
callback 한 번이 실제 backend E/F/kernel 한 번이라는 주장은 아니다.
평가기 자체의 native 비용 및 중단/프로세스 자원 관리는 owning evaluator가 담당한다.

종료 상태는 `projected_stationary`, `step_limit`, `evaluation_limit`,
`motion_limit`, `line_search_failed`, `evaluation_failed`, `geometry_failure`,
`numerical_failure`, `no_representable_step`다. 불완전/실패를 정지성으로 바꾸지 않는다.
초기 평가 실패는 energy/forces=None이고 이후 실패는 마지막 수락 좌표·energy·힘을
보존한다. callback의 일반 Exception 내용은 외부에 노출하지 않는다.
KeyboardInterrupt/SystemExit 같은 process-level interruption은 이 함수가 삼키지 않으며,
그 경우 완결된 SearchResult가 생겼다고 가정하면 안 된다.

입력과 출력 좌표·metadata는 immutable tuple로 보존한다. 수치 코어는 momentum,
L-BFGS history 또는 전역 캐시를 갖지 않으므로 새로운 호출에 오래된 최적화 이력을
재사용하지 않는다. 외부 평가기의 cache 무효화까지 자동 보장하지 않는다.
평가기는 전달받은 새 좌표와 고정 context에 대해 실제로 평가해야 한다.

## 연결과 검증

코어는 `StructureTopology`, `SearchConfig`, `Evaluation` 및
`refine_structure(coordinates, topology, evaluate, config)`를 제공한다.
평가 callback은 정확한 원자 순서의 좌표 tuple을 받아 energy와 raw force를 반환한다.
동일 atom count만으로 chemical identity가 보장되지 않으므로 authority·model·source
binding은 상위 refiner가 확인해야 한다.

별도 opt-in adapter `betelgeuze_product/structure_preserving_refinement.py`는 기존
`DockingPoseRefiner` 경계에서 사용할 목적의 연결이다. 기본 경로에 등록하거나
기존 인증·scoring·pose validity를 생략하지 않는다. 해당 adapter의 실제 합성
계약 테스트와 아래 stdlib 수학 테스트는 서로 다른 검증 층이다.

`BoundEnergyForceProvider`는 좌표와 모델 identity를 결속하는 평가 인터페이스다.
이 변경에는 실제 분자 물리 평가기를 감싸는 완성된 provider 구현이 포함되지
않으며, 인터페이스의 존재가 native 실행을 승인하지 않는다. 선언한 digest의
일치는 데이터 결속 검사이지 출처의 진위나 실행 자격 인증이 아니다.
기존 candidate search는 opt-in refiner를 전달받을 수 있지만 기본 CLI와
기본 탐색 경로는 변경하지 않는다. 실제 계약 타입을 사용하는 합성 adapter
테스트도 실제 분자 E/F 평가와 별도로 보고해야 한다.
adapter 인스턴스는 단일 worker에서 사용한다. 반환 proposal의 최종 좌표와
재계산한 torsion metadata가 정제 결과이며, 원래 rigid rotation/translation
필드는 시작 배치의 metadata로 남는다. 이를 최종 포즈의 rigid transform으로
다시 해석하지 않는다.

```bash
python tests/unit/test_engine_v2_structure_preserving.py
python -O -S tests/unit/test_engine_v2_structure_preserving.py
python -m pytest -q tests/unit/test_engine_v2_structure_preserving_refinement.py
```

수학 테스트는 rigid/rotor 역변환, local chirality·bond 보존, nested rotor,
현재 chart의 여러 h 유한차분, 잘못된 topology·force·예산·실패 상태를 다룬다.
작은 분석 함수와 작성한 그래프는 실제 분자 실행이 아니다. 실제 개선 채택에는
승인·자격이 충족된 실제 입력에서 같은 시작점·같은 총예산으로 후보 회복률,
구조 퇴행, 실패 및 비용을 비교해야 한다. 그 실행이 없는 상태에서 테스트 통과를
도킹 정확도 개선이나 파일럿 전체 완성으로 보고하지 않는다.

## 후속 연구용 물리 evaluator 연결

위 내용은 PR614 자체의 범위와 당시 검증 근거를 보존한 기록이다. 후속 확장은
[고정 수용체 구조 보존 정제](fixed_receptor_structure_refinement.ko.md)에서
기존 자체 CPU `FixedReceptorEvaluator`의 선택적 provider 연결과 구성요소·
제약·최종 strain 정책, 복구 가능한 좌표 trial 거절을 제공한다. 이는 제품
기본 활성화, native 실행 승인, HOLD/UNKNOWN 해제 또는 실제 분자 도킹 정확도
입증을 뜻하지 않는다. 기존 PR614 합성 검증과 후속 실제 CPU 합성 매개변수
통합 검증의 범위를 구분해야 한다.

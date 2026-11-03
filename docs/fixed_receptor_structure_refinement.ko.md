# 고정 수용체 구조 보존 정제: 연구용 연결

이 모듈은 기존 `FixedReceptorEvaluator(ExtendedEvaluator(parameters), fixed)`를
PR614 구조 보존 탐색기에 연결한다. 신규 엔진·힘장·준비·순위 모델이 아니다.
실행 승인, native qualification, 제품 기본 경로 또는 CLI를 만들지 않는다.
호출자는 기존 입력·런타임 승인과 HOLD/UNKNOWN 정책을 그대로 유지해야 한다.
해시와 명시적 매개변수는 교차 연결 오류 검사이지 실행 허가증이 아니다.

## 범위와 호출

`FixedReceptorEnergyForceProvider`는 인증된 authority, 원본 ligand/receptor,
명시적 v2 내부 매개변수와 cross 매개변수를 요구한다. CPU float64, 비주기,
단일 model, ligand 최대256원자/receptor 최대8192원자만 지원한다.
리간드·수용체 canonical hash와 좌표계, 매개변수/부분전하 대응을 검증한다.
평가 호출은 새 ligand 상태와 radius graph를 만들며, 모델·좌표 영역 검사를
통과한 호출만 실제 raw E/F를 계산한다.
Cartesian force를 tangent force로 바꿔서 미분으로 제시하지 않는다.

`FixedReceptorStructureCoordinator.run(proposal, max_steps=...)` 결과의
`admissible`은 정제 정책 통과만 뜻한다. 구조 유효성, 순위 적합성,
도킹 정확도 또는 실행 승인을 대신하지 않는다. 불채택 결과도 좌표와
정제 기록을 남기므로 소비자는 `admissible`을 반드시 검사해야 한다.

## 기존 과학 정책 유지

성공한 E/F마다 내부·cross LJ·cross Coulomb·합계, 제약조건 관측값,
과학적 blocker, calibrated=False/validated_for_composition=False를 보존한다.
최종 내부 에너지 증가가 명시된 cross 한도를 초과하면 불채택한다.
이는 **최종 채택 정책**이며 탐색 trial에 새 strain 제한을 도입하지 않는다.
E/F 호출 전 기하 관측만으로 초기 거리 제약을 검사하며 불충족이면 탐색을 중단한다.
이 거절은 E/F 0회이고 초기 제약 거절 기록에 남는다. 추가 또는 캐시 E/F 호출은 없다. 거리 제약은 회전 가능한 결합 이동으로 달라질 수 있으므로 최종 관측을
검사한다. 구조 보존이라는 이유만으로 모든 제약이 충족됐다고 간주하지 않는다.

`admission_document()`는 기존 selection의 strain 필드를 반드시 포함하며
`converged=False`를 유지한다. projected_stationary는 기존 Cartesian/tangent
수렴과 다르다. 기존 require_convergence=True 정책은 자동 통과하지 않는다.
과학적 미검증 blocker는 계산 성공으로 사라지지 않는다.

## 검증 경계

단위 테스트는 명시적으로 작성한 합성 원자/매개변수의 실제 자체 CPU E/F를
사용한다. 직접 evaluator 일치, 유한차분, 새 neighbor graph, 입력 변경,
좌표계, 예산, component/constraint 전달을 검사한다. 실제 약물 분자·재도킹
성공률·상용 성능·HIP/GPU 성능의 근거가 아니다. 신규 코드는 source-checkout
연구 확장이고 기존 격리 engine wheel 배포에 포함된다는 주장을 하지 않는다.

## 복구 가능한 trial과 비용 회계

`RecoverableTrialRejection("coordinate_domain_singularity")`는 명시적으로
검사한 현재 좌표의 거리 영역 위반에만 사용한다. 먼저 기존 extension
위상 검사와 `_applicability_blockers`를 **hard 검사**한다. 잘못된 매개변수와
충돌이 동시에 있어도 잘못된 모델을 재시도로 숨기지 않는다. 실제 evaluator의
예외 종류나 문자열을 일괄 soft 처리하지 않는다. 아직 명시적으로 분류하지
않은 각도·improper 특이점 등의 실제 예외는 보수적으로 hard 실패한다.

인식한 trial 거절은 같은 이동의 step을 절반으로 줄이며 호출·backtrack
예산을 소비한다. 초기 좌표에서 발생하면 채택 상태 없이 실패한다.
`recoverable_rejections`는 `failed_evaluations`의 부분집합이며
`evaluation_attempts = successful_evaluations + failed_evaluations`이다.
복구 가능한 거절과 일반 에너지 거절 모두, 거절된 trial이 호출 예산을
소진하면 `evaluation_limit`을 기록한다. backtrack 동시 소진보다 우선한다.
hard 실패는 `evaluation_failed`를 유지하며 성공한 채택·정지 판정은 바꾸지 않는다.
모델·입력·정체성이 바뀌면 soft 예외를 전달하기 전에도 hard 실패한다.

coordinator의 evaluation_attempts는 core의 모든 callback 시도이며,
provider_admitted_attempts는 정체성·capacity 사전검사를 통과한 provider 호출이다.
provider 자체의 evaluation_attempts 속성도 이 admitted 횟수다. 사전검사 거절을
전체 core 예산에서 빼지 않는다. 이 둘과 provider 소유 graph build 시도, 실제 물리 evaluator
호출, 복구 가능한 거절을 따로 센다. 실제 evaluator 내부의 정합성 확인용
추가 graph rebuild는 provider graph 횟수에 포함되지 않는다. 이 숫자는
벽시계 시간이나 전체 네이티브 연산량을 대신하지 않는다. 거절된 trial도
전체 탐색 예산에서 제외하지 않는다. 최종 관측은 이미 계산한 endpoint에서
찾으므로 보고서를 만들기 위한 숨은 추가 E/F 호출이 없다.

반환하기 전에 실제 evaluator fingerprint, 에너지·힘 shape/device/dtype,
유한성, 단위·미분 의미·미검증 descriptor·고정 수용체 blocker를 검사한다.
잘못된 force 의미를 `BoundEnergyForceResult` 기본값으로 다시 표시하지 않는다.

정제 실패 시에도 `attempts`의 optimizer 회계와 `failed_work`의 후보별
callback/graph/물리 평가/복구 거절 횟수를 보존한다. 초기 거리 제약 거절은
별도 `initial_constraint_rejections`에 저장되며 E/F·graph 작업은 0회다.

refiner의 torsion anchor 등 0-callback 사전검사 실패는 채택된 시도가 아니며
`failed_work`에 저장하지 않는다. 실제 optimizer attempt가 있을 때만 해당
상세 작업 기록을 저장하여 별도 실패 맵이 max_attempts를 우회하지 않게 한다.

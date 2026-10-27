# 공개 포즈 평가 실행 기록 v1

`betelgeuze_product/public_pose_benchmark.py`는 표준 라이브러리만 사용하는
별도 실험 기록 도구입니다. 기존 `benchmark_contract.py`의 평가 계획이나
`benchmark_ledger.py`의 외부 주장 관리 규칙을 대체하거나 변경하지 않습니다.
엔진 소스, 모델, 준비 정책, 실행 승인, 보호된 입력을 변경하지 않습니다.

## 기록하는 것

- 데이터셋 이름·릴리스·manifest SHA-256와 사전 고정 사례 목록
- `development` 또는 `locked_evaluation` 목적
- 엔진별 버전·설정 SHA-256·하드웨어 식별자·스레드 수와 seed 목록
- 준비·포켓·평가 설정 SHA-256, 평가기 버전, 필수 PoseBusters 검사 이름
- 순서가 고정된 `prepare/search/refine/select/evaluate` 단계 관측
- 선택된 Top-1 포즈 식별자·SHA-256와 평가 대상 SHA-256의 일치
- RMSD(Å), 명시적인 검사별 참/거짓/미측정, 선택적 시간·RSS 관측

해시는 일관성을 묶는 수단이지 인증이나 실행 적격성 증명이 아닙니다.
`locked_evaluation` 문자열을 지정하는 것만으로 맹검이나 데이터 접근 통제가
성립하지 않습니다. 별도 절차에서 설정과 개발/평가 분리를 보장해야 합니다.

## 실패·누락과 분모

입력 protocol에 선언한 모든 사례·엔진·seed 조합을 출력합니다. 기록이 없는
조합도 `recorded=false`, 전 단계 `not_run`으로 남습니다. 이미 추가한 결과는
덮어쓸 수 없습니다. 새 실험은 별도 protocol/ledger로 작성합니다.

`success`는 해당 단계가 완료됐다는 의미입니다. `failure`, `error`,
`unsupported`, `timeout`, `unassigned`는 각각 이유 코드를 요구합니다.
실패나 미실행 이후 단계가 실행된 모순된 기록은 거부합니다. v1은 위 다섯
단계의 순차 경로만 지원하며, 외부 엔진의 단계 생략을 자동 추론하지 않습니다.

예를 들어 아직 매개변수 준비 도구가 없는 경우에는 준비 단계에
`status=not_run`, `reason_code=parameterization_not_available`를 기록합니다.
그 사실만으로 해당 분자가 화학적으로 `unsupported`라고 판단하지 않습니다.
원시 예외, 고객 정보, 경로 대신 통제된 이유 코드를 사용합니다.

집계는 엔진별·seed별로 분리하며 seed를 서로 다른 분자로 합치거나 가장 좋은
seed만 선택하지 않습니다. 모든 사례의 종료 결과가 기록되기 전에는
`aggregation_status=incomplete`, 성공률은 `null`입니다. 성공 개수가 0이라는
중간 상태를 실제 측정된 0% 도킹 정확도라고 표현하지 않습니다.

종료 결과가 모두 기록되면 사전 고정 전체 사례를 분모로 공동 성공률을
계산합니다. 실패·미지원·시간초과·미할당은 분모에 남습니다. 준비 실패만으로
이루어진 0% 결과도 엔진이 만든 포즈의 정확도와 구분해야 하므로 평가 완료 수와
각 단계 상태를 함께 해석해야 합니다. 실행 오류를 무시한 과학적 결론도 금지됩니다.

## 공동 성공의 의미

평가가 완료되고, 동일 Top-1 포즈의 RMSD가 고정된 `lt` 또는 `lte` 경계를
통과하며, protocol에 명시된 모든 검사가 정확한 boolean `True`여야 합니다.
필수 검사가 없거나 `None`이면 완료된 평가로 기록할 수 없습니다. 명시적으로
`False`인 검사는 평가 실행 완료와 양립하지만 공동 성공은 아닙니다.

RMSD 성공 개수, PB-valid 개수, 교집합 성공 개수는 각각 제공합니다. 이 코드는
RMSD나 PoseBusters 자체를 실행하지 않습니다. 필수 검사 목록이 실제 고정된
PoseBusters 설정 전체와 일치하는지는 외부 연결 계층이 보장해야 합니다.
가짜/합성 관측을 입력하여 얻은 집계는 과학적 성능 증거가 아닙니다.

## 자원 관측

준비·엔진·평가의 겹치지 않는 벽시계 시간(초), 준비부터 평가까지 전체 시간을
기록할 수 있습니다. 미측정은 `null`이며 0으로 채우지 않습니다. 성공 실행만
제공하여 시간초과 실행 비용을 숨겨서는 안 됩니다.

RSS는 바이트 단위로 관측 방법과 `process` 또는 `process_tree_sampled` 범위를
함께 기록합니다. 샘플링 피크는 정확한 순간 최대값 또는 강제된 프로세스 트리
메모리 상한이 아닙니다. 이 모듈은 평균/P95나 신뢰구간을 아직 계산하지 않습니다.

## API와 소스 CLI

`BenchmarkProtocol`, `EngineSpec`, `OutcomeRecord`, `StageObservation`,
`ResourceObservation`으로 불변 관측을 만들고 `PublicPoseLedger.add()` 후
`to_json()`으로 내보냅니다. JSON 필드는 dataclass 필드와 같습니다.

CLI 입력은 `schema="public_pose_benchmark_submission_v1"`, `protocol`,
`records` 세 필드만 갖는 JSON 객체입니다. `protocol`은 위 protocol의 필드,
`records`는 관측 record 객체 배열입니다. JSON에서는 tuple 대신 배열을 씁니다.
protocol SHA는 API의 `protocol.sha256`로 계산하며 기록마다 일치해야 합니다.

```bash
python -I -S betelgeuze_product/public_pose_benchmark.py < submission.json > ledger.json
```

CLI는 stdin 최대 4 MiB, protocol 최대 10,000개 예정 실행, 필수 검사 최대 256개를
허용합니다. 중복 JSON 키, 미지원 schema, 예기치 않은 필드, 잘못된 숫자를
거부합니다. 잘못된 입력은 종료 코드 2와 일반화된 오류를 반환합니다.
stdout은 `public_pose_benchmark_v1` schema이며 입력 submission schema와 다릅니다.

## 검증 범위

소유 테스트는 합성 기록에 대한 분모·누락·실패·Top-1 결속·설정 불일치·JSON
검사입니다. 실분자 계산, 비교 엔진 실행, 상용 성능, 맹검 검증을 뜻하지 않습니다.
모든 출력의 `claim_promotion_allowed`는 `false`입니다.

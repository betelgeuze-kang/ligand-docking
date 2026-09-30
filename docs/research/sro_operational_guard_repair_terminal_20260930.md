# SRO 운영 수정 실험 — 종료 결과와 다음 개발 근거

고정된 네 개발 시작점의 CPU 실험은 `stopped`로 종료됐다. 계산 완료 2개, 첫 force 실패 1개,
미시작 1개이며 분모는 **4**다. 마지막 수락 상태를 사전 기준으로 평가한 회복 성공은 **0/4**다.
완료된 두 사례 모두 힘 수렴 기준을 넘었다. 전체 포괄 시간은 2418.245301483초다.
기존 실행은 재시작·재시도하지 않는다. 목표는 `active`, 과학·학습·HIP·서비스 상태는 `NOT_QUALIFIED`다.

[이전 진행 기록](sro_operational_guard_repair_20260930.md)은 첫 사례 완료 시점의 역사적 snapshot이다.
이번 결과가 이후 최종 상태다. 같은 시작점의 별도 운영 수정 실험이며 독립 평가 집합이나
이전 실패의 재개·예산 재설정이 아니다. 이전 실패 1·미시작 3은 별도로 보존한다.

| 사례 | 실행 결과 | force 시도 / 반환 / 오류 | 수치 endpoint 검산 | 최종 최대 원자 힘 | 최종 대칭 heavy RMSD | 사전 채택 |
|---|---|---:|---|---:|---:|---|
| 01 | 완료, objective 상한 소진 | 417 / 417 / 0 | 2/2 통과 | 0.47662518 | 1.298618 Å | 거부 |
| 02 | 완료, objective 상한 소진 | 417 / 417 / 0 | 1/2 통과, 초기 힘 실패 | 0.0015660185 | 1.516548 Å | 거부 |
| 03 | 첫 force applicability 실패 | 1 / 0 / 1 | 실행되지 않음 | 관측 없음 | 관측 없음 | 실패 |
| 04 | 정책에 따라 미시작 | 작업량 unknown | 실행되지 않음 | 관측 없음 | 관측 없음 | 미시작 |

힘 단위는 kcal/mol/Å, 기준은 원자 L2 **0.001**이다. 시작된 세 사례의 Force 합계는 **835 시도 = 834 반환 + 1 오류**,
score 정상 반환은 5개, graph 정상 반환은 835개다. 미시작 작업량을 0으로 추정하지 않는다.
Oracle은 시작·마지막 수락 상태 네 개를 평가해 세 개 통과·한 개 실패를 기록했다.
Endpoint 상태 수와 API 호출 수, 계산 완료와 채택, 점수 개선과 친화도를 구분한다.

## 수치 실패에서 확정된 것과 부족한 기록

02의 초기 에너지 오차는 5.064e-9 kcal/mol로 통과했지만 최대 힘 성분 오차는
**4.7613866627e-8 > 1e-8**로 실패했다. 마지막 상태의 힘 오차 2.035e-11은 통과했다.
초기 cross LJ는 96281.781 kcal/mol, 최소 cross 거리는 0.755529 Å, 심한 겹침은 16개였다.
급한 LJ 반발 영역에서 작은 수치 차이가 증폭됐다는 가설은 근거가 있지만 인과는 미확정이다.
단위 환산 소스는 차원적으로 일관된다. 작은 상대 오차를 이유로 절대 기준을 완화하지 않는다.
Oracle 힘 벡터·최대 오차 atom/axis·항별 힘 오차·변환 파라미터의 정확한 binary64 차이가 없어
원인을 확정할 수 없다. 향후 별도 prospective 진단에서 이 항목을 먼저 기록해야 한다.

03은 `ReferencePhysicsApplicabilityError`, 정상 force 반환 0, `evaluation_failed`다.
설치 minimization의 예외 처리에서 메시지와 발생 위치가 소실됐다. 같은 클래스가 topology,
angle/torsion, internal/cross 거리 등 여러 경계에서 발생하므로 특정 최소거리 위반으로 단정하지 않는다.
프로세스 exit 0은 실패 결과를 저장한 소프트웨어 종료이다. `known_completed_force_calls=1`은
실패한 종료 시도 하나이며 성공한 force 하나가 아니다. 역사적 결측은 그대로 남는다.

## 저장 결과의 완결과 평가 위상

원래 payload **947개·60,712,054 bytes**의 정확한 목록·크기·SHA를 종료 manifest로 봉인했다.
고정된 supervisor 소스의 저장 전용 exporter가 plan·검토·선행 실패·소스 역할·장부를 인증했다.
Rich export는 네 사례와 실패·unknown을 유지한다. Legacy export는 완료 2개만 표현하며
03은 인증된 endpoint 시작이 없어 생략, 04는 미시작 작업량 unknown으로 생략한다.
완료 두 개만으로 분모를 줄이지 않는다. 독립 읽기 전용 검토도 전체 947개 SHA를 확인했다.

최초 좌표 평가기는 actual receipt의 JSONL을 JSON으로 해석해 실패했다. 최초 실패 script와
도구 출력 전사 기록을 보존했다. 추가 adapter는 모든 원본 참조의 bytes·해시와 역할을 먼저
검증한 뒤 JSON-only 평가 입력을 별도로 만든다. 제외한 JSONL/log/source는 전체 검증 receipt에
남고 원래 export·packet·캠페인을 변경하지 않는다. 기존 evaluator의 전체 packet·사전 검토·
좌표·물리 게이트 검사를 그대로 실행한다.

참조 RMSD는 실험 종료 후의 별도 저장 좌표 계산이다. 이 위상에서만 평가 전용 참조와
원래 bound source를 packet 인증에 읽었다. Optimizer의 원본/reference/control 입력 금지는 유지한다.
기존 가드·예산·허용오차를 바꾸지 않았고 새 force·score·optimizer·OpenMM 관측도 만들지 않았다.
새 계산 없음의 근거는 pinned stdlib 저장 전용 소스와 Python 감사 hook 범위이며 전체 OS/native
계측으로 확대하지 않는다. 기존 절대 경로가 필요하므로 다른 위치의 재생 가능성을 주장하지 않는다.

## 실제로 다음 개발 가치가 큰 두 작업

1. **수치 실패 진단과 거부 기록 보강.** 새 버전에서 typed reason·발생 단계·안전한 메시지 또는
   원문 해시를 잃지 않고 실패·미시작 분모와 같은 계산 장부를 유지한다. 합성 오류 주입으로
   정보 보존을 검증하고, 별도 사전 계획의 항별 힘 진단으로 02의 불일치 위치를 찾는다.
   현재 frozen 결과를 다시 계산해 통과로 바꾸는 작업은 포함하지 않는다.
2. **실험 endpoint와 준비 상태의 증거 intake 계약.**
   [새 공개 전사 대응 기록](human_5ht6_2024_cross_artifact_reconciliation_20260930.md)은
   205 main·78 Ki summary·6 repeat·71 Table S1 행·89 이름 표시를 별도 분모로 연결한다.
   Local PR label 대응은 화학 identity나 독립 측정이 아니다. PR9 등 분쟁, NA/ND/NT와 다른
   endpoint를 보존하며 독립 측정 분모 null·신규 credit 0·모든 admission false다.
   Raw 반복/N, batch·microstate, construct/pH, 권리·source family와 별도 역할 결정의
   제공/미제공/미해결 상태를 소비할 계약이 다음 완료 조건이다.

목표 3의 의미 있는 후보 비교에는 수치 검증과 endpoint/source 역할 적격성이 모두 필요하다.
현재 자료로 AI 학습 효과·친화도·서비스 가능성·HIP 전환 적격을 선언하지 않는다.
목표 4에서는 01의 저장 검증 153.948초, 입력 parse 43.858초, scorer 구성 16.563초를 관측했다.
실행 중 대응 단계보다 각각 약 9.2배·10.1배지만 trace/profile 인과 기여는 미측정이다.
무결성을 유지한 준비 객체 재사용과 journal/fsync/checkpoint 비용 분해가 먼저이며 속도 향상은 아직 없다.
포괄 단계와 내부 시간을 더하지 않는다. Fresh-128과 300개 개발 자료의 구분을 유지한다.

## 개발 검증과 증거

이번 통합 검증: **199 passed, 2 skipped, 31 subtests passed in 5.00s**, 변경된 Python 5파일의 Ruff·diff 검사 및 공개 대응 CLI 통과.
소스·테스트 pin은 전후 같았다. 단위 테스트의 내부 분자 dispatch 수는 별도 계측하지 않았으므로
시험 통과를 zero dispatch나 과학 검증이라고 부르지 않는다. 이전 284 passed + 31 subtests는
53476bce의 운영 경계 검증이며 이번 시험 수에 합산하지 않는다. Hosted CI·설치·과학 증거는 별개다.
선택적 원문 PDF 시험 두 개는 이 실행에 공식 2024 PDF를 공급하지 않아 skip됐다.
이번 공개 대응 검사는 원문 source-byte 검증을 갱신하지 않는다.
넓게 잡은 최초 lint에서는 변경하지 않은 동결 protocol과 기존 test의 스타일 오류 58개가 남았다.
최초 실패 로그를 보존하며 해결됐다고 주장하지 않는다. 동작 검사와 과학 게이트를 그대로 유지하고
변경한 5파일의 lint 결과를 별도로 기록했다. 동결 source를 포맷해 packet SHA를 바꾸지 않았다.

전체 참조·해시·게이트·실패·비용은 [증거 JSON](../evidence/sro_operational_guard_repair_terminal_20260930_v1.json)에 있다.

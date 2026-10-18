# 리간드 도킹 개발 우선순위 — 2026-10-18

근거는 사용자가 지정한 ChatGPT 대화 `6aceb8de-f144-83e8-8a7e-e99220b448a4`
「리간드 도킹 개발평가」의 최신 평가다. 기준 main은
`feba36dc7cbc137a0177b2e45346a836dcae1e08`이다. 기존 dirty 체크아웃과
역사 실행은 보존하고 별도 작업 공간에서 진행한다.

| 순서 | 목표 | 완료에 필요한 증거 |
|---|---|---|
| P1 | 설치된 CLI에서 실제 준비 분자 한 작업 완주 | 다른 디렉터리의 설치 패키지로 입력 검사, 제한된 실제 계산, 알려진 중단/재개, 검증, 원래 상태와 정제 상태 비교 보고. 실패·미상 작업의 올바른 처리도 별도 검사 |
| P2 | 물 배향의 실제 추가 가치 | 같은 시작점·8DOF·모델·예산의 dry/wet 비교. RMSD, 구조·접촉, 비용, 마지막 동일 상태의 리간드/물 수렴을 구분 |
| P3 | 기존 고정 D1 32사례와 기준 도구 비교 | 국소 정제, 독립 재도킹, 후보 선별/순위를 구분. 유효 Top1/Top5, 단계별 손실, 퇴행, 모든 실패, 전체 시간·메모리 |
| P4 | 에이전트 실험 생명주기 | 기존 공통 API의 계획/실행/상태/취소·재개/검증/비교/보고. 실행ID, 중복 방지, 총예산, 모델과 힘의 종류·단위, 실패 코드·위치 |
| P5 | Linux CPU 사용자 파일럿 | 동일 엔진·입력·예산의 기존 방식 대비 개입시간, 실패 처리, 복구·재현, 근거가 연결된 보고 |

Fresh-128·Stage0는 독립 평가로 보존한다. 개발 결과를 보고 기준·분모를
바꾸거나, 실행 완료·에너지 감소·설치 성공을 과학적 검증이나 고객 승인으로
승격하지 않는다. 실패·UNKNOWN·NOT_QUALIFIED와 과거 소스 식별값을 유지한다.

## P1의 작은 통합 경로

`betelgeuze-dock prepared-refine`는 기존
`cpu_refinement_fourier_v1.workflow`의 수치·저널·체크포인트 코드를 호출한다.
기존 fixed64 합성 `dock/verify/report` 계약은 별도다. 준비·양성자화·포켓 탐색을
추가하지 않으며, 이미 준비된 단일 리간드와 고정 수용체 모델만 받는다.

```bash
betelgeuze-dock prepared-refine preflight \
  --protocol /absolute/protocol.json --expected-protocol-sha256 SHA256 \
  --output /absolute/preflight.json
betelgeuze-dock prepared-refine run \
  --protocol /absolute/protocol.json --expected-protocol-sha256 SHA256 \
  --run-dir /absolute/new-run --pause-after-accepted-iterations 1 \
  --output /absolute/paused.json
betelgeuze-dock prepared-refine verify \
  --protocol /absolute/protocol.json --expected-protocol-sha256 SHA256 \
  --run-dir /absolute/new-run --output /absolute/verification.json
betelgeuze-dock prepared-refine resume \
  --protocol /absolute/protocol.json --expected-protocol-sha256 SHA256 \
  --run-dir /absolute/new-run --output /absolute/completion.json
betelgeuze-dock prepared-refine report \
  --protocol /absolute/protocol.json --expected-protocol-sha256 SHA256 \
  --run-dir /absolute/new-run --output /absolute/report.json
```

프로토콜은 기존 `prepared_fourier_development_protocol/1.0.0`이다.
모든 출력은 기존 디렉터리의 새 파일이어야 하고 실행 디렉터리 밖에 둔다.
덮어쓰기 옵션은 없다. 출력 부모 디렉터리도 계산 전에 descriptor로 검사한다.
실행 전에 프로토콜과 모든 bound 입력을 검사한다. Linux의 기존 hardened
writer를 사용하며, 알려진 체크포인트만 재개한다. 미완료 intent는
`interrupted_unknown`으로 남고 자동 재실행하지 않는다.

기존 프로파일의 1 CPU, 최대 4 iterations·3 backtracks를 유지한다.
optimizer objective 상한은 17, B0는 별도 1이다. 알려진 재개는 각각 힘 평가
1회를 추가하며, 가능한 최대 4번 재개까지 포함한 상한은 22다.
단 한 번 재개하는 파일럿은 최대 19회다. 실제 비용은 각 invocation의 work에서
합산한다. 미상 intent가 있으면 총비용은 `null`이며 알려진 비용만 따로 제시한다.
CLI 자체는 wall-clock 제한을 시행하지 않으므로 실제 계산은 외부의 유한
감독기 아래 실행한다. 합성 검사 비용과 실제 분자 비용은 합치지 않는다.

`prepared_refinement_report/1.0.0`은 원래 B0와 마지막 관측 B3를 비교한다.
실패 후의 마지막 checkpoint를 성공한 최종 포즈로 부르지 않는다.
실행상태, 수치수렴, 기록 일관성, 화학적 타당성(`null`), 포즈 정확도(`null`),
포즈 채택(`false`)은 각각 별도다. 힘은 무구속 Fourier 모델의 원시 음의 좌표
미분이며, kcal/mol/angstrom 단위를 명시한다. verify/report의 새 E/F는 0이다.
시간은 저장된 수치 invocation 범위이며 설치·준비·보고의 전체 시간과 다르다.

새 standalone CLI 소스도 기존 수치 source manifest에 들어간다. 따라서 기존
실행의 현재 코드 재검증은 source drift로 거절될 수 있다. 과거 실행은
이관·재봉인하지 않고 새 설치 패키지의 결과를 별도로 남긴다.

현재 P1의 제한된 설치·실제 입력 완주 결과는
[실행 기록](docking_priority_p1_installed_20261018.ko.md)에 정리했다.
수치 수렴은 미달이며 P2~P5와 고객·과학 승인은 미완료다.

## 다음 단계의 현재 입력 요건

P2 최종 물 상태는 외부 보존 자료다. 보고서 숫자로 좌표를 재구성하거나
과거 미수렴 상태로 대체하지 않는다. 정확한 원시 코드·좌표·저널을 확보하고
현재 정책과 비교한 뒤 유한 실행계획을 고정한다.

- summary: `water-global-fixed-chart-return-optimizer-preflight-20261017/runs/optimization/summary.json`
- summary SHA256: `1dcc05e38be87e995175d3360c3cd7a56a63460080a8a9bd9cc76a3fe53b217a`
- final observation SHA256: `67cbbfd7571c1bf84020ad3bfbaae5f2b6a17805b9671332572fb2e531b6b6a6`
- final state SHA256: `0900979def2185c3d3713976042bff37ef7ed7d678f7130adb20ce6b9f79a156`
- terminal audit SHA256: `5baad329e7bd3704ce713ccc6469e3e98648382722c261385778cbe65a5d03b4`

P3의 기존 D1 프로토콜은 실제 licensed/private 32입력과 연결해야 한다.
로컬 Vina/GNINA 이름의 wrapper만으로 실행기 설치가 확인된 것은 아니다.
현재 발견된 wrapper의 대상 runtime은 없다. 실행기·모델·버전·입력 출처를
먼저 확보한다. 기존 D1 materializer의 ligand Kabsch aligned RMSD는
분자 형상 지표이며 수용체 좌표계 도킹 RMSD로 바꾸어 부르지 않는다.
실제 포즈 회복 평가는 수용체 좌표계와 대칭 매핑 정책을 사전 고정해야 한다.

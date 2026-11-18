# #624 6YSP 정확 재현 실패 재확인

2026-11-18 KST. [PR #624](https://github.com/betelgeuze-kang/ligand-docking/pull/624)의 원래 실패 실행과 별도 두 호스트 진단을 저장 산출물로 대조했다. 신규 분자 계산은 없다.

원본 파이프라인 3모드, 추가 두 호스트의 각 3모드를 합쳐 총 9개 작업자 관측이다. 고정 64후보를 가진 같은 한 사례의 반복이며 독립 사례 9건이 아니다. Top-5 SDF 바이트는 9/9에서 과거 값과 같았다. 원래 시간·명령·실행 정책 제외 규칙을 적용한 뒤에도 모든 작업자에서 **같은 1,738개 값이 불일치**했다. 차이는 후보 진단 아래에 있었고 좌표 지문 61개, 후보 점수 51개가 달랐다. 후보 점수 최대 절대 차이는 약 1.15e-9였다. [구조화된 감사 결과](624-exact-replay.json)

집계기의 `case mode order/process gate` 오류는 작업자 실패의 후속 결과다. 작업자는 `fresh pipeline historical scientific row` 정확 비교에서 먼저 실패했다. 역사 기록과 현재의 Python 런타임 기록, 패키지 목록, wheel, 평가기 payload는 일치했다. 소스 파일 목록과 전체 환경 결속은 다르다. 이전 좌표 감사에서는 첫 차이가 후보 생성 직후부터 확인됐다. 어느 계산이나 호스트 조건이 최초 차이를 만들었는지는 여전히 UNKNOWN이다.

원래 과학 비교를 변경하지 않았다. 이 파이프라인의 내역을 정확히 재현했다고 판정하려면 최초 차이를 분리한 후 원래 비교 조건을 통과해야 한다. 기존 Top-5 일치를 별도 관측으로 보존한다.

- [실패한 통합 실행](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41798394302)
- [두 호스트 진단](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41832112034)

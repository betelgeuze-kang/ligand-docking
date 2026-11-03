# P1: 제품 CLI 계층 수정 후 설치·실제 입력 검증 — 2026-10-18

현재 제품 패키지의 `betelgeuze-dock` 진입점은
`betelgeuze_product.docking_cli:main`이다. 준비 분자 정제·비교 보고를 여기서
연결하고, 기존 명령은 독립 엔진 CLI에 위임한다. 독립 엔진 wheel의 진입점은
`betelgeuze_engine_v2.standalone_cli:main`을 유지한다. 엔진 소스는 기준 main과
동일하며 architecture guard·고정 source golden을 완화하지 않았다.

최초 구현의 엔진→제품 import는 hosted CI가 거절했다. 당시
[15c01c8bd 실행 기록](docking_priority_p1_installed_20261018.ko.md)은 보존했다.
아래는 수정 패키지로 새 환경·새 실행 디렉터리에서 얻은 별도 결과다.

## 현재 코드와 설치 확인

- 실행 코드 commit: `6ea1275a2e66afce7a43fbf8aae97e9dc8332bb6`
- wheel SHA256: `8fc912675b8b457dc4fad1db74c986b2f581bd8ab5e578d42ad619c101f3abb6`
- Python 3.10.12 / Torch 2.6.0+cpu / 새 venv, system-site-packages 미사용
- root product 의존성 설치 및 `pip check` 통과. 이 경로에 불필요한 선택적
  RDKit은 설치하지 않았다.
- 패키지 538파일의 source/wheel/설치 바이트 일치. 설치 RECORD 1,090행의
  유일성·위치 확인, 해시가 있는 553행의 해시·크기 확인.
- 저장소 밖의 Python `-I`에서 프로젝트 import 경로·console entrypoint를 확인.
  `tools`/`tests` 모듈은 없으며 로드된 프로젝트 모듈은 새 설치 안에 있다.
- 수치 checkpoint 결박과 제품 wrapper 결박은 구분한다. 전체 wheel 바이트·진입점
  확인과 보고서의 wrapper/helper/engine 소스 해시를 함께 사용한다.

## 실제 준비 입력 한 사례

SRO 리간드 26원자, 고정 수용체 4,376원자에 기존 Fourier 프로파일을 적용했다.
원래 입력과 모델·시작 좌표를 바꾸지 않고 최대 4단계·3 backtracks·동일 힘 기준을
사용했다. 과거 실행을 재개하거나 영수증을 현재 코드로 재봉인하지 않았다.

입력 검사 → B0 → B3 1단계 후 알려진 체크포인트 → 검증·보고 → 한 번 재개 →
검증·보고 → 완료 결과 재조회를 새 설치 CLI에서 완료했다.

| 항목 | B0 | 마지막 관측 B3 |
|---|---:|---:|
| 모델 전체 에너지 (kcal/mol) | 14.798201989215876 | -6.265237047193981 |
| 원시 최대 원자힘 (kcal/mol/Å) | 128.4364735627077 | 19.902898756321665 |

- 실행 `complete`, 수치 상태 `max_iterations_reached`, **수렴 미달**.
  기준은 변경하지 않은 0.001 kcal/mol/Å이다.
- 힘 평가 **8회** = B0 1 + 첫 invocation 2 + 재개 invocation 5.
  optimizer 관측은 initial 1 + accepted 4 + rejected Armijo 1이며 재개 확인 1회가
  별도 포함된다. 실패 호출 0, 미상 작업 0, 단 한 번 재개의 상한 19회 이내다.
- 외부 감독 한도: wall 600초·CPU affinity 1·자식 주소 공간 6GiB·파일당 및 총
  출력 512MiB. 감독기 wall 94.964061683초, 자식 최고 RSS 491,212,800bytes,
  수치 invocation 내부 wall 합계 16.576030350초. 이 시간들의 범위는 다르며
  설치 비용이나 성능 개선 비교를 나타내지 않는다.
- 자식 10단계 모두 exit 0. 고유 원본 10개 파일의 실행 전후 바이트 동일.
  검증·보고·완료 재조회 전후 journal과 보존 work 동일, 추가 E/F 0.
- 초기 15c01c8bd와 수정 6ea1275a2 검증은 **같은 한 분자 입력의 두 패키지
  검증**이다. 각 8회, 두 실제 실행 합계 16회의 비용을 보존한다. 두 독립 분자나
  독립 도킹 정확도 실험으로 세지 않는다. 합성 검사 비용도 별도다.
- 좌표·에너지·힘 결과가 초기 패키지와 일치하지만, 서로 다른 소스 결박과
  checkpoint 해시는 그대로 유지한다. 그 일치를 과학적 일반화로 확대하지 않는다.

에너지 감소는 포즈 정확도나 친화도 개선의 증거가 아니다. 화학적 타당성·RMSD는
미평가 `null`, 포즈 채택은 `false`다. 출처·과학·원래 Hamiltonian·학습·제품 순위
승인은 모두 `false`, 독립 측정 분모는 `null`을 유지한다. 이번 실제 실행은
알려진 pause/restart를 검사했으며, 실제 강제 중단·실패는 실행하지 않았다.
미상 작업 및 실패 경계는 합성 검사로 검증했다.

## 보존된 증거

로컬 묶음은 `engine-v2-priority-cli-corrected-20261018-glZ3Lo`, 실제 실행은
`installed-p1-real26-3kp17t7a`다. 아래는 외부 보존 파일의 바이트 SHA256이며
저장소 안의 파일 링크나 공개 다운로드 주소가 아니다.

| 파일 | SHA256 |
|---|---|
| `protocol.json` | `e7dc3ba4f32f22319db05aa2e155865ee73f3eb6834bc09dbaf59c21dd0e67a6` |
| `plan-before-force.json` | `6404a0d3b8e9b54bd0063c384de0f3e9d84ffefe1962800d492972f139fd46d6` |
| `supervisor-result.json` | `8a411384284d447186c432598844aaffa5d1f9b9efcb098cef1b1c018b4aeb11` |
| `07-final-report.json` | `8cb0feb071621349299c5c9f7eb8ead628ee62c4f48cc010f67dd0cc67fd1089` |
| `completed-resume-zero-force.json` | `da0fe0883f8a824dc7eb69a9e6bbc36b6fcd372c0a4a0d43d0d832cba4fd1d19` |

수정 후 로컬 bridge·source 경계·패키징 경계·기존 standalone 검사 50개가
통과했다. architecture guard, 고정 engine source manifest, lint, 설치된 합성
pause/restart/미상 작업 보존/입력 변조 거절/보고 검사도 통과했다.
6ea1275a2의 독립 wheel hosted 검사 3.10/3.11/3.12는 통과했으며, 다른 hosted
검사와 최종 PR head의 상태는 해당 SHA에 맞춰 별도 확인해야 한다.

P1의 제한된 설치·실제 입력 경로를 확인한 결과이며, P2~P5의 물 비교·개발세트
성능·전체 에이전트 생명주기·사용자 효익 검증을 대신하지 않는다.

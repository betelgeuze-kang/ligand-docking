# 추가 보강 작업: 실행 환경 중단 시점의 검증 기록

기록 시각: 2026-11-12 UTC / 2026-11-13 KST.

## 이 브랜치에 실제로 포함된 것

이 브랜치는 이전 draft PR #625의 head
`bb2cdf712e64c78e726122d85afd433f8061856c`를 기반으로 한다.
**새 API body-replay/disconnect 수정, 그 전용 테스트/CI, 이 기록만 원격 반영했다.**
아래 준비 화학, reader 자원 제한, 패키징, 평가 체계의 대규모 변경을
이 브랜치에 이미 포함한 것으로 해석하면 안 된다.

클라우드 실행 환경이 작업 중 `unavailable`로 전환됐다.
`exec-server transport closed` 이후 확인 명령도
`No usable execution environment is available`로 거절됐다.
추가 코드의 최종 통합 테스트, wheel 재생성, 실제 분자 paired 평가,
전체 코드 원격 반영은 완료하지 못했다. 이는 승인 거절이 아니라 실행 환경 장애다.
파일이 영구적으로 소실됐는지는 확인되지 않았으며, 복구 시 기존 worktree를
먼저 회수해야 한다.

## 원격에 보존한 독립 수정

### PR #625의 CI 소유권 수정

제품의 준비 화학 테스트가 `test_engine_v2_*.py` glob에 포함되면서
RDKit이 없는 엔진 전용 CI에서 22개가 실패했다.
테스트를 `test_product_receptor_preparation_v1.py`로 100% 동일하게 이동하고,
준비 기능 전용 CI의 세 경로를 갱신했다. RDKit pin, assertion,
zero-skip 조건은 유지했다. 새 위치에서 31 passed를 실제 관측했다.

수정 commit:
`bb2cdf712e64c78e726122d85afd433f8061856c`.
2026-11-12 15:34:29 UTC 조회 기준 23개 workflow 중 21 success,
main/top-stack 두 개는 실행 중이었다. 이 시점에 전체 CI 성공을 주장하지 않는다.

### 이 브랜치의 API 스트리밍 수정

`api/security.py`의 body buffer 소진 후 `replay_receive()`가
await 없이 빈 `http.request`를 계속 생성했다. 이 때문에 실제 disconnect가
전달되지 않고, streaming listener가 event loop를 점유할 수 있었다.

소진 후 `await limited_receive()`로 돌아가도록 좁게 수정했다.
원래 채널의 대기/연결 종료와 기존 바이트 누적 검사를 유지한다.
세 회귀 테스트가 다음을 확인하도록 작성됐다.

- 여러 body chunk가 정확히 한 번 재생된 뒤 원래 disconnect가 전달되는가.
- body 소진 후 receive가 실제 채널을 기다리는가.
- replay 이후 추가 body도 기존 payload 제한으로 차단되는가.

같은 생산 코드 수정은 중단 전에 reader 작업 브랜치에서 기존 API/security
회귀와 함께 실행됐다. 다만 **이 새 테스트 파일과 원격 tree는
로컬에서 재실행하지 못했다.** 새 `ci-api-disconnect`의 실제 결과를 별도로 확인해야 한다.

## 원격 미반영 작업과 관측된 검증

각 행의 테스트 수는 서로 다른 코드 시점/부분집합이다. 중복을 합쳐
통합 테스트 총수로 표시하면 안 된다. 원시 로그/산출물은 중단된 환경에
있고, 이 기록은 세션 중 관측한 결과의 checkpoint다.

| 영역 | 작성/관측된 내용 | 정확한 완료 경계 |
| --- | --- | --- |
| 수용체 준비 V2 | 원본 SHA에 결속한 화학 상태, peptide 링크, OXT, H 보완, CCD component graph, 원본 원자/좌표 보존 | combined 74 passed, 0 skip을 관측. 이후 H-H overlap과 aromatic source-bond guard 두 개를 추가했고 그 최종 상태는 재실행하지 못함. 아직 commit/원격 반영 전 |
| 실제 6T88 준비 | 원본 7,052 원자 모두 보존, 7,109 원자로 준비 성공. H 56개와 OXT 1개 추가, 삭제 0. formal/partial total +6 | 한 실제 입력의 명시된 개발 모델 준비 성공. 최종 후속 archive script 종료는 미확인. 생물학적 상태/정확도/force-field 검증 아님 |
| 파라미터 authority | 선언된 수치 자료의 SHA, typed parameter fingerprint, topology, 원자/결합/각도 coverage, charge 및 cross-state 검증 | 실제 force-field 자동 부여나 생물학적 타당성 증명은 구현하지 않음. 올바른 실분자 parameter 자료가 없으면 차단 |
| Reader 자원 제한 | SQLite 공유 admission, global/tenant 슬롯, 요청 전체 wall/CPU/AS/spool 제한, 고정 outer worker, HTTP/CLI 전달까지 lease 유지 | 261 passed를 관측. 별도 설치 wheel의 queue-only 32-reference read smoke 통과. 두 cleanup/timeout 경계 보완은 아래 재개 과제 |
| 패키징 | 제품/엔진 파일·console 단일 소유, 제품 CLI 분리, 새 dev 버전, 실제 pip 공존/업그레이드/삭제 검사 | 124 passed, 0 skip 관측. 양방향 설치/재설치/제거와 구제품 업그레이드 손상→복구 재현 통과. 통합본 wheel은 아직 만들지 못함 |
| 배포 preflight | RECORD hash/누락, console owner, dependency, CPU tensor와 RDKit probe | 별도 설치 환경의 CPU/RDKit probe 통과. Docker/ROCm 실장비 실행은 없으며 qualification false 유지 |
| Paired 평가 | 입력/seed/source manifest, 예측과 native 평가 subprocess 분리, 실패 포함 고정 분모, Wilson 및 보수적 paired CI, 단계별 RMSD, PoseBusters 0.3.1 | 새 평가 테스트 13 passed를 관측. 이후 wait4 자원 수집 변경의 실제 worker 통합 테스트 1 passed. 실분자 paired pilot은 아직 미실행. isotope RMSD 결함 추가 발견 |
| 후보 다양성 | 점수/유효성 통과 후보에 수용체 좌표계 heavy-atom RMSD 기준의 선택 옵션, 기본 동작 유지 | 10 passed 관측. 정확도 향상은 미측정 |
| Holdout 구성 | 원본 428건과 논문 308건 membership 해시 검증, 개발 300건과 대조 | 기존 complement 128건 중 120건이 논문 308건 밖임을 실제 계산. 남은 8건도 exposure/sequence/scaffold 검증 전에는 fresh holdout 자격 없음 |

### 6T88에서 확인한 실제 화학 문제

HIS 15개의 ring H 이름만 보면 HID 5개/HIE 10개처럼 보였지만 원본
formal charge는 모두 +1이었다. H 패턴만으로 중성 상태를 선택하면
원본 charge와 충돌한다. 개발용 spec은 명시적으로 HIP와 부족한 H 보완을
선택하고 그 가정을 기록했다. 임의의 pH 예측 결과로 취급하지 않았다.

ARG 17개의 원본 NH2 +1을 보존하는 명시적 resonance 선택이 필요했다.
FAD의 공식 CCD aromatic flag와 RDKit perception 차이도 명시적인 정책과
차이 기록으로 처리했다. FAD, GOL 8개, Na 1개, Cl 3개를 제거하지 않았다.

RDKit sequence template의 ILE named mapping에서 CG1/CG2와 CD1 연결이
실제 PDB 이름에 맞지 않는 문제를 찾았다. V2에서 공식 ILE CCD와 대조해
교정했으며, 20종 amino-acid named heavy adjacency를 CCD와 대조했다.
기존 v1은 이 경우 geometry 검사로 거절하므로 잘못된 결합으로 조용히
진행하지 않는다는 regression도 관측했다.

이는 전체 준비 커버리지나 생리적 protonation, affinity calibration,
상용 수준의 pose recovery를 증명하지 않는다.

## 재개 시 가장 먼저 수정/검증할 사항

1. **RMSD 원자 대응 오류.** `Chem.RemoveHs`는 동위원소 H 등을 남길 수 있다.
   현재 신규 evaluator는 query index와 dense heavy-atom ordinal이 같다고
   가정한다. 동일한 `[2H]OC` SDF를 입력/정답으로 주어도
   1.4142135623730951 Å가 나오는 오류를 실제 재현했다.
   원본 atom-index provenance와 제거 후 query-heavy index를 분리해
   `mapping[query_heavy_index]`로 대응시켜야 한다.
   이 수정의 apply_patch는 실행 환경 장애로 시작하지 못했다.
2. **Paired worker 자체 wall timer.** 부모 watchdog만으로는 부모 사망 뒤
   I/O 대기 중인 worker의 wall 상한을 보장하지 못한다.
   worker 진입 즉시 상한 timer를 설정하고, 검증된 요청의 절대 deadline으로
   좁혀야 한다. 부모 crash 뒤 실제 자동 종료 테스트가 필요하다.
   코드 검토로 확인한 항목이며 새 native 재현 명령은 환경 장애로 실행되지 않았다.
   timeout 후 무기한 wait4/process.wait cleanup도 상한/보장 범위를 보완한다.
3. **Reader spool cleanup 예외.** worker reaping과 TemporaryFile close 이후
   빈 임시 디렉터리 삭제 실패만으로 lease가 계속 남지 않게 한다.
   handle closure가 확인된 경우 lease.close를 finally에서 실행하고,
   미확정 자원 소유는 fail-closed 유지한다.
4. **HTTP 첫 header 전송 중 timeout 경계.** 최초 send가 timeout되면
   header 일부가 이미 전송됐는지 확정할 수 없다. send 직전에
   headers_attempted를 표시하고, 전송 시도 이후 두 번째 response.start를
   보내지 않는다. pre-send typed504와 전송 중 abort를 문서/테스트로 구분한다.
5. 준비 V2 마지막 두 guard와 모든 신규 회귀를 재실행하고 6T88 결과를
   최종 source/spec에 다시 결속한다. 변경된 소스로 기존 결과를 재봉인하지 않는다.
6. 패키지·reader·화학·평가 통합 회귀, 최종 product/engine wheel 설치,
   실제 paired development pilot, 원격 CI를 수행한다.
7. 실제 물리 parameter authority, 충분한 독립 holdout, 대표 규모 부하 및
   실제 지원 Docker/ROCm 호스트 증거가 확보되기 전에는 과학/배포 flags를
   true로 올리지 않는다.

## 복구할 worktree 및 commit 단서

작업은 새 클라우드 worktree에서만 수행됐다. main과 사용자의 로컬 PC를
변경하지 않았다. 임시 환경이 다시 사용 가능해지면 다음 상태를 먼저
확인하고, 접근이 끊겼다는 이유로 이 디렉터리를 재생성/삭제하지 않는다.

| Worktree basename / branch | 로컬 상태 |
| --- | --- |
| ligand_docking_next_20261113 / codex/priority-hardening-20261113 | 마지막 확인 HEAD 43ab7132. 208530c7(평가/holdout/diversity), b6872056(wait4/CI), 44b09d30(reader 통합), 43ab7132(packaging 통합) |
| reader_limits_20261113 / codex/reader-budgets-20261113 | 803db423773a85aa5be695083d08fd83ac8572c0 |
| package_hardening_20261113 / codex/package-ownership-20261113 | 7117147c(CI rename), 69eb9240(packaging). 후속 stale test 조사 중 |
| chemistry_support_20261113 / codex/chemistry-support-20261113 | 새 4개 구현 모듈, 2개 테스트, CCD fixtures, 문서가 미커밋. archive 실행 session 98081 종료 미확인 |

원격 API는 로컬 통합 commit 43ab7132를 찾지 못했다.
이 표의 로컬 SHA를 GitHub에 이미 올라간 commit으로 링크하면 안 된다.

부분 검증 wheel 해시(통합 배포물 아님):

- Reader: `3ce9fe9147c56de10cf687417835d14f5e9678f44e6854eb6a053cf5c93f9648`
- Product packaging: `a462d4e27f5956796af92f9f1cb24149931685cbb4226fe8f7b9f16c0af05ebd`

## 데이터 출처와 판정 한계

PoseBusters 원본 archive SHA-256:
`495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c`.

논문 308 identifier SHA-256:
`a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6`.

공식 source record는 428건과 peer-review 후 308건을 구분하며,
일부 구조의 crystal contacts를 설명한다:
https://zenodo.org/records/8278563

CCD 의미 및 component source:
https://www.wwpdb.org/data/ccd
https://www.rcsb.org/ligand/FAD

RDKit 수소 제거의 예외:
https://www.rdkit.org/docs/source/rdkit.Chem.rdmolops.html

**현재 판정:** 실제 입력 준비와 제품 운영 안정성에서 구체적인 진전이
관측됐지만, 추가 코드의 완전한 원격 반영·통합 검증과 실제 분자 정확도
평가는 미완료다. 개발 완료율이나 상용 도킹 소프트웨어 대비 정확도 비율을
새로 산출할 근거는 없다.

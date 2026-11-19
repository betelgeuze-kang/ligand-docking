# 독립 입력 준비 진단과 32TH conformer 생성

PR #629는 재생 증거가 있을 때만 검증 완료를 표시하도록 수정했다. 전체 CI 33개와 필수 검사 20개가 통과했고 리뷰 지적을 해결한 뒤 squash 병합했다. 병합 커밋과 검사 대상 HEAD의 파일 트리가 일치한다. [PR #629](https://github.com/betelgeuze-kang/ligand-docking/pull/629)

## 9SZ4

동일 원자·좌표·연결의 입력 두 개를 설치된 Amber `bondtype -j full` 및 `atomtype -p bcc`에 넣었다. 대조 입력의 CCD 방향족 표기 21개만 달랐다. 두 조건의 결합형 및 BCC 원자형 출력은 바이트 단위로 같았고, 원본 조건은 과거 출력도 재현했다. 두 조건 모두 BCC 결합 67/68 지원에서 멈췄다. 추적기의 한글 경로 이스케이프 때문에 먼저 끝난 호출이 사후 검증에서 거절됐으며, 경로 디코딩을 수정해 완료 출력을 재사용했다. 합계 네 호출이 정상 종료·회수됐다. QM 및 E/F는 각각 0회였다.

CCD C30–N31을 포함한 한 5원 고리의 네 방향족 표기가 Amber에서 단일 또는 이중결합으로 다시 분류됐다. 고정 그래프에서 원자별 이중결합 수를 만족하는 배치 두 가지 모두 C30–N31이 이중결합이었다. 이 계산은 그래프 열거이며 두 배치 각각의 Amber 실행 결과는 미측정이다. 현재 설치·준비 경로의 9SZ4 준비 실패를 유지한다.

## 32TH–A1KFC

공개 메타데이터 고정 명단 10건 중 기존 축 규칙을 통과한 1건을 추가 준비 입력으로 선정했다. 축은 C07–C08이다. 기존 목록과 대조했으며 더 넓은 과거 개발 이력의 독립성은 UNKNOWN이다. 수용체에서 대체 위치가 있는 잔기 6개와 미관측 선언 21개 잔기·28개 원자가 확인됐다. 수용체 및 비고분자 성분 처리 판정과 BCC 지원은 미확인이다. [32TH](https://www.rcsb.org/structure/32TH) · [A1KFC CCD](https://files.rcsb.org/ligands/download/A1KFC.cif)

CCD 그래프를 사용한 RDKit 2026.03.6 ETKDGv3 1회 실행에서 시드 2026110815, 한 스레드로 네 conformer를 생성했다. 38원자·23중원자의 좌표가 모두 유한하고 conformer 네 좌표 배열이 서로 다름을 저장 증거에서 확인했다. 실험 구조의 좌표는 생성 작업에 전달하지 않았다. 프로세스 종료 코드 0, 감독자의 정리 완료, 약 0.84초이며 엔진 E/F와 OpenMM Context는 0회다. 이 conformer는 포켓 배치 전 리간드 좌표다. 힘장 매개변수, 완성된 엔진 입력, RMSD·구조검사·D3·최종 선택은 미검증이다.

저장 증거 검증 네 항목을 일반 모드와 `-O`에서 각각 통과했다. 제품 전체 테스트 및 새 도킹은 미실행이다. 다음 작업은 32TH의 리간드 BCC 사전 범위와 수용체 누락·대체 위치 정책을 각각 확정하는 것이다. production HOLD, THRB HOLD, 기존 17 UNKNOWN, 실제32·공식 verify·고정100 미실행을 유지한다.

## 원본 증거 SHA256

- `9sz4/RESULT.json` `b9715fa441561b3fc3bd9a8d49f752b77063ffb018992ec82c662ce85e733c07`
- `9sz4/BOND-ATRIBUTION.json` `6e396355d80a9f1dadf12e64c06a6c801bb3ad44f37cd404f7ea9648caf7f839`
- `32th/RESULT.json` `041f9c5c47853d6b80014a011f9653e04ea568eaba9a5e4bab96f5db044efa8f`
- `32th/SOURCE-READINESS.json` `611c6b4d7a58b0780d42c191664aebd03c4501eb42c46e3f7e64738510ae9f6a`
- `32th/conformer-preparation/executed-once/generated-conformers.json` `8d9e5e1fcab53d05bc9f0da4e5bf1aaee79aa0e10593f5e2cb9d6a86ac9387e1`
- `32th/conformer-preparation/executed-once/supervisor.json` `ac2f1506a3b3858379f9b3247c2e9ab0dcad67cf56eb970ea92a9db0a71b97c3`

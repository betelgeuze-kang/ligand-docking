# METTL3/METTL14 9G4S/A1III 준비 결정 명세

`decision_manifest.v1.json`은 **미결 결정과 입력 요구사항을 기록한 개발 문서**다.
상태는 `DECISIONS_UNRESOLVED_EXECUTION_BLOCKED`이며 준비·수치 비교·실험 비교·학습·제품 실행 적격성은 모두 false다.
구조 준비 파일, 실행 요청, 데이터 입학 허가 또는 과학적 검증 결과로 사용할 수 없다.

이 문서는 통합 소스 `3ad331560c29a3e158aa28de95f3d871e11be119`를 기준으로 작성했다.
기존 source screen과 9G4S preflight의 불변 영수증, 공식 좌표와 메타데이터 등 19개 파일을 SHA-256으로 참조한다.
큰 원자료를 저장소에 복사하거나 기존 영수증·보호 문맥·역할을 변경하지 않는다.
로컬 위치는 `source_bundle_locations`의 힌트이며, 검증 시 루트 경로를 명시적으로 바꿀 수 있다.

## 현재 관측과 미결 사항

선택 인스턴스는 9G4S, model 1, label asym C, CCD A1III, **atom-site auth_seq_id 601**이다.
scheme의 auth_seq_num 600과 혼동하지 않는다. 기존 600 요청 실패는 원본 영수증에 남아 있다.
CCD stereo InChIKey와 ChEMBL SPA 활동 ID의 연결은 화합물 정체성 관측이다.
실험 측정값과 assay construct/미시상태의 일치를 뜻하지 않는다.

기존 preflight의 미결 사항 9개를 원래 ID 그대로 보존하고 다음 4개를 추가 기록했다.
모든 결정은 `unresolved`, `selected_action=null`, `resolution_evidence=[]`다.

| 범위 | 미결 내용 |
| --- | --- |
| 준비 입력 | construct 범위·미관측 26잔기·말단, B273 서열 충돌, 수소, 미시상태·전하·파라미터, 근접 물, Ca/TRS·altloc, 준비 PDB/SDF/GRO/ITP 파일 |
| 실험 연결 | Active Motif SPA construct와 Sf21 결정 construct, 인쇄 화합물 번호 충돌 |
| 추가 결정 | 출처·용도별 권리, 독립 source-component 역할, SPA 엔드포인트·활성 정의, 사전 고정된 수치 비교 계획 |

관측 좌표를 임의로 수선하거나 원자·물·금속을 지워 reader에 맞추지 않는다.
수소나 전하·토폴로지를 생성하지 않았으며 각 준비 파일·상태 선언·평가 파라미터 슬롯은 null이다.
관측의 무거운 원자 수 34, 리간드 수소 누락 34, 단백질 수소 0, 물리 평가 0을 그대로 기록한다.

## 기존 인터페이스로 연결되는 지점

실제 준비가 별도로 해결된 후에 사용할 입력은 `prepared_gromacs_components_v3`다.
`betelgeuze_engine.product.prepared_gromacs_input.load_prepared_gromacs_components`는 해시 결합된 준비 파일을 읽는다.
이 reader의 `prepared_state_id` 등 선언 문자열은 화학 준비나 assay-state의 독립 증명이 아니다.

이후의 개발 경로는 `tools.product.score_prepared_cross_interactions`와
`tools.product.verify_prepared_cross_numerics`다. 현재 이 문서가 실행을 승인하거나 요청하지는 않는다.
독립 스칼라 검사의 성공은 같은 좌표와 명시된 모델의 산술 일치를 뜻한다.
친화도·force-field 정확도·실험 활성·순위 품질·AI 우위는 별도 근거가 필요하다.
한 구조는 후보 간 순위 대비를 제공하지 않는다.

EP652의 SPA는 `IC50` / `enzyme_inhibition_IC50` 범위다.
현재 설치형 native-v4의 `receptor_radioligand_binding_Ki` 계약에 넣거나 그 게이트를 완화하지 않는다.
`synthetic_constants`를 실제 자료의 대체 입학 경로로 사용하지 않는다.
향후 실험 비교에서도 같은 DOI/연결 성분을 여러 역할로 나누지 않고 SPA·HTRF·세포 IC50를 구분한다.

기록된 PDB CC0, ChEMBL CC BY-SA 3.0, SI CC BY-NC 4.0은 서로 다른 출처의 허락 정보다.
SI 허락을 구매 접근으로 기록된 ACS 본문에 전이하지 않으며 제품 용도 허락으로 합치지 않는다.
이 명세는 권리 판단을 수행하지 않는다.

## 정적 검증

저장소 루트에서 표준 라이브러리만 사용하는 다음 명령을 실행할 수 있다.
첫 명령은 명세 구조와 차단 상태만 확인하며 외부 영수증을 열지 않는다.

```sh
python3 -I -B docs/research/mettl3_9g4s_prepared_state/verify_manifest.py
python3 -I -B docs/research/mettl3_9g4s_prepared_state/verify_manifest.py --verify-receipts
```

두 번째 명령은 19개 파일의 해시를 기존 두 manifest와 대조하고,
기존 preflight의 미결 ID, 선택 인스턴스, 정체성 연결 및 보호 정책 해시를 확인한다.
PDF/CSV는 해시만 읽고 내용을 디코딩하지 않는다. 보호 정체성 문맥과 실험 outcome 파일을 열지 않는다.
네트워크, 원본 분석 스크립트, 분자 라이브러리, 준비·물리 계산 worker를 호출하지 않으며 파일을 쓰지 않는다.
영수증을 옮겼다면 `--verify-receipts --identity-root /새/출처감사 --preflight-root /새/구조감사`로 위치를 지정한다.
파일 누락이나 해시 불일치는 실패하며, 자동 다운로드·복구·게이트 완화는 없다.

`PASS_STATIC_DECISION_SPECIFICATION`은 문서 계약의 검사 결과다.
`source_receipt_hashes_verified=true`도 해시와 기록의 일관성만 나타낸다.
원자료의 역사적 진위·이용 허락·준비 정확성·과학 적격성을 증명하지 않는다.
해결 근거가 확보되면 이 v1 차단 기록을 보존하고 별도 검토된 개정 명세를 만든다.

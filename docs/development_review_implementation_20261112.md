# 2026-11-12 코드 검토 후 개발 보고

## 판단과 검토 기준

기준 main은 `4c6e4b9fba670e325be37b538e054af88f65dc01`이며, 변경은
`codex/docking-review-integration-20261112`에서 통합한다.
이번 개발은 코드 검토에서 확인한 입력 화학, 작업 관리, 응답 계약, 배포 누락과
정제 정책의 연결을 다룬다. 실제 분자군에 대한 정확도 개선이나 상용 제품과의
동등성을 측정한 개발은 아니다.

현재 판정은 **실행 가능한 연구 개발 경로와 제품 계약의 보강**이다. 새로운
준비·정제 경로의 과학적 성능은 아직 검증되지 않았다. 기존 벤치마크를 새로운
구현의 결과로 다시 표시하지 않고, 기존 V7 정책과 수치 receipt를 보존한다.
관측하는 소스 파일이 바뀌었으므로 새로운 실행의 source manifest는 달라진다.

## 수정한 10개 검토 영역

| 영역 | 변경과 현재 동작 | 범위 또는 이행 조건 |
|---|---|---|
| 수용체 결합·수소 준비 | Named peptide template으로 표준 잔기의 전체 결합·결합 차수·수소를 준비하는 명시적 개발 프로파일 추가 | 완전한 heavy inventory, 연속 chain, OXT, 선언된 HID/HIE/HIP 필요. 실제 단백질 전반의 준비 성공률은 미측정 |
| PDB CONECT | 5열 고정폭 serial을 해석해 붙어 있는 5자리 원자 번호의 결합을 보존 | 지원 밖 확장 필드와 잘못된 record는 명시적 실패 |
| 원자 순서에 의존하는 formal charge | 새 경로는 named residue/microstate의 formal charge와 explicit graph의 Gasteiger partial charge를 사용 | 기존 proxy는 frozen diagnostic에 남음. 새 전하는 검증된 단백질 힘장 매개변수가 아님 |
| Scorer와 guidance의 화학 특징 차이 | 완전한 결합 그래프에서 공통 versioned 특징을 판정한 뒤 공간 부분집합을 적용 | 새 policy marker가 있는 양쪽 입력에만 적용. legacy/new 혼합 거부 |
| Queue 선두의 admission 실패 | 알려진 admission/plan/budget 오류를 durable `rejected_before_dispatch`로 확정 | 수치 dispatch와 budget 소모 0. 다음 owner-once가 다음 작업을 처리 |
| 늦게 도착한 취소 | Process 종료 확인 후 `cancel_state`를 terminal 상태와 일치하게 정리 | numerical 결과 상태와 lineage를 임의로 바꾸지 않음 |
| 계획과 실제 numerical source의 불일치 | Metadata 단계에서 owning numerical source inventory를 관측하고 worker의 첫 freeze와 비교 | 소스가 바뀐 계획은 stale. 과거 계획을 자동 재봉인하지 않음 |
| 원본 report의 비공개 값 노출 | 원본 numerical report는 private receipt로 유지하고 별도 public projection을 생성 | public artifact 역할과 digest가 별도이며, 기존 private role의 목록·다운로드는 차단 |
| 제출과 polling 응답의 `scientific_input` 불일치 | POST/GET이 같은 응답 builder를 사용 | 실제 authenticated HTTP 왕복 및 반환 keyset 회귀 포함 |
| Product Docker의 Engine V2 누락 | `.dockerignore`, 실제 `COPY`, build 중 CLI help 검사 보강 | 실제 COPY 파일 구성 검사와 설치 wheel 검증을 구분. ROCm image 실행은 별도 검증 필요 |

## 정제 설계의 세 가지 보강

### V9의 후보 보존과 선택

`InteractionAwareTorsionContactEnsembleRefinerV9`는 V7의 receptor penalty
`[2,4)` 선택 구간을 새 정책에서 제거한다. Receptor penalty가 2 미만이어도
내부 overlap을 개선할 torsion을 평가한다. Combined objective의 엄격한 감소,
receptor component의 비증가, authority·이동량·torsion·step의 기존 한계는 유지한다.

Source마다 V6 기준 후보와 개선 끝점을 최대 두 개 보존하고 각 후보에 scorer와
독립 내부 유효성 검사를 적용한다. 유효한 후보가 부족하면 Top-K를 채우지 않는다.
64개 source에서 최대 128개 후보를 scoring할 수 있으므로 과거 fixed-64 V7과
동일 계산량 비교라고 해석할 수 없다. V9 contact objective 자체는 overlap이다.

### 실제 물리·구조보존 정제의 연결

Product 계층의 `ExplicitRefinementDockingPipelineV1`에 두 provider를 연결한다.
`ContactRefinementProviderV9`는 위 후보 보존 정책을 실행한다.
`FixedReceptorStructureProviderV1`는 명시적인 legacy 또는 Fourier parameter와
matching cross parameter를 받아 실제 energy/force coordinator를 실행한다.
모델이 없거나 frame/topology/provider authority가 맞지 않으면 실패한다.

물리 경로의 입력 기준 후보와 최종 후보는 따로 보존한다. 최종 admission에
실패한 후보는 사유와 좌표를 남기되 선택에서 제외한다. Projected stationarity,
optimizer 종료 상태, Cartesian convergence는 서로 다른 항목이다.
자동 힘장 추정이나 과학적 유효성 승격은 추가하지 않았다.

### 전체 계산량과 선택 경로의 분리

`RefinementWorkV1`는 중첩된 모든 정제 arm의 objective 시도·완료·실패, trial,
accepted step, 방향 계산을 관측한다. 버려진 arm과 실패 전 이미 수행된 계산도
합산한다. 기존 numerical receipt와 별도인 sidecar이며, 선택된 경로의 step과
전체 계산량을 동일시하지 않는다. 물리 경로의 callback, 실제 evaluator 시도,
graph build, recoverable rejection도 구분한다.

## 통합 검토에서 추가로 보강한 부분

- Scorer 호출 **이전**에 후보 identity를 보존하도록 수정했다. 좌표와 hash를
  함께 바꾸는 coherent rebinding도 단일·batch scorer 양쪽에서 거부한다.
- 실제 legacy/Fourier E/F evaluator와 engine physics/geometry까지 numerical
  source inventory에 포함했다. 어댑터 파일만 hash하는 것으로 계산 구현의
  동일성을 주장하지 않는다.
- 새 수용체 H는 이름으로 결정되는 heavy-atom local frame에서 생성한다.
  강체 회전·이동에 따른 일관성을 검사하고, 공선·퇴화 frame은 실패시킨다.
- 산화·고원자가 S의 acceptor 오분류를 수정하고 sulfoxide/sulfone/thioether를
  scorer와 guidance 양쪽에서 검사한다.

## 검증 증거의 범위

검증 환경은 별도 cloud checkout의 Python 3.12.14, Torch 2.6.0+cpu,
NumPy 1.26.4, RDKit 2026.03.6이다. 테스트·설치 범위와 결과는 아래
최종 검증 기록에 명시한다. 합성 fixture의 통과는 실제 docking 정확도 증거가 아니다.

### 확인한 실제 입력의 한계

22개 표준 residue/microstate 각각을 가운데 둔 소규모 A–X–G 준비 검사는
통과했다. 이는 template 지원 점검이다. 보관된 6T88 원본 PDB에 대해서는
준비 경계만 확인했으며 가장 먼저 발생한 오류는
`histidine_microstate_required`였다. HIS를 임의로 HIE로 바꾸거나 FAD/GOL을
삭제해 통과시키지 않았다. 이 입력의 cofactor와 기타 nonpolymer도 v1 범위 밖이다.

새 프로파일로 PoseBusters, native recovery, affinity 또는 fresh holdout
정확도를 측정하지 않았다. `chemistry_validated`, `scientifically_validated`,
`product_qualified`, `claim_safe`는 승격하지 않는다.

## 다음 개발 우선순위와 완료 조건

| 우선순위 | 남은 개발 | 완료 조건 |
|---|---|---|
| P0 | 실제 표적의 준비 지원 확대 | Histidine/terminus 선택 근거, partial H·chain gap·missing heavy·water·ion·cofactor·crosslink 지원 정책과 실제 입력별 성공/typed failure 목록. Unsupported 원자의 묵시적 삭제 금지 |
| P0 | 준비→제안→정제→선택의 단계별 실분자 평가 | 고정 입력·seed·분모에서 V7/V9와 물리 경로의 후보 보존, invalid 생성, Top-1/Top-5를 새로 측정. 개발 집합과 fresh holdout 분리, 동일 계산량 비교 별도 |
| P0 | 물리 모델 및 특징의 검증 | 명시적 parameter authority와 atom typing, protonation/tautomer 및 cofactor 상태의 검증. Gasteiger와 contact overlap을 calibrated binding affinity로 표시하지 않음 |
| P1 | Reader의 전체 요청·동시성 예산 | 전역·tenant active 슬롯, 부모의 해시/JSON 처리와 stream까지 포함하는 deadline, 최대 32개 compare의 누적 비용 예약, aggregate memory 제한 검증 |
| P1 | 배포 패키지 소유권 정리 | Engine module과 `betelgeuze-dock`의 단일 소유자/고유 이름, release dependency와 migration, 두 wheel RECORD·entry point 중복 및 upgrade/uninstall 검사 |
| P1 | 실제 배포 runtime 검증 | ROCm image build/run, native scorer 비교와 운영 process containment의 지원 host 검증. CPU source/wheel smoke와 구분 |
| P2 | 후보 다양성·성능·사용성 | 검증된 RMSD 기반 diversity 정책, 전체 work/시간/메모리 수치, 연구자용 준비 오류 설명과 결과 비교 흐름 |

Reader의 기존 제한을 없다고 해석하면 안 된다. Owning child에는 wall 120초,
CPU 90초, address space 4 GiB, 1 CPU/thread 및 입출력 byte 제한이 있고,
HTTP 공통 rate/quota도 있다. 남은 경계는 이 child 밖의 부모 처리와 여러 요청의
합계이다. 주소 공간 제한과 실제 aggregate RSS 보장도 구분해야 한다.

현재 product와 independent engine distribution은 같은 Engine V2 module과
`betelgeuze-dock` 이름을 소유한다. 이 release 계약을 정리하기 전에는 각각
별도의 깨끗한 virtual environment에서 운용해야 한다.

## 실행·구현 문서

- [새 준비·특징 프로파일](engine_v2_prepared_peptide_development_v1.md)
- [후보 보존·물리 정제 API](explicit_refinement_pipeline_v1.md)
- [Prepared lifecycle와 공개 결과 계약](prepared_job_lifecycle.md)

## 최종 검증 기록

코드 commit `10825763da159ff920a2172f4f66345ec32ec08c`에서 **458개를 수집해
455개 통과, 실패 0개, skip 3개**를 확인했다. 실행 시간은 96.65초이다.
Skip은 native extension 미설치에 따른 기존 scorer 비교 3개이며, 새 기능의
실패를 skip으로 바꾼 것이 아니다. Starlette httpx deprecation과 `-c /dev/null`
사용 시 mobile marker 미등록으로 경고 2개가 있었다.

검사 범위와 skip의 정확한 test ID는
[기계 판독 검증 기록](evidence/development_review_20261112.json)에 포함했다.

| 검증 | 결과와 해석 |
|---|---|
| 통합 회귀 | Lifecycle/API/tenant/Docker context/준비/특징/정제/기존 V7/물리 adapter의 455개 통과 |
| 새 준비·CLI 및 retained pipeline | 위 통합 결과에 포함된 52개, skip 없음 |
| Engine V2 architecture guard | 통과. Product 역의존 및 금지된 dense operation 추가 없음 |
| External oracle architecture guard | 통과. 외부 도킹·시뮬레이션 엔진을 제품 의존성으로 연결하지 않음 |
| Ruff와 whitespace | 변경 Python 검사 및 diff 검사 통과 |
| Product wheel | 외부 context 빌드, clean venv 비편집 설치, `pip check`, CLI help 3개 통과 |
| Wheel 출처 | Python 555개와 필수 admission JSON 1개의 바이트 일치. 로드한 프로젝트 모듈 186개가 설치 prefix 아래에 존재 |
| Installed read-only journal | 합성 producer 1회, E/F 6회, failed E/F 0회. Reader 2회, 추가 E/F 0회. Journal 7개 파일과 부모 Torch 상태 보존 |
| 실제 ROCm image/native host | 이번 local 검증에서 실행하지 않음. Native scorer 비교 3개도 별도 지원 환경에서 필요 |
| 실분자 정확도 | 새 PoseBusters/native recovery/holdout 실험 없음 |

제품 wheel은 source `c5189d55a62cc74080133aa23777501b8ca9b002`에서 빌드했다.
해당 snapshot과 위 최종 코드 commit의 packaged source 557개를 해시로 비교해
전부 같음을 확인했다. 이후 변경은 runner/test/doc/CI에 한정됐다.
Wheel SHA-256은
`ce36e1ea1a1fa61f412504af5a31adca3865b7b658f370661ef9185a0f644a50`이다.

설치 smoke의 수치 실행은 `max_iterations_reached`로 끝났다.
`numerical_convergence=false`, `chemical_validity=null`, `pose_accuracy=null`을
그대로 유지했다. 설치 성공을 수렴·정확도 성공으로 해석하지 않는다.

통합 회귀의 재현 명령은 다음과 같다. 준비된 CPU dependency 환경에서 실행하며
기존 artifact bootstrap을 실행하지 않는 명시적 unit 범위이다.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python -B -m pytest --rootdir=. -c /dev/null --noconftest -p no:cacheprovider -q -rs \
  tests/unit/test_prepared_lifecycle*.py tests/unit/test_api_product_prepared.py \
  tests/unit/test_product_docking_http_contract.py \
  tests/unit/test_product_docking_response_contract.py \
  tests/unit/test_product_docking_response_snapshot.py \
  tests/unit/test_betelgeuze_product_api_contract.py \
  tests/mobile/test_product_docking_tenant_isolation.py \
  tests/unit/test_product_docker_cli_closure.py \
  tests/unit/test_verify_product_docker_context.py \
  tests/unit/test_build_product_image_smoke_preflight.py \
  tests/unit/test_github_workflow_trust_boundaries.py \
  tests/unit/test_engine_v2_receptor_preparation_v1.py \
  tests/unit/test_engine_v2_bounded_scaffolds.py tests/unit/test_engine_v2_input_identity.py \
  tests/unit/test_engine_v2_scorer_v1_stage5.py tests/unit/test_engine_v2_guided_proposal_stage4.py \
  tests/unit/test_explicit_refinement_pipeline.py \
  tests/unit/test_engine_v2_standalone_pipeline_core.py \
  tests/unit/test_fixed_receptor_structure_refinement.py \
  tests/unit/test_prepared_fourier_structure_refinement.py \
  tests/unit/test_engine_v2_element_contact_round8.py
```

새 `ci-docking-review-contracts.yml`은 Python 3.10/3.12에서 API·Docker COPY
계약과 CPU 준비·정제 계약을 실행한다. 후자의 지정 CPU 계약은 skip을 허용하지
않는다. 기존 native·lifecycle·product image CI를 대체하거나 완화하지 않았다.
원격 CI의 실제 완료 상태는 PR에서 별도로 확인해야 하며, 위 수치는 local 결과다.

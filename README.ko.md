# 리간드 도킹 및 분자동역학 납품 엔진

[English README](README.md)

이 저장소는 의도적으로 분리된 두 표면을 포함합니다.

1. **Independent Engine v2** — 버전형 분자 계약, 제한된 희소 기하,
   CPU 기준 AI·물리 합성 primitive, 엄격한 checkpoint, 제한형 PDB/SDF
   입력, 도킹 검색 scaffold, 실패 행을 보존하는 benchmark ledger입니다.
2. **레거시·제품 납품 스택** — validated runner, evidence gate, API,
   wetlab packet, CASP/CAMEO 준비, 제한형 로컬 납품 도구입니다.

V2 단거리 기하 경로는 밀도·cutoff·이웃/셀 용량·모델 폭·후보 예산이
고정될 때의 **조건부 제한 차수 `O(N)` 알고리즘 계약**을 갖습니다. 이는
저장소 전체나 장거리 물리의 실측 end-to-end `O(N)` 증거가 아닙니다.

## Engine v2 현재 상태

현재 구현 단계:

```text
v2_ao_native_cpu_scorer_contract_rc5
```

구현되어 GitHub-hosted CPU CI로 검증되는 범위:

- 정규 all-atom 상태, 검증 단계, SHA-256 identity
- 고정 용량 희소 radius geometry와 periodic image-shift gradient
- 정확한 좌표 미분을 갖는 scalar-energy AI 기준 모델
- matrix-free projection, torsion, temporal, physics gate primitive
- fail-closed CPU 오케스트레이터와 엄격한 runtime/checkpoint fingerprint
- Python 3.10–3.12용 독립 `betelgeuze-engine-v2` wheel
- 단일 모델 PDB와 단일 분자 SDF V2000 제한형 파서
- 독립 physics term registry 계약
- failure row와 exact checkpoint/restart identity를 보존하는 bounded
  deterministic CPU `float64` reference minimization; 과학·제품 승격은 없음
- 모든 perturbation을 보존하는 bounded component-energy central-difference
  force와 non-periodic configurational virial diagnostics; periodic virial은 fail-closed
- 별도 versioned reference-forcefield 확장에 ordered-star harmonic out-of-plane
  improper energy·force와 bounded deterministic symmetric degree-relaxed
  equal-weight distance-constraint projection, tangent-force 수렴과 exact
  checkpoint/restart를 갖는 projected Armijo minimization을 구현; mass weighting·
  과학 검증·제품 활성화는 없음
- caller-supplied fixed effective Born radius를 사용하는 bounded non-periodic
  CPU `float64` polar Generalized Born transfer energy·exact force와 v2 결합
  evaluator, solvation parameter identity를 결속한 optional constrained
  minimization·exact checkpoint/restart를 구현; radius 추정·nonpolar·salt/ion·
  periodic solvent·독립 검증·과학/제품 승격은 없음
- unsolvated·constrained·fixed-Born constrained·checkpoint·fail-closed 범위의
  ordered 14-case와 사전 10개 metric, 전 case failure denominator, exact 구현 source
  identity와 independent-reference 요구사항을 결과 전에 고정한 execution-disabled
  CPU minimization validation protocol, 그리고 11개 fixture·14개 case를 실제 CPU
  float64 v1/v2/fixed-Born runtime input·checkpoint pause plan·failure injection으로
  투영하되 physics를 평가하거나 결과를 수집하지 않는 exact materializer, 그리고
  constraint/tangent-force projection·fixed-Born·bounded backtracking·fail-closed
  identity·exact checkpoint/restart를 별도로 구현하고 source/import 경계를 고정한
  표준 라이브러리 독립 reference; test-only 비교는 구현 검증일 뿐 validation 결과가
  아니며, author/reviewer identity 분리·ordered review check와 limitation 확인·외부
  trusted reviewer 공개키·bounded freshness를 요구하는 Ed25519 독립 review
  attestation 계약, single-run authorization, local POSIX one-time nonce reservation,
  그리고 raw signed chain·durable nonce·실제 CPU-only deterministic process·network
  namespace를 다시 검증하고 최대 5분 operator-signed network-isolation attestation을
  확인한 뒤 별도 private root에 canonical mode-0600 secret-free 환경 receipt 하나를
  원자적으로 기록하는 run-start primitive, failure-inclusive bounded runner와 result
  writer까지 구현됨. stdlib-only bootstrap은 Engine v2/Torch/NumPy import 전에 Python
  executable·stdlib·OpenSSL·cryptography·NumPy·Torch의 실제 payload byte를 측정하고,
  run-start와 runner가 exact 6개 signed identity를 다시 측정함. 실제 attestation·trusted
  key·production root/receipt·승인된 실행·독립 result review·과학 승격은 없음
- exact synthetic case identity·사전 허용오차·failure row를 고정하고 실행 및
  parameter fitting 승인 gate를 닫아 둔 CPU reference energy/force 검증 protocol,
  그리고 결과를 수집하지 않는 exact fixture materializer와 source-bound
  표준 라이브러리 전용 analytic oracle, 구현 작성자/독립 reviewer identity 분리와
  외부 trusted reviewer key를 요구하지만 실제 review는 포함하지 않는 signed
  independent-review attestation 계약, 별도 operator identity·24시간 만료·외부
  revocation 목록·one-time nonce를 요구하지만 receipt는 포함하지 않는 single-run
  execution-authorization 계약, 그리고 27개 case·59개 variant 전체의 CPU 실행 환경과
  failure-inclusive 결과 receipt 형식을 고정하고 raw signed artifact 두 개를 다시 검증한 뒤
  POSIX `O_EXCL`/`fsync`로 one-time nonce를 로컬에서 소비하는 primitive, 이어서 전체
  chain과 실제 CPU-only deterministic process를 다시 검증하고 짧은 수명의 operator-signed
  network-isolation attestation을 확인한 뒤 secret-free 환경 receipt를 원자적으로 기록하는
  run-start primitive, 이어서 그 receipt와 exact code·source·dependency·artifact binding을
  다시 확인하고 one-time runner-start marker를 원자적으로 소비한 뒤 120초 평가 예산 안에서
  27개 case·59개 variant의 성공과 실패를 빠짐없이 메모리에 보존하는 제한형 CPU float64
  runner, 이어서 raw signed chain·live environment receipt·runner-start marker·exact
  observation을 다시 검증하고 private artifact root에 canonical mode-0600 receipt 하나를
  원자적으로 기록하는 failure-inclusive result writer. reader는 외부 exact receipt hash와
  revocation/supersession 입력을 요구하며 변경된 content는 외부 hash로 탐지하지만 receipt
  signature나 same-UID pathname/inode replacement resistance는 주장하지 않음. direct CLI는
  닫혀 있음. 실제 trusted key, production receipt·reservation/
  artifact root·production nonce reservation·production 환경 receipt·runner start/result
  receipt·승인된 production 실행·independent result review·과학 acceptance는 포함하지 않음
- 결정론적 제한형 torsion/rigid 도킹 후보·검색 scaffold
- 입력 case마다 정확히 하나의 성공/실패 행을 갖는 benchmark manifest

이 표면은 calibrated docking, MD, free energy, GPU 또는 고객 제품 기능이
아닙니다. 현재 모든 V2 capability는 `claim_safe=false`,
`customer_execution_enabled=false` 상태입니다.

먼저 읽을 문서:

- `docs/engine_v2_status.md`
- `docs/engine_v2_public_api.md`
- `config/independent_engine_v2_capabilities.yaml`
- `docs/entrypoints.md`

## 저장소 구성

| 영역 | 역할 |
| --- | --- |
| `betelgeuze_engine_v2/` | 독립 V2 계약, 분자 상태, 희소 기하, AI·수학 primitive, strict ingest, physics registry, 도킹·benchmark scaffold |
| `packaging/engine-v2/` | 독립 `betelgeuze-engine-v2` 배포 metadata |
| `core/`, `betelgeuze_engine/` | 레거시 물리·runtime·호환 표면. V2 wheel이 암묵적으로 import하지 않습니다. |
| `api/`, `betelgeuze_product/` | validated-runner 제품 API와 납품 orchestration |
| `tools/` | gate, manifest, bundle, benchmark/accounting, 운영 command |
| `tests/` | V2, 레거시 runtime, API, evidence, 납품 gate 테스트 |
| `config/` | capability 정책, target preset, threshold, runtime profile, gate 설정 |
| `docs/` | 아키텍처, 주장 경계, reviewer entrypoint, 납품 runbook, wetlab 문서, roadmap |
| `casp17/` | CASP17 로컬 operator/review scaffold와 상태 문서 |

## Independent Engine v2 빠른 시작

```bash
python3 -m venv .venv-v2
source .venv-v2/bin/activate
python -m pip install --upgrade pip
python -m pip install "build>=1.2,<2" numpy==1.26.4
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python tools/build_engine_v2_wheel.py --output-dir dist-engine-v2
python -m pip install --no-deps dist-engine-v2/*.whl
python -m pip check
```

기계 판독 가능 상태 확인:

```bash
python - <<'PY'
from betelgeuze_engine_v2.capabilities import capability_snapshot
import json
print(json.dumps(capability_snapshot(), indent=2, sort_keys=True))
PY
```

루트 API는 `ENGINE_API_VERSION`으로 관리됩니다. V2-G의 `io`, `docking`,
`benchmark`, registry, runtime submodule은 배포 버전 `1.0.0` 전까지
provisional입니다. 자세한 정책은 `docs/engine_v2_public_api.md`에 있습니다.

## 모노레포 개발 환경

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

표준 V2 집중 테스트:

```bash
python -m pytest -q \
  tests/unit/test_engine_v2_contracts_molecular.py \
  tests/unit/test_engine_v2_sparse_geometry_features.py \
  tests/unit/test_engine_v2_ai_core.py \
  tests/unit/test_engine_v2_periodic_energy.py \
  tests/unit/test_engine_v2_orchestrator_contract.py \
  tests/unit/test_engine_v2_runtime_checkpoint_contracts.py \
  tests/unit/test_engine_v2_packaging_guards.py \
  tests/unit/test_engine_v2_bounded_scaffolds.py \
  tests/unit/test_engine_v2_post_merge_state.py
```

`.github/workflows/ci-engine-v2-main.yml`은 관련 PR과 V2 관련 `main` push에서
Python 3.10, 3.11, 3.12로 같은 계약을 재검증합니다.

## 제품 API (`/simulate`)

HTTP 제품 표면은 **validated-runner ligand HTVS와 backmapping scoring만**
지원합니다. 범용 MD 및 Engine v2 고객 실행은 의도적으로 지원하지 않습니다.

```bash
pip install -r requirements-api.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

승인된 `runner_profile_id`가 없으면 요청은 fail-closed 됩니다.

## 로컬 evidence와 납품

`data/`, `runs/`, trajectory, checkpoint, 로컬 bundle, log, cache 같은 생성·민감
산출물은 GitHub에서 제외됩니다. Clean clone에는 소스, 테스트, schema,
lightweight figure, template이 들어 있지만 로컬 evidence gate나 과학 성능을
증명하지는 않습니다.

제한형 납품 검토는 다음 문서부터 시작합니다.

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_claim_policy.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/broad_claim_unlock_roadmap.md`

필요한 산출물이 재생성되거나 검토된 bundle로 제공되기 전까지 로컬 evidence
validator는 의도적으로 fail-closed 됩니다.

## CASP17 및 운영 lane

변경 가능성이 큰 CASP17 상세 상태는 다음 문서에서 관리합니다.

- `casp17/WORKBENCH.md`
- `casp17/CASP17_CURRENT_STATUS_REPORT.md`
- `casp17/CASP17_WIN_TIER_GOAL.md`

이들은 로컬 준비·operator review 표면이며 제출, leaderboard, win-tier 증거가
아닙니다.

## 주장 경계

현재 허용되는 표현:

- V2-G 제한형 CPU 기준 계약과 scaffold가 구현되고 테스트됐습니다.
- 독립 wheel은 Python 3.10–3.12의 clean environment에서 설치됩니다.
- strict ingest는 source hash를 기록하고 화학을 조용히 추론하지 않습니다.
- docking·benchmark ledger는 실패 candidate/case를 제거하지 않고 보존합니다.
- 제한형 로컬 납품 주장은 별도의 evidence gate와 검토된 로컬 산출물을 따릅니다.

추가 증거 없이 허용되지 않는 표현:

- calibrated docking 정확도 또는 광범위한 virtual screening 성능
- 검증된 force field, MD, MM/GBSA, FEP, binding free energy
- CUDA/ROCm/HIP parity 또는 가속
- wetlab-proven hit
- 자동 scorer/router/platform 승격
- 광범위한 상업용 신약개발 플랫폼

구현, 과학 검증, 공개 benchmark, 제품 qualification은 서로 다른 단계입니다.
소스 수준 테스트가 green이라고 해서 이 단계들이 하나로 합쳐지지 않습니다.

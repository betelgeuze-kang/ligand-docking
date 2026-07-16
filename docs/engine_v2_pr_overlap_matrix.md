# Engine v2 PR overlap and supersession matrix

역사적 분해 기준: `main@29aa6de8b15ed33a72519e4a7e06acf01e1ac356`

현재 기준: donor-cleanup evidence endpoint `main@2c0eddb107dde5dbdddf206ea24b6fefc78d7d18`

상태: #43, #49, #66은 bounded replacements 뒤 superseded로 닫혔다.
열린 donor PR은 없다. 닫힌 donor도 통째 병합 금지이며 다시 cherry-pick하지 않는다.

이 문서는 대형 draft PR #43과 #49를 통째로 병합하지 않고, 보안 스택과
독립 Engine v2 스택을 분리해 검토하기 위한 파일 단위 기준선이다.

## 1. PR 역할

| PR | 역할 | 현재 권장 처리 |
| --- | --- | --- |
| #43 | API 보안, validated runner, scientific proxy, legacy CPU physics가 혼합된 donor PR | 보안은 #44~#48/#62, scientific-input은 #77~#79, pose/RMSD는 #82, legacy retained scope는 #96/#97로 대체되어 closed/superseded |
| #44 | mobile-lite 의존성·CI 기준선 | `c48feab1`로 병합 완료 |
| #45 | 서버 고정 tenant identity | `2f5b6589`로 병합 완료 |
| #46 | product docking JSON ledger tenant isolation | `e997756c`로 병합 완료 |
| #47 | SQLite simulation ownership primitive | `27d6126f`로 병합 완료 |
| #48 | live `/simulate`, `/status`, `/results` ownership integration | `be42d1af`로 병합 완료 |
| #62 | current API security, validated runner, signed artifact/runtime evidence, fail-closed deployment | `3f9ede19`로 병합 완료; #43의 동일 보안 파일은 재추출 금지 |
| #49 | 독립 Engine v2 대형 donor PR | #50~#54, #56, #57로 대체되어 closed/superseded |
| #50 | V2-A contracts and molecular identity | `27dc439c`로 병합 완료 |
| #51 | V2-B sparse geometry and deterministic features | `48f550a7`로 병합 완료 |
| #52 | V2-C sparse AI, periodic gradients, projections | `1adca716`으로 병합 완료 |
| #53 | V2-D CPU orchestration and physics/residual composition | `b789ccf1`로 병합 완료 |
| #54 | V2-E runtime vocabulary, conditioning, checkpoint contracts | `b7b90d75`로 병합 완료 |
| V2-F (#56) | independent wheel, clean install, AST guards, overlap record | `f7309044`로 병합 완료 |

## 2. #43과 #44~#48 직접 파일 중복

| 대상 | #43과 직접 겹치는 파일 | 결정 |
| --- | --- | --- |
| #44 | `tests/route_compat.py`, `betelgeuze_product/tier_beta_vertical_slice.py` | #44의 경량 CI/route 계약을 기준으로 삼고 #43 변경은 별도 reconciliation 필요 |
| #45 | `api/config.py`, `api/request_identity.py`, `api/security.py` | #45가 인증 identity의 작은 검토 단위. #43에서 동일 파일을 다시 병합하지 않음 |
| #46 | `api/product_docking.py` | #46의 object authorization을 기준으로 삼음 |
| #47 | 직접 동일 파일 없음 | 개념상 #43의 `api/job_store.py` hardening과 연결되므로 SQLite transaction 정책을 별도 검토 |
| #48 | `api/main.py` | #48의 endpoint ownership wiring을 기준으로 삼고 #43의 main.py patch는 수동 분해 |

#44~#48 자체는 의도적인 stacked PR이었고 순서대로 병합됐다. 다음 파일은 당시
자식 PR에서 누적 갱신됐다.

- `.github/workflows/ci-mobile-lite.yml`: #44, #46, #47, #48
- `docs/api_server_bound_identity.md`: #45, #46, #47, #48

이 중복은 다른 구현을 뜻하지 않고 한 보안 스택의 누적 검증을 뜻한다.
현재 validated runner, signed result bundle, runtime qualification, deployment,
restricted/customer verifier의 소유권은 #62의 병합 결과다. #43에서 같은 API
security 파일을 다시 가져오지 않는다.

## 3. #49에서 새 V2 스택으로 추출된 파일군

| #49 파일군 | 대체 PR | 상태 |
| --- | --- | --- |
| `betelgeuze_engine_v2/contracts/**`, molecular models/validation | #50 V2-A | 추출 완료. canonical hash와 staged claim contract로 보강 |
| `betelgeuze_engine_v2/geometry/**`, `features.py` | #51 V2-B | 추출 완료. image shift와 실제 cutoff/permutation 테스트 추가 |
| `betelgeuze_engine_v2/ai/**`, `physics/projection.py` | #52 V2-C | 추출 완료. periodic exact-gradient path와 quantity semantics 추가 |
| `betelgeuze_engine_v2/engine.py` | #53 V2-D | 추출 완료. independent physics와 residual/total을 분리 |
| `train/runtime_inputs.py`, `train/checkpoint_contracts.py`, `core/ai_correction.py`, capability YAML | #54 V2-E | 추출 완료. vocabulary, `[B,P]`, strict fingerprints로 보강 |
| `.github/workflows/ci-engine-v2-cpu.yml`, packaging portions | #56 V2-F | 독립 wheel·clean install·AST guard로 대체 |

## 4. #49에서 아직 자동 승계하지 않는 파일

다음은 V2 core와 독립적으로 검토해야 하므로 #49에서 그대로 가져오지 않는다.

- `benchmark/performance_bench.py`
- `train/evaluator.py`
- `train/trainer.py`
- `train/train_pipeline.py`
- `tools/export_ai_router_onnx.py`
- `tests/unit/test_evaluator_metrics.py`
- `tests/unit/test_performance_bench_checkpoint.py`
- `tests/unit/test_checkpoint_consumers.py`
- `README.md`, `README.ko.md`
- `docs/independent_engine_v2_architecture.md`
- `docs/independent_engine_v2_migration_matrix.md`
- `docs/independent_engine_v2_commercial_roadmap.ko.md`

이 파일들은 각각 training consumer migration, benchmark harness, export contract,
상위 문서 PR로 나눈다. 문서의 capability 표현은 executable blocker와 CI 결과보다
우선할 수 없다.

## 5. 개념 중복과 비중복

- #43의 FEP, explicit solvent, MM-GBSA 명칭·주장 제한은 #97의 claim-honest
  legacy proxy 계약으로만 추출됐다. V2-A~F의 독립 에너지/힘 계약과 합산하지 않는다.
- #43의 legacy neighbor/cache와 pocket working-set 경계는 #96으로 추출됐다.
  V2-B compact radius graph와 목적 및 소유권이 다르다.
- #44~#48과 #62는 제품 API security lane이며 V2-A~F에는 API route나 tenant code를 넣지 않는다.
- V2-A~F green은 제품 API readiness나 legacy restricted delivery green으로 합산하지 않는다.

## 6. 완료된 기반 병합 순서

```text
Security lane: #44 -> #45 -> #46 -> #47 -> #48 -> #67 -> #62
Engine lane:   #50 -> #51 -> #52 -> #53 -> #54 -> V2-F
```

두 lane은 위 순서로 `main`에 병합됐다. #49는 필요한 child PR로 대체되어 닫혔다.
#43은 retained legacy scope를 #96/#97로 분리한 뒤 superseded로 닫혔다. 오래된
API/security/dependency/Tier-beta material은 current-main 소유권과 충돌하므로 폐기됐다.

## 7. 금지 사항

- #43 또는 #49를 child PR 위에 추가로 병합해 중복 패치를 되살리지 않는다.
- security lane green을 V2 scientific validity로 해석하지 않는다.
- V2 unit-test green을 docking accuracy, MD validity, GPU parity 또는 commercial
  readiness로 해석하지 않는다.

## 8. 2026-07 recovery stack 결과

| 소유 계층 | PR | Merge SHA | 현재 의미 |
| --- | --- | --- | --- |
| H0/H1 | #58, #59 | `a90c1d8b`, `de83e282` | post-merge state와 canonical input identity |
| P0 | #67 | `a3a585d5` | 공개 PR을 persistent self-hosted runner에서 구조적으로 분리 |
| H2 | #60 | `298c8223` | symmetry mapping identity와 not-evaluated pose semantics |
| H3 | #72 | `bf73e0ac` | #61을 대체한 clean benchmark-contract restack |
| H5 | #63 | `8097b516` | bounded reference-physics contracts; scientific promotion 없음 |
| H6 | #64 | `1657b6a1` | reproducible release-candidate packaging과 분리된 CI |
| H7 | #65 | `13af55c8` | offline external-baseline receipts; public benchmark validation 아님 |
| #66 child 1 | #73 | `6ae6d114` | bounded single-data-block CIF syntax만 추출 |
| H4 API leaf | #62 | `3f9ede19` | artifact/runtime/deployment fail-closed hardening; customer route disabled |

H3 donor #61은 #72 병합 후 superseded로 닫혔다. H4는 위 Engine 계층과 구현
소유권을 공유하지 않는 API-only leaf로 마지막에 최신 `main`에 병합됐다.

## 9. 현재 donor 경계

- #43은 closed/superseded이며 어떤 donor commit도 다시 가져오지 않는다.
- #66은 stale mixed ancestry donor로서 병합 없이 닫혔다. #73/#89/#90/#91/#94/#95만
  bounded child로 병합됐다. selected `_struct_conn`, polymer topology, peptide
  preparation, PDB/SDF/SMILES, alkane physics, SPICE evidence의 donor patch는
  폐기됐으며, 필요하면 각각 current `main`에서 새 작업으로 독립 검토한다.
- 추출된 syntax/identity/declaration 테스트 성공은 semantic mmCIF conformance, molecular preparation,
  scientific validation, public benchmark validation, GPU parity, customer execution,
  또는 commercial readiness를 확립하지 않는다.

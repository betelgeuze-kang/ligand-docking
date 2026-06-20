# AI-MD 제품 런타임 및 엔진 다음 진행 문서

상태: 다음 구현 방향 문서
작성일: 2026-06-18
관련 문서: `docs/product_full_implementation_plan.md`, `docs/post_p0_commercial_expansion_queue.md`, `docs/ai/tasks/TASK-TEMPLATE.md`

## 2026-06-19 진행 기준

- GUI 초기 시안은 향후 P0/P1 제품 실행 리스크가 닫힌 뒤 진행한다.
- 지금 우선순위는 CPU fallback이 아니라 GPU ROCm/HIP/Rust 기반 product runner를 clean container에서 끝까지 green으로 증명하는 것이다.
- core 물리엔진 작업은 `core/` 삭제가 아니라 compatibility layer를 유지한 채 `betelgeuze_engine` 계약, force-term result, ONSPS evidence, guarded residual, benchmark gate 순서로 승격한다.
- OpenCode/Cursor는 Codex의 하위 구현 워커로만 사용하고, Codex가 task slicing, 검토, 검증, 최종 수용 판단을 유지한다.

## 총평

다음 방향은 명확하다.

1. 먼저 제품 실행 현실성을 잠근다.
2. 그다음 코어 물리엔진과 토폴로지를 본격 리팩토링한다.

지금 바로 forcefield를 크게 갈아엎으면 안 된다. 첫 우선순위는 현재 product API, runner profile, Docker image, manifest, worker가 fake runner가 아니라 실제 production runner로 끝까지 도는지 확인하는 것이다. 그다음 아래 순서로 코어를 제품 엔진 구조로 옮긴다.

```text
Topology -> ForceTerm -> ONSPS Evidence -> Guarded Residual -> Benchmark
```

현재 레포는 제품 실행 경계가 꽤 잘 만들어져 있다. `/simulate`는 `runner_profile_id`를 요구하고, product scope는 approved validated runner profile로 잠겨 있으며, runner validation은 allowlisted script, profile id, evidence artifact, readiness, runner script SHA256을 확인한다. result manifest도 request hash, result hash, claim scope, topology fidelity, accuracy claim grade, HMAC signature를 담는다.

하지만 아직 실제 상용 AI-MD 코어는 아니다. topology는 sequence-aware 기능이 들어갔지만 기본 생성에는 placeholder 성격이 남아 있고, AdResS/all-atom path도 production blocked 또는 placeholder 성격이 남아 있다. H-bond/hydrophobic analytic force는 들어갔지만, 아직 제품급 force-term architecture라기보다는 smoke 가능한 최소 항에 가깝다.

## 먼저 닫아야 할 P0 리스크

### P0-1. Product Docker에서 실제 runner가 깨질 가능성

`Dockerfile.product`는 `requirements-package.txt`, `requirements-api.txt`, `requirements-deploy.txt`를 설치한다. 그런데 `requirements-package.txt`에는 `torch`가 없고, `tools/run_ligand_backmapping_scoring.py`는 top-level에서 `torch`를 import한다. `backmapping_scoring.production` profile은 이 runner를 실행한다.

즉 API/worker fake runner 테스트가 통과해도 실제 product container 안에서는 import error로 죽을 수 있다.

해야 할 일:

- CPU fallback이 아니라 ROCm/HIP/Rust product runtime을 기준으로 `requirements-product-rocm.txt`를 추가한다.
- `requirements-product-rocm.txt`는 기존 `requirements-rocm.txt`의 `torch==2.6.0+rocm6.1` profile을 재사용한다.
- `Dockerfile.product`는 ROCm/PyTorch base, `FORCE_RUST_HIP=1`, `RUST_HIP_USE_GPU_NBLIST_BUILDER=1`, `TORCH_BLAS_PREFER_HIPBLASLT=0`을 product 기본값으로 둔다.
- `rust_engine/`을 image 안에서 빌드해 `ldi_arc_rust` Rust/HIP backend import 경로를 보존한다.
- clean ROCm container 안에서 real runner import smoke와 Rust/HIP backend probe를 실행한다.

권장 구조:

```text
requirements-package.txt
requirements-api.txt
requirements-deploy.txt
requirements-product-rocm.txt
```

Definition of Done:

```bash
docker build -f Dockerfile.product -t ligand-docking-product .
docker run --rm \
  --device=/dev/kfd \
  --device=/dev/dri \
  --group-add video \
  --group-add render \
  -e FORCE_RUST_HIP=1 \
  -e RUST_HIP_USE_GPU_NBLIST_BUILDER=1 \
  -e CPU_FALLBACK_ALLOWED_FOR_PRODUCT=0 \
  ligand-docking-product python - <<'PY'
import torch
import ldi_arc_rust
import tools.run_ligand_backmapping_scoring
import api.main
from core.rust_hip_backend import probe_rust_hip_backend
assert torch.cuda.is_available(), "ROCm/HIP torch device is required"
assert getattr(torch.version, "hip", None), "PyTorch ROCm/HIP build is required"
print("product import ok", torch.__version__, getattr(torch.version, "hip", None), probe_rust_hip_backend().enabled)
PY
```

위 수동 smoke는 보조 확인일 뿐이며, product claim에 필요한 증거는 CPU fallback 없는 `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh` receipt다. 추가로 container 안에서 `backmapping_scoring.production`을 직접 실행해 기대 result artifact와 manifest를 생성해야 한다.

현재 진행:

- `deploy/verify_product_image.sh`의 `rocm-runtime` 모드는 host-mounted smoke directory에 Tier α dispatch smoke JSON과 backmapping scoring summary JSON을 남긴다.
- clean-container receipt는 단순 runner 성공이 아니라 `tier_alpha_result_manifest_signature_verified=true`, `backmapping_runner_claim_metadata_ready=true`, `product_runner_claim_metadata_ready=true`까지 요구한다.
- backmapping scoring smoke는 `hbond_evidence_v1`, `onsps_backmap_evidence_v1`, runner `claim_metadata`를 receipt에 기록한다.
- product ROCm dependency path는 `requirements-product-rocm.txt -> requirements-rocm.txt -> requirements-base.txt`로 분리되어 CPU `torch==2.6.0` pin을 타지 않으며, `product_rocm_requirements_no_cpu_torch_pin` preflight row가 이를 fail-closed로 검증한다.
- build-only image smoke receipt는 `product_image_build_smoke_ready`로만 기록하고, `product_image_smoke_ready`는 `rocm-runtime` mode에서 container runtime proof와 runner claim metadata가 모두 준비된 경우에만 허용한다. `build_mode_receipt_not_product_claim_ready` preflight row가 이 혼선을 fail-closed로 감시한다.
- 2026-06-20 기준 `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh`가 clean ROCm container에서 끝까지 통과했고, `runs/product_image_smoke_receipt_current.json`은 `status=product_image_smoke_ready`, `clean_container_smoke_ready=true`, `container_runtime_proof_ready=true`, `product_runner_claim_metadata_ready=true`, `container_runtime_rust_hip_backend_enabled=true`, GPU `AMD Radeon RX 6900 XT`로 기록한다.
- product ROCm image는 base image의 ROCm PyTorch를 보존하고, `requirements-product-rocm.txt`에서 CPU torch pin 없이 `requirements-base.txt`와 RDKit topology dependency를 설치한다.
- backmapping scoring smoke는 synthetic native PDB와 RDKit ligand topology를 사용해 `ligand_topology_claim_safe=true`, `onsps_backmap_claim_safe_row_count>=1`까지 receipt에 남긴다.

### P0-2. `/results/{job_id}`가 JSON result를 PDB로 반환하는 문제

현재 `/results/{job_id}`는 `status.result_file`을 읽고 무조건 `media_type="chemical/x-pdb"`로 `FileResponse`를 반환할 수 있다. 그런데 `backmapping_scoring.production` profile은 `{job_results_dir}/runner_result.json`을 만들 수 있다.

해야 할 일:

- 확장자 또는 manifest metadata로 artifact type을 판별한다.
- JSON result는 `JSONResponse`로 반환한다.
- PDB result는 `chemical/x-pdb`로 반환한다.
- 알 수 없는 binary artifact는 `application/octet-stream`으로 반환한다.

장기적으로 더 좋은 API 형태:

```text
/results/{job_id}                    -> manifest/result summary JSON
/results/{job_id}/artifact/{name}    -> named artifact download
```

Definition of Done:

- `backmapping_scoring.production` 결과는 JSON으로 반환된다.
- pose delivery profile artifact는 PDB/SDF/zip 성격에 맞게 반환된다.
- result manifest에 artifact type이 기록된다.
- response model과 실제 response behavior가 어긋나지 않는다.

현재 진행:

- `/results/{job_id}`는 signed manifest/evidence bundle provenance 없이는 fail-closed하며, `.json` 결과는 `JSONResponse`, `.pdb/.sdf/.mol/.zip`은 각 media type, 알 수 없는 artifact는 `application/octet-stream`으로 반환한다.
- `api.result_manifest`는 `result_file_suffix`, `result_artifact_type`, `result_file_media_type`을 서명 대상 manifest에 기록하고, `/results/{job_id}`는 manifest metadata를 우선 사용한 뒤 확장자 기반 판별로 fallback 한다.
- `/results/{job_id}` OpenAPI 계약은 더 이상 `ResultsResponse` 단일 response model을 선언하지 않고, JSON/PDB/SDF/MOL/ZIP/binary artifact media type을 명시한다.

### P0-3. `job_store`를 lazy config-aware factory로 바꿔야 함

`api/main.py`가 import 시점에 `job_store = SQLiteJobStore(settings.api_job_store_path)`를 만들면, 테스트에서 이후 `settings.api_job_store_path`를 monkeypatch해도 이미 생성된 store에는 반영되지 않을 수 있다.

해야 할 일:

- module-level 고정 `job_store`를 `get_job_store()`로 바꾼다.
- `settings.api_job_store_path`가 바뀌면 store를 다시 만든다.
- API endpoint와 worker wrapper가 모두 factory를 쓰게 한다.

Definition of Done:

- 테스트에서 `api_job_store_path` monkeypatch 후 tmp path에 DB가 생성된다.
- app import 순서에 따라 테스트 결과가 달라지지 않는다.
- worker와 API server가 같은 configured DB path를 사용한다.

현재 진행:

- `api.job_store.get_configured_job_store()`는 `settings.api_job_store_path` 변경을 감지해 path별 `SQLiteJobStore`를 lazy 생성한다.
- `api.main.get_job_store()`는 module import 시점에 DB를 고정하지 않고 현재 configured path를 사용하며, legacy 테스트의 `main.job_store` monkeypatch는 유지한다.
- `submit_simulation`, `/status/{job_id}`, `/results/{job_id}`, `run_simulation_async_wrapper`는 모두 lazy store factory를 통한다.

### P0-4. CI가 실제 product path를 증명해야 함

workflow 파일이 있는 것만으로는 부족하다. 현재 branch/PR에서 관련 GitHub Actions가 실제로 돌고 green인지 확인해야 한다.

해야 할 일:

- repository에서 Actions가 enabled인지 확인한다.
- path filter가 실제 변경 파일과 맞는지 확인한다.
- 필요하면 `workflow_dispatch`를 추가하거나 실행한다.
- product Docker build smoke를 CI에 추가한다.
- 이 lane이 merge gate라면 product API/worker workflow를 required check로 설정한다.

Definition of Done:

- `product-api-worker` workflow가 관련 branch/PR에서 green이다.
- Product Docker build smoke가 green이다.
- required status check가 product runtime gate를 반영한다.

현재 진행:

- 2026-06-20 기준 current branch `codex/commercialization-accounting-closure`의 GitHub Actions run은 코드/테스트 실패가 아니라 GitHub billing/spending-limit 문제로 job이 시작되지 않았다.
- `product-api-worker` run `27770545121`과 `product-image-smoke` run `27770546783` 모두 annotation이 "recent account payments have failed or your spending limit needs to be increased" 계열로 기록되며, 따라서 원격 CI green claim은 아직 금지한다.
- `runs/product_ci_runtime_gate_current.json` / `.md`는 `status=blocked_product_ci_runtime_gate`, `github_actions_started=false`, `external_blocker=true`, `blocker_code=github_actions_billing_or_spending_limit`, `workflow_dispatch_executed=false`, `external_state_mutated=false`로 fail-closed 상태를 기록한다.
- 같은 gate는 local ROCm clean-container 증거(`runs/product_image_smoke_preflight_current.json`)를 함께 읽어 `local_rocm_clean_container_ready=true`를 기록하므로, 남은 차단은 owner가 GitHub Billing & plans/spending-limit를 복구한 뒤 `product-api-worker.yml`, `product-image-smoke.yml` build mode, self-hosted ROCm `rocm-runtime` mode를 재실행하는 것이다.

## 권장 PR 순서

### PR-1. Product Runtime Reality Check

목표: product API, worker, validated runner profile, result manifest, container가 실제 production runner로 end-to-end 실행되는지 증명한다.

작업 범위:

- `requirements-product-rocm.txt` 추가
- `Dockerfile.product` ROCm/HIP/Rust dependency와 Rust extension build 수정
- `/results` JSON/PDB response handling 분리
- lazy `job_store` factory 추가
- real `backmapping_scoring.production` smoke fixture 추가
- product Docker build CI smoke 추가

집중 테스트:

```bash
python3 -m py_compile \
  api/main.py api/tasks.py api/validated_runner.py api/worker.py api/result_manifest.py

python3 -m pytest -q \
  tests/unit/test_api_validated_runner_adapter.py \
  tests/unit/test_p0_p1_closure.py
```

추가할 테스트:

```text
tests/e2e/test_product_real_runner_container_contract.py
tests/unit/test_results_endpoint_content_type.py
tests/unit/test_job_store_lazy_config.py
```

합격 기준:

- clean container에서 `tools/run_ligand_backmapping_scoring.py` import 성공
- `backmapping_scoring.production` profile validation 성공
- `/simulate -> worker -> runner_result.json -> result_manifest.json` 완료
- manifest signature verify 성공
- `/results`가 JSON을 PDB MIME으로 반환하지 않음

### PR-2. Engine Package Scaffold

목표: legacy behavior를 깨지 않고 새 engine package를 adapter/facade 방식으로 도입한다.

권장 package 구조:

```text
betelgeuze_engine/
  contracts/
    state.py
    result.py
    claim.py
  topology/
    protein.py
    ligand.py
    complex.py
    validity.py
  physics/
    state.py
    neighbor.py
    force_term.py
    forcefield.py
    terms/
      legacy_lj.py
      hbond.py
      hydrophobic.py
  backmapping/
    onsps.py
  interactions/
    hbond_evidence.py
  validation/
    force_checks.py
    invariance_checks.py
```

Compatibility policy:

```text
core/forcefield.py       -> legacy adapter
core/topology.py         -> facade
core/onsps_backmap.py    -> 새 backmapping module로 연결하는 shim
```

현재 진행:

- `core/forcefield.py`는 기존 `ForceField.compute()` 경로를 유지하면서 `product_energy_forces()` bridge를 통해 `betelgeuze_engine.physics.ProductForceField`의 `EnergyForces`/claim metadata 계약을 반환한다.
- KPI report는 `core_forcefield_bridge_ready`를 PM product gate로 노출하고, product evidence bundle validator는 tar 안의 KPI JSON에서 이 gate를 검증한다.
- KPI report는 추가로 `core_compatibility_layer_ready`를 PM product gate로 노출해 `core/onsps_backmap.py`, `core/topology.py`, `core/forcefield.py`가 새 `betelgeuze_engine` 구현을 호출하는 compatibility layer인지 검증한다.
- `core_forcefield_bridge_smoke`와 `core_compatibility_layer_smoke.rows[forcefield_product_bridge]`는 `ProductForceField` result의 neighbor diagnostics도 보존해야 한다. `neighbor_diagnostics_ready=true`, `neighbor_pair_count>0`, `neighbor_source=full_neighbor_pairs`가 없으면 product evidence bundle validation은 fail-closed된다.
- force-term physics validation rows는 finite-difference/translation/rotation/energy-drift pass뿐 아니라 `topology_fidelity=sequence_mapped`, `ligand_topology_valid=true`, `hbond_evidence_status=pass` claim metadata를 함께 통과해야 하며, `force_term_physics_validation_claim_safe_ready` PM physics gate가 product evidence bundle에서 fail-closed로 검증된다.
- 이 bridge gate는 runtime GPU readiness 주장이 아니라 compatibility/metadata 계약 증거이며, 실제 제품 실행 readiness는 ROCm manifest, Rust HIP build, clean-container `rocm-runtime` receipt로만 열린다.

핵심 interface:

```python
@dataclass
class EngineState:
    coords: torch.Tensor
    atom_types: torch.Tensor
    residue_types: torch.Tensor
    box: torch.Tensor | None
    metadata: dict[str, Any]

@dataclass
class NeighborPairs:
    idx: torch.Tensor
    dist: torch.Tensor
    mask: torch.Tensor

@dataclass
class EnergyForces:
    energy: torch.Tensor
    forces: torch.Tensor
    terms: dict[str, float]
```

합격 기준:

- `betelgeuze_engine` package가 추가된다.
- 기존 runner behavior가 바뀌지 않는다.
- `LegacyLJTerm`이 기존 `ForceField`와 smoke parity를 가진다.
- 기존 테스트가 green이다.

### PR-3. Topology v1

목표: placeholder 중심 topology helper에서 제품용 topology validity layer로 승격한다.

작업 범위:

```text
betelgeuze_engine/topology/protein.py
betelgeuze_engine/topology/ligand.py
betelgeuze_engine/topology/complex.py
betelgeuze_engine/topology/validity.py
```

필요 객체:

```python
@dataclass
class ProteinTopology:
    sequence: str
    residue_indices: torch.Tensor
    hbond_roles: list[str]
    virtual_site_offsets: torch.Tensor
    fidelity: str

@dataclass
class LigandTopology:
    smiles: str
    atom_elements: list[str]
    formal_charges: list[int]
    donor_acceptor_roles: list[str]
    ring_flags: list[bool]
    chirality_tags: list[str]
    validity: dict[str, Any]

@dataclass
class ComplexTopology:
    protein: ProteinTopology
    ligand: LigandTopology
    pocket_residue_indices: list[int]
    claim_scope: str
```

정책:

- product profile에서 sequence가 없으면 `topology_fidelity=placeholder_alanine`으로 기록한다.
- placeholder topology는 delivery-ready claim을 막는다.
- sequence-mapped여도 ligand topology validity가 fail이면 claim을 막는다.
- AdResS production-blocking behavior는 fail-closed로 유지한다.
- `GENERAL_MD_ACCURACY_CLAIM`은 계속 차단한다.

현재 반영 상태:

- `LigandTopology.validity`는 RDKit parse source, atom/H-bond/ring/charge/chirality counts, chirality/ring/protonation/tautomer status, claim-safe blocker를 기록한다.
- `topology_claim_metadata()`는 ligand product validity를 `ligand_topology_claim_safe`, `ligand_chirality_status`, `ligand_protonation_status`, `ligand_tautomer_status`, `ligand_validity_blockers`로 엔진 claim metadata에 연결한다.
- sequence-mapped protein이라도 unassigned ligand chirality가 있으면 `unassigned_ligand_chirality`로 fail-closed된다.
- PM chemistry KPI는 별도 휴리스틱이 아니라 `LigandTopology.validity`에서 나온 상태를 집계한다.
- `betelgeuze_engine.topology.TopologyFactoryFacade`는 product module 내부에서 `ProteinTopology`, `LigandTopology`, `ComplexTopology`, `topology_claim_metadata()`를 한 번에 생성하는 facade로 추가됐다. `engine_topology_factory_facade_ready` Product KPI는 sequence+valid ligand claim-safe, placeholder protein blocked, invalid ligand blocked를 함께 검증한다.

합격 기준:

- `TopologyFactory`는 facade로 남고 내부에서 `ProteinTopology`를 사용한다.
- placeholder와 sequence-mapped fidelity가 manifest metadata에 정확히 기록된다.
- invalid ligand chemistry fixture가 fail-closed된다.

### PR-4. Force-Term Modularization

목표: LJ 중심 `ForceField`에서 product force-term pipeline으로 이동한다.

초기 term:

```text
betelgeuze_engine/physics/terms/
  legacy_lj.py
  screened_electrostatics.py
  directional_hbond.py
  hydrophobic_contact.py
  pocket_wall.py
  torsion_prior.py
  topology_penalty.py
```

활성화 순서:

```text
v1 default:
  LegacyLJTerm
  HydrophobicContactTerm
  DirectionalHBondTerm

v1 guarded:
  ScreenedElectrostaticsTerm
  PocketWallTerm

v2:
  TorsionPriorTerm
  TopologyPenaltyTerm
  WaterDisplacementProxyTerm
```

필수 검증:

```text
1. finite difference force check
2. neighbor-list vs full-pair parity
3. translation invariance
4. rotation equivariance
5. no NaN / no Inf under close contacts
6. force norm cap
7. energy drift under short integration
```

합격 기준:

- `LegacyLJTerm` parity test 통과
- `DirectionalHBondTerm`이 donor/acceptor role을 반영
- `HydrophobicContactTerm`이 hydrophobic mask를 반영
- finite difference force error가 threshold 이하
- O(N) neighbor cap 유지

현재 반영 상태:

- default product registry는 `directional_hbond`, `hydrophobic_contact`, `legacy_lj` 3개를 유지한다.
- `guarded_force_term_registry()`는 opt-in `screened_electrostatics` term을 추가로 제공한다.
- `ScreenedElectrostaticsTerm`은 caller-supplied charge vector와 `charge_model_valid=true`가 있을 때만 energy/forces/diagnostics/claim metadata를 claim-safe로 반환한다.
- charge metadata가 없거나 charge model이 검증되지 않으면 zero energy/force와 fail-closed `blocked_reason`을 반환한다.
- KPI report는 `guarded_force_term_plugin_ready`로 default registry 보존, opt-in registry 확장, screened electrostatics finite-difference, missing/unvalidated charge blocker를 함께 검증한다.

### PR-5. ONSPS Interaction Evidence

목표: ONSPS 4-bead output을 scoring feature에서 interaction evidence module로 승격한다.

새 module:

```text
betelgeuze_engine/backmapping/onsps.py
betelgeuze_engine/interactions/hbond_evidence.py
```

Evidence schema:

```python
@dataclass
class HbondEvidence:
    site_count: int
    donor_site_count: int
    acceptor_site_count: int
    donor_acceptor_pairs: list[dict]
    distance_pass_count: int
    angle_pass_count: int
    distance_pass_fraction: float
    angle_pass_fraction: float
    unsatisfied_donor_count: int
    unsatisfied_acceptor_count: int
    overanchoring_flag: bool
    missing_expected_anchor_flag: bool
    geometry_evaluated: bool
    geometry_complete: bool
    hbond_confidence: float
    claim_safe: bool
```

현재 반영 상태:

- `OnspsBackmapEvidence`는 `onsps_backmap_evidence_v1` schema, `mapping_source`, `role_counts`, `claim_safe`, `blocked_reason`을 기록한다.
- `backmap_4bead_onsps()`는 기존 tuple 반환을 유지하면서 metadata에 ONSPS evidence dict를 싣는다.
- `HbondEvidence`는 2-bead ligand 입력에서 ONSPS metadata를 `onsps_backmap_metadata`로 포함한다.
- `HbondEvidence`는 top-level `donor_site_count`, `acceptor_site_count`, `distance_pass_count`, `angle_pass_count`, `geometry_evaluated`, `geometry_complete`를 포함해 PM/KPI가 nested pair list 없이 schema readiness를 검증할 수 있다.
- `HbondEvidence.schema_ready()`는 `hbond_evidence_v1` top-level counts와 embedded `onsps_backmap_evidence_v1` metadata readiness를 함께 검사한다.
- `HbondEvidence.to_claim_metadata()`는 `hbond_claim_metadata_v1`로 `topology_fidelity`, `ligand_topology_valid`, `hbond_evidence_status`, `force_residual_applied`, `claim_safe`, `blocked_reason`을 공통 claim metadata 표면에 연결한다. H-bond evidence 단독으로는 product claim을 승격하지 않고 `product_claim_promoted=False`이면 `hbond_evidence_not_product_claim_promoted`로 fail-closed한다.
- `ONSPS_BACKMAP_SCHEMA_VERSION`은 `betelgeuze_engine.backmapping`에서 공개되며, `onsps_backmap_evidence_schema_ready` Product KPI는 valid RDKit ETKDG mapping, empty geometry fail-closed, no-site ligand fail-closed, H-bond embedded ONSPS metadata schema를 함께 검증한다.
- ONSPS가 RDKit ETKDG 기반 claim-safe backmap이 아니면 H-bond claim도 fail-closed된다.
- pose/ranking/H-bond KPI harness는 active fixture를 2-bead ONSPS path로 평가하고, top1 row에 `onsps_backmap_evidence_v1` provenance를 남긴다.
- pose/ranking/H-bond KPI harness는 `amide_overanchored_decoy_pose`를 `overanchored_decoy`로 차단하고 `overanchored_decoys_blocked=true`를 summary gate로 기록한다.
- `tools/run_ligand_backmapping_scoring.py` shim이 호출하는 product runner summary는 row-level `hbond_evidence_v1` / `hbond_claim_metadata_v1` / `onsps_backmap_evidence_v1` fields, `hbond_evidence_schema_ready`, `onsps_backmap_metadata_schema_ready`, `hbond_evidence_summary`, fail-closed `claim_metadata`를 내보낸다.
- runner-level `claim_metadata`는 `hbond_claim_metadata_schema_version`, `hbond_claim_metadata_schema_ready_row_count`, `hbond_distance_pass_count`, `hbond_angle_pass_count`, `hbond_unsatisfied_donor_count`, `hbond_unsatisfied_acceptor_count`, `onsps_backmap_metadata_schema_ready_row_count`를 집계한다.
- API `result_manifest.json`은 JSON runner result의 `claim_metadata`와 `hbond_evidence_summary`를 복사해 HMAC signature 대상에 포함한다.

필수 fixture:

```text
- ethanol CCO
- amide ligand
- tertiary amine
- carboxylate
- phosphate
- heteroaryl nitrogen
- invalid SMILES
```

합격 기준:

- site count만 보지 않고 role, angle, distance, unsatisfied count를 산출한다.
- over-anchoring detector가 너무 가까운 polar contact를 잡는다.
- H-bond evidence가 `runner_result` 또는 result manifest에 들어간다.
- `delta_backmap`이 크면 yellow band 또는 abstention으로 연결된다.

### PR-6. Guarded Top-K Force Residual

목표: product policy가 허용하는 범위에서만 guarded force residual을 적용한다.

정책:

```text
- top 1-5%에만 적용
- max_abs_delta_score cap
- max force norm cap
- max displacement cap
- energy drift cap
- topology validity fail이면 skip
- uncertainty high이면 abstain
- result에 residual_applied, residual_skipped_reason 기록
```

필요 객체:

```python
@dataclass
class ForceResidualDecision:
    apply: bool
    reason: str
    rank_pct: float
    topology_valid: bool
    uncertainty: float
    delta_score: float

@dataclass
class ForceResidualReport:
    applied: bool
    max_force_norm: float
    energy_drift_pct: float
    displacement_rmsd: float
    skipped_reason: str
    delta_score: float
    rank_pct: float
    top_k_eligible: bool
```

현재 반영 상태:

- `decide_force_residual()`은 `delta_score`를 받아 `max_abs_delta_score` 초과와 non-finite score를 fail-closed abstention으로 막는다.
- `decide_force_residual()`은 non-finite `rank_pct`와 top-K policy 밖 rank를 fail-closed abstention으로 막는다.
- `apply_guarded_force_residual()`은 수동 decision 입력에도 `max_abs_delta_score`, `max_force_norm`, `max_displacement`, `max_energy_drift_pct`를 다시 확인한다. Product-facing policy cap에는 요구서 표현과 맞춘 `max_energy_drift` alias도 함께 기록한다.
- `ForceResidualReport.to_claim_metadata()`는 `force_residual_claim_metadata_v1`로 `force_residual_applied`, `force_residual_delta_score`, `force_residual_rank_pct`, `force_residual_top_k_eligible`, `force_residual_policy_caps`, `force_residual_abstention_reason`을 엔진 claim metadata로 변환한다.
- residual claim metadata는 `force_residual_required_policy_caps`, `force_residual_policy_caps_ready`, `force_residual_observed_caps_ready`, `force_residual_all_observed_caps_within_policy`를 포함해 policy cap 자체가 finite/in-range인지와 관측된 correction이 cap 안인지 분리해 검증한다.
- local PC KPI report는 top10 residual runtime과 별도로 `delta_score_cap_exceeded`, `uncertainty_abstained`, `outside_top_k_policy` abstention smoke를 기록한다.
- PM runtime KPI는 `force_residual_bounded_policy_ready`, `force_residual_observed_caps_ready`, `force_residual_confidence_abstention_ready`, `force_residual_top_k_policy_ready`, `force_residual_top_k_rank_pct`를 노출한다.

합격 기준:

- top-K policy 밖에서는 force residual을 절대 적용하지 않는다.
- `max_abs_delta_score` 초과 residual은 적용하지 않고 abstain한다.
- residual 적용 후 NaN/Inf가 없다.
- energy drift threshold 초과 시 rollback한다.
- result에 guard trace와 skip reason을 기록한다.
- pose/physics check가 뒷받침하지 않으면 rank score만 바꾸지 않는다.

## Milestone 정의

### Milestone A. Product Alpha Runtime

목표: 실제 product profile이 container에서 끝까지 돈다.

완료 조건:

```text
- Docker build green
- API /simulate green
- validated runner executes real profile
- JSON/PDB result content-type correct
- signed result manifest generated
- worker queue/heartbeat/retry works
- security middleware does not block intended local path
```

### Milestone B. Engine Alpha

목표: 새 engine package가 legacy behavior를 깨지 않고 들어간다.

완료 조건:

```text
- betelgeuze_engine package exists
- force-term interface exists
- topology interface exists
- ONSPS moved behind adapter
- legacy runner still green
- physics smoke tests green
```

### Milestone C. Physics Beta

목표: 물리항이 제품적으로 의미 있는 수준이 된다.

완료 조건:

```text
- H-bond directional evidence
- hydrophobic/contact evidence
- screened electrostatics optional
- topology validity gate
- force finite difference test
- neighbor parity test
- energy drift guard
```

### Milestone D. Scientific Validation Beta

목표: 상용급 정확도 논의가 가능한 최소 benchmark surface를 만든다.

완료 조건:

```text
- pose RMSD fixtures
- active/decoy ranking fixtures
- H-bond recovery fixtures
- over-anchoring false-positive fixtures
- runtime O(N) scaling plot/report
- confidence calibration report
```

## 지금 하지 말아야 할 것

1. `E0-E5 closed`를 과학적으로 완료된 것처럼 말하지 않는다. 용어를 분리한다.

```text
roadmap_contract_closed
engine_physics_validated
scientific_claim_promoted
```

2. API gate와 문서만 계속 늘리지 않는다. 다음 핵심 작업은 반드시 코드로 들어가야 한다.

```text
topology
force terms
interaction evidence
physics validation tests
```

3. `SE3EquivariantCorrection` 이름만 믿지 않는다. rotation equivariance test를 추가하거나, 통과하지 못하면 `NeuralForceCorrection` 같은 낮은 claim 이름으로 바꾼다.

## 수석엔지니어 기준 코드 원칙

1. 기존 runner path는 유지한다. `tools/run_ligand_htvs_pipeline.py`, `tools/run_ligand_backmapping_scoring.py`, `tools/run_ligand_topk_delivery.py` 같은 allowlisted script는 구현이 이동하더라도 shim으로 남긴다.

2. `core/`는 compatibility layer로 유지한다.

```text
새 betelgeuze_engine 구현
-> core가 새 구현을 호출
-> 기존 tests green
-> runner가 새 구현 직접 호출
-> core legacy 축소
```

현재 product KPI는 `core_compatibility_layer_ready`로 이 원칙을 추적한다. 이 gate는 `core/onsps_backmap.py`의 import identity shim, `core/topology.py`의 `ProteinTopology` bridge, `core/forcefield.py`의 `ProductForceField`/`EnergyForces` claim metadata bridge를 함께 확인한다.

3. 모든 물리항은 energy, forces, diagnostics를 반환한다.

```python
@dataclass
class TermResult:
    energy: torch.Tensor
    forces: torch.Tensor
    diagnostics: dict[str, Any]
```

4. 모든 correction은 bounded여야 한다.

```text
max_abs_delta_score
max_force_norm
max_displacement
max_energy_drift
abstain_threshold
```

5. 모든 결과는 claim-safe metadata를 가져야 한다.

```json
{
  "topology_fidelity": "sequence_mapped",
  "ligand_topology_valid": true,
  "hbond_evidence_status": "pass",
  "force_residual_applied": false,
  "claim_safe": false,
  "blocked_reason": "placeholder_alanine_topology"
}
```

## PM이 봐야 할 KPI

Runtime KPI:

```text
- 1k ligand score-only runtime
- top 100 4-bead rescoring runtime
- top 10 force residual runtime
- memory peak
- neighbor-list rebuild frequency
```

Physics KPI:

```text
- finite difference force error
- energy drift
- neighbor-list parity error
- topology invalid rate
- backmapping failure rate
```

현재 반영 상태:

- `betelgeuze_engine.validation`은 finite-difference force error, translation invariance, energy drift smoke, neighbor-list parity error를 실제 로컬 계산으로 제공한다.
- `betelgeuze_engine.validation`은 회전 등변성(rotation equivariance) 검사도 제공해 force 방향이 좌표 회전에 맞게 회전하는지 확인한다.
- `ai_md_engine_kpi_report`의 Physics KPI는 더 이상 `energy_drift_smoke_pct`와 `neighbor_list_parity_error`를 상수로 채우지 않고 validation helper 결과를 기록하며, `rotation_equivariance_error < 1e-9`도 product physics gate로 잠근다.
- PM 요구서의 Physics KPI 표면에 맞춰 `topology_invalid_rate`와 `backmapping_failure_rate`도 Physics KPI와 PM physics summary에 명시적으로 승격한다. 계산 출처는 ligand validity/ONSPS evidence fixture이며, Chemistry KPI에도 그대로 남겨 원인 분석 경로를 보존한다.
- `backmapping_failure_rate`는 H-bond site count proxy가 아니라 `OnspsBackmapEvidence.claim_safe` 기준의 ONSPS 2-bead backmap failure rate로 계산한다.
- PM physics summary는 `finite_difference_force_error_pass`, `energy_drift_pass`, `rotation_equivariance_pass`, `neighbor_list_parity_pass`, `topology_invalid_rate_pass`, `backmapping_failure_rate_pass`를 노출한다. Product evidence bundle validator는 tar 안 KPI JSON에서 이 physics 표면이 빠지거나 threshold를 넘으면 `product_claim_ready=false`로 fail-closed 처리한다.
- Runtime KPI도 단순 숫자 출력이 아니라 `score_only_1k_runtime_tracked`, `top100_4bead_rescoring_runtime_tracked`, `top10_force_residual_runtime_tracked`, `memory_peak_tracked`, `neighbor_list_rebuild_frequency_tracked` PM gate로 승격한다. Product evidence bundle validator는 tar 안 KPI JSON에서 이 runtime 표면이 비어 있거나 0이면 `product_claim_ready=false`로 fail-closed 처리한다.
- `neighbor_list_rebuild_frequency_tracked`는 이제 helper count만 보지 않고, rebuilt `NeighborPairs`가 `ProductForceField.energy_forces()`에 실제 제공됐는지 `neighbor_pairs_provided=true`, `neighbor_source=provided`, `last_forcefield_neighbor_pair_count == last_neighbor_pair_count`로 확인한다.

Chemistry KPI:

```text
- H-bond recovery
- unsatisfied donor/acceptor detection
- over-anchored decoy rejection
- ligand chirality preservation
- ring/tautomer/protonation validity
```

Product KPI:

```text
- clean install success
- runner profile validation pass
- signed manifest verification pass
- bundle validation pass
- blocked claim correctly blocked
```

현재 반영 상태:

- `ai_md_product_evidence_bundle`은 생성한 tar를 다시 열어 member list, member count, tar sha256, tar 내부 artifact sha256을 검증하고 `bundle_validation_pass`를 기록한다. bundle export 이후 worktree 원본 파일이 재생성되어도 tar 내부 manifest와 payload가 일치하면 bundle 자체 검증은 통과한다.
- `ai_md_engine_kpi_report`의 Product KPI는 current evidence bundle JSON/tar를 검증해 `bundle_validation_pass`, `bundle_validation_error_count`, `bundle_validation_errors`를 보고한다.
- Product KPI는 PM-facing 필드명과 raw `product_kpi` 필드명을 맞춘다. `runner_profile_validation_pass`, `signed_manifest_verification_pass`, `bundle_validation_pass`, `blocked_claim_correctly_blocked`, `clean_install_success`는 raw KPI와 PM summary 양쪽에서 확인되어야 한다.
- `ai_md_engine_kpi_report`의 Product KPI는 runner result의 `claim_metadata`, `hbond_evidence_summary`, `force_residual_shortlist`/`force_residual_summary`가 signed API `result_manifest`에 포함되는지 `runner_claim_metadata_signed`로 확인한다.
- `ai_md_product_evidence_bundle`은 signed manifest 안의 `force_residual_summary`를 `force_residual_summary_signed`로 따로 노출하고, `force_residual_claim_metadata_v1`, policy caps, observed caps가 모두 준비되지 않으면 `product_claim_ready=false`로 fail-closed 처리한다.
- signed runner manifest smoke는 `manifest_claim_safe=false`와 non-empty `manifest_blocked_reason`을 함께 요구한다. Product evidence bundle validator는 `blocked_claim_correctly_blocked`가 Product KPI와 PM Product KPI 양쪽에 없거나 manifest blocked reason이 비어 있으면 `product_claim_ready=false`로 fail-closed 처리한다.
- `tools/run_ligand_htvs_pipeline.py`, `tools/run_ligand_backmapping_scoring.py`, `tools/run_ligand_topk_delivery.py`는 allowlisted path를 유지하면서 `betelgeuze_engine.product.runners.*` adapter로 라우팅한다. `allowlisted_runner_shim_contract_ready` Product KPI는 세 shim의 adapter import, runtime symbol identity, runner profile SHA256 일치를 함께 검증한다.
- 세 allowlisted runner shim은 local runner implementation을 다시 품으면 안 된다. KPI와 product evidence bundle validator는 `sys.modules[__name__]` 또는 `_sys.modules[__name__]` canonical module alias, `shim_contract_type=canonical_module_alias`, `self_implementation_blocked=true`가 아니면 fail-closed한다.
- `force_term_result_contract_ready` Product KPI는 registered force term 각각이 `TermResult.energy`, `TermResult.forces`, `diagnostics`, `claim_metadata`를 반환하고 shape/finiteness/required claim keys를 만족하는지 검증한다.
- `force_term_claim_metadata_smoke`는 aggregate `ProductForceField` result도 `forcefield_neighbor_diagnostics_ready`, `forcefield_neighbor_pair_count`, `forcefield_neighbor_source=full_neighbor_pairs`로 검증한다. Product evidence bundle validator는 이 aggregate neighbor diagnostics가 빠지면 force-term result contract를 claim-ready로 보지 않는다.
- guarded analytic correction인 `screened_electrostatics`는 opt-in registry에만 존재하며 `max_abs_energy`, `max_force_norm`, `max_active_pair_count` caps를 claim metadata와 diagnostics에 노출한다. cap 초과 fixture는 zero correction + `screened_electrostatics_policy_cap_exceeded`로 fail-closed되어야 하며, product evidence bundle validator는 `policy_caps_ready`, `observed_caps_ready`, `bounded_correction_ready`, `policy_cap_exceeded_blocked`가 없으면 claim-ready로 보지 않는다.
- `ProductForceField` aggregate `force_term_claim_rows`도 guarded analytic term의 bounded cap metadata를 보존해야 한다. 단독 term smoke가 통과해도 aggregate row에서 `policy_caps_ready`, `observed_caps_ready`, `bounded_correction_ready`가 사라지면 product evidence bundle validation은 fail-closed한다.
- bundle validation이 통과해도 clean ROCm container smoke receipt가 없으면 `product_claim_ready=false`를 유지한다.
- clean install/product claim의 다음 required step은 CPU fallback이 아니라 `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh`로 clean container ROCm/HIP/Rust runner smoke receipt를 붙이는 것이다.
- release refresh chain은 `product_image_smoke_preflight -> ai_md_engine_kpi_report -> ai_md_product_evidence_bundle -> ai_md_engine_kpi_report -> ai_md_product_evidence_bundle` 순서로 current artifacts를 수렴시킨다. KPI report가 bundle validation을 읽고 bundle이 KPI readiness를 읽는 순환 증거 구조라, 한 번만 실행하면 stale blocker가 남을 수 있다.

Chemistry KPI 현재 반영 상태:

- `hbond_recovery_present`는 단순 site-count proxy가 아니라 pose/ranking benchmark의 expected top-1 pose에서 `hbond_claim_safe=true`와 `hbond_status=pass`가 확인된 `hbond_recovery_pose_count`를 기준으로 한다.
- `hbond_evidence_schema_ready`는 fixture 전체에서 `hbond_evidence_v1`, ONSPS metadata, donor/acceptor role count, distance/angle pass count, geometry flags가 모두 존재하는지 확인한다.
- `unsatisfied_donor_acceptor_detection`은 더 이상 상수 gate가 아니다. `HbondEvidence.unsatisfied_donor_count`와 `unsatisfied_acceptor_count`를 fixture/pose benchmark에서 집계하고, 실제 unsatisfied donor/acceptor evidence가 있을 때만 PM chemistry gate를 통과한다.
- pose/ranking H-bond benchmark는 far-decoy와 overanchored-decoy row의 unsatisfied/blocked evidence를 함께 기록해 H-bond recovery와 decoy rejection을 같은 schema에서 추적한다.
- `ligand_topology_validity_schema_ready`는 fixture 전체에서 `ligand_topology_validity_v1`, claim-safe blocker list, chirality/ring/protonation/tautomer status, charge/ring/chiral counts가 모두 존재하는지 확인한다.
- `chirality_preservation_ready`는 specified chiral fixture 보존뿐 아니라 unassigned stereocenter fixture가 `unassigned_ligand_chirality`로 fail-closed될 때만 통과한다.
- `ring_validity_ready`, `tautomer_validity_ready`, `protonation_validity_ready`는 각 chemistry fixture의 ligand topology validity schema에서 PM chemistry gate로 직접 승격한다.

## GUI 초기 시안 반영

참고 시안: `/home/betelgeuze/다운로드/ChatGPT Image 2026년 6월 19일 오후 10_05_44.png`

GUI의 첫 화면은 marketing/landing page가 아니라 실제 operator가 바로 쓰는 `Betelgeuze AI-MD Workbench`로 잡는다. 전체 정보 구조는 좌측 module navigation, 상단 runtime/control bar, 중앙 3D molecular viewer, 우측 evidence/delivery cards, 하단 ranked ligand review와 run queue로 구성한다.

시안에서 유지할 핵심 구조:

```text
- 좌측 nav: Dashboard, Project Intake, Runs, Review Board, 3D Viewer, Backmapping,
  H-Bond Evidence, Topology, Manifests, Reports, Settings
- 상단 bar: project selector, GPU runtime health, validated runner profile,
  run status, notification/help/user controls
- 중앙 viewer: protein surface + ligand/backmapped atom overlay + H-bond/interaction callouts
- 우측 evidence cards: topology fidelity, claim boundary, manifest signature,
  runner profile, H-bond confidence, uncertainty, force residual, delivery verdict
- 하단 tables: ranked ligand review, run queue/workers, manifest verification footer,
  GPU/RAM/disk/runtime utilization
```

제품 기준으로 수정할 점:

- Runtime 표기는 CPU/NVIDIA 중심이 아니라 AMD `ROCm/HIP/Rust` GPU runtime을 기본값으로 표시한다.
- clean-container 증거가 없을 때는 `RUNNING`/`READY`처럼 보이게 하지 않고 `blocked_clean_container_receipt_missing` 또는 `runtime evidence required`로 fail-closed 상태를 드러낸다.
- Runner profile selector는 `api/validated_runner.py` allowlist와 signed profile SHA256이 검증된 profile만 선택 가능하게 한다.
- 우측 evidence cards는 예쁜 summary가 아니라 실제 artifact field에 연결한다: `topology_fidelity`, `ligand_topology_valid`, `hbond_evidence_status`, `force_residual_applied`, `claim_safe`, `blocked_reason`.
- Delivery Verdict는 `product_claim_ready=false`이면 반드시 `internal review` 또는 `blocked`로 표시하고, clean ROCm/HIP/Rust receipt 전에는 external delivery 문구를 쓰지 않는다.
- 3D viewer callout은 H-bond distance/angle, ONSPS backmapped atoms, unsatisfied donor/acceptor, over-anchored decoy rejection evidence를 같은 schema에서 표시한다.

프론트엔드 구현 순서:

1. read-only evidence dashboard shell을 먼저 만든다.
2. `runs/ai_md_engine_kpi_report_current.json`, `runs/ai_md_product_evidence_bundle_current.json`, `runs/product_image_smoke_preflight_current.json`을 읽어 cards/table을 채운다.
3. run launch는 validated runner profile과 clean runtime gate가 연결된 뒤에만 enable한다.
4. 3D viewer는 PDB/SDF artifact download path와 manifest media metadata가 안정화된 뒤 연결한다.
5. 마지막에 queue/worker control을 붙인다. 외부 mutation, CASP submission, deployment action은 GUI에서 human-confirmed flow 없이는 실행하지 않는다.

## 바로 실행할 순서

지금 바로:

1. Product Docker에서 ROCm/HIP/Rust real runner가 깨지는지 확인
2. ROCm `torch` 및 Rust HIP product runtime dependency 정리
3. `/results` JSON/PDB 반환 수정
4. `job_store` lazy factory 수정
5. GitHub Actions product workflow green 확인

그다음:

6. `betelgeuze_engine` scaffold 추가
7. `TopologyFactory` facade화
8. `ProteinTopology`, `LigandTopology`, `ComplexTopology` 추가
9. ONSPS module 이동
10. H-bond evidence schema 추가

그다음:

11. force-term plugin 구조 추가
12. legacy LJ term adapter 추가
13. directional H-bond term 추가
14. hydrophobic term 추가
15. finite-difference/invariance test 추가

마지막으로:

16. top-K guarded force residual 추가
17. confidence/abstention 추가
18. pose/ranking/H-bond benchmark harness 추가
19. local PC runtime report 추가
20. product bundle evidence export 추가

## 다음 PR 제목 제안

```text
PR-3: Make product runtime execute real validated runners end-to-end
PR-4: Introduce betelgeuze_engine contracts and force-term scaffold
PR-5: Promote sequence/ligand topology to product validity gate
PR-6: Promote ONSPS 4-bead backmapping to directional interaction evidence
PR-7: Add guarded top-K force residual and physics validation tests
```

## 최종 방향

제품 껍데기는 좋은 방향으로 만들어져 있다. scope lock, validated runner, SQLite queue, signed manifest, security middleware는 상용제품 기반으로 적절하다.

이제 성공 조건은 제품 껍데기에서 제품 물리로 넘어가는 것이다.

```text
clean container에서 실제 product runner를 끝까지 green으로 만든 뒤,
topology, force terms, ONSPS evidence, guarded residual, benchmark를
제품 module로 승격한다.
```

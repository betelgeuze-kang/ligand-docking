# 리간드 도킹 및 분자동역학 납품 엔진

[English README](README.md)

이 저장소는 로컬 납품 방식의 분자동역학 및 리간드 검증 스택입니다. 핵심 방향은 물리 기반 `O(N)` 실행 경로, 제한된 AI residual 보정, 재현 가능한 게이트, 그리고 로컬 데이터는 노출하지 않으면서 검토 가능한 납품 산출물을 만드는 것입니다.

GitHub에는 소스코드, 설정, 테스트, 문서, 스키마, 납품 템플릿을 저장합니다. 분자동역학 실행 데이터와 무거운 로컬 산출물은 의도적으로 제외합니다.

## 저장소 구성

| 영역 | 역할 |
| --- | --- |
| `core/` | 물리 기반 MD 엔진 핵심 로직, integrator, topology, AI residual routing, spatial kernel, GPU/runtime 지원 코드입니다. |
| `rust_engine/` | Rust/HIP 가속 엔진 스캐폴딩과 native build 표면입니다. 빌드 결과물은 Git에서 제외됩니다. |
| `tools/` | 게이트, manifest, 납품 bundle, wetlab packet, evidence ledger, benchmark summary, 상용화 readiness를 만드는 CLI 도구입니다. |
| `tests/` | 엔진 동작, 납품 게이트, 검증 산출물, packet builder, regression guard에 대한 테스트입니다. |
| `config/` | target policy, calibration input, scorecard, acceptance threshold, runtime preset, gate 설정입니다. |
| `docs/` | 아키텍처 노트, 검증 계획, 로컬 납품 runbook, wetlab handoff 문서, 논문 초안, target-family roadmap입니다. |
| `docs/wetlab_packets/` | 파트너/실험팀 전달용 lightweight wetlab packet 템플릿과 CSV control 파일입니다. |
| `benchmark/` | 정확도 및 성능 benchmark entry point입니다. |
| `train/` | residual model training pipeline entry point입니다. |
| `api/`, `viewer/`, `deploy/`, `monitoring/` | 로컬 서비스, 시각화, 배포, 운영 모니터링 스캐폴딩입니다. |
| `requirements*.txt` | runtime, development, API, training, deployment, optional dependency를 나눈 파일입니다. |

## GitHub에 올리지 않는 것

`.gitignore`를 통해 아래 항목은 GitHub에 올라가지 않도록 제외했습니다.

- `data/`, `runs/`, `output/`, `logs/`, `models/`, `archives/`, `tmp/`, `runtime/cache/`
- `.env`, `.env.*`, 로컬 agent metadata, virtualenv, Python cache, test cache
- `*.so`, `*.dll`, `*.o`, Rust `target/`, 다운로드된 로컬 tool bundle 같은 build/native 산출물
- `*.h5`, `*.npz`, `*.pt`, `*.pth`, `*.onnx`, `*.tar.gz`, `*.tar.zst` 같은 대형 모델/배열/압축 산출물

즉 GitHub에는 재현 가능한 구현과 문서가 올라가고, 무거운 MD trajectory, 생성 dataset, local model checkpoint, 납품 output은 로컬에 남기는 구조입니다.

## 핵심 원칙

1. 기본 계산 경로는 `O(N)`을 유지합니다.
2. 속도를 위해 과학적 정확도를 희생하지 않습니다.
3. AI는 물리 엔진을 대체하지 않고, 제한된 residual 보정으로만 사용합니다.
4. provenance, wetlab evidence, queue 상태, 납품 gate가 불완전하면 fail-closed로 막습니다.
5. 생성된 evidence는 fingerprint와 provenance를 갖추고, 소스코드와 분리합니다.

## 빠른 시작

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

납품 게이트 관련 핵심 테스트만 빠르게 실행:

```bash
python3 -m pytest -q \
  tests/unit/test_build_local_delivery_verdict_gate.py \
  tests/unit/test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py \
  tests/unit/test_run_wetlab_tcruzi_pde_allatom_rescue.py
```

로컬 납품 verdict gate 실행:

```bash
python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py
python3 tools/build_local_delivery_verdict_gate.py
```

이 verdict gate는 필수 P0 evidence, wetlab 상태, delivery readiness 조건이 모두 충족되기 전까지 의도적으로 fail-closed 됩니다.

## 주요 워크플로우

| 워크플로우 | 주요 entry point |
| --- | --- |
| 로컬 납품 preflight | `tools/run_local_delivery_preflight.py`, `tools/build_local_delivery_bundle.py`, `tools/validate_local_delivery_bundle.py` |
| P0 납품 verdict | `tools/build_local_delivery_verdict_gate.py`, `docs/local_delivery_p0_gate.md`, `docs/local_delivery_verdict_template.md` |
| PDE rescue provenance | `tools/run_wetlab_tcruzi_pde_allatom_rescue.py`, `tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py` |
| 정확도 및 regression gate | `tools/validate_accuracy_gate.py`, `tools/check_strict_release_regression.py`, `benchmark/accuracy_bench.py` |
| nightly/local 운영 | `tools/run_nightly_screening_batch.py`, `tools/run_nightly_ops.sh` |
| 상용화 readiness | `tools/build_commercialization_readiness_report.py`, `tools/build_ligand_scaleup_suite_status.py`, local-delivery 문서, 생성된 verdict artifact |

## 로컬 납품 문서

납품 준비 상태를 볼 때는 아래 문서부터 보면 됩니다.

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_manifest_template.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/local_delivery_verdict_template.md`
- `docs/local_delivery_engine_provenance.md`
- `docs/local_delivery_claim_policy.md`
- `docs/post_green_improvement_plan.md`

## 현재 검증 스냅샷

업데이트: 2026-05-15 KST.

`runs/` 아래 runtime artifact는 로컬에만 남고 Git에서는 제외됩니다. 아래 표는 로컬에서 어떤 파일을 먼저 열어야 하는지와 현재 해석을 요약합니다.

| Lane | 현재 상태 | 주요 로컬 artifact | 먼저 볼 데이터 | 해석 |
| --- | --- | --- | --- | --- |
| 제한 로컬 납품 | Green | `runs/local_delivery_verdict_gate_current.json` | `delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0` | 제한된 납품 claim에 한해 delivery-ready입니다. |
| 납품 claim 경계 | Restricted | `docs/local_delivery_claim_policy.md` | `kinase,gpcr,ion_channel` | transporter, CA2/PXR, broad IDP, broad all-atom, broad platform, unattended decision-making은 claim 밖입니다. |
| 상용툴 정확도 parity | Blocked | `runs/accuracy_parity_scorecard_current.json` | `status=blocked_accuracy_parity` | broad commercial-tool parity는 아직 주장하지 않습니다. |
| family refresh 재현성 | Green | `runs/family_expansion_refresh_current.json` | `overall_ok=true`, `step_count=137`, `failed_count=0` | 현재 packet chain은 로컬에서 재현 가능합니다. |
| ligand scale-up suite | Tracked suite green | `runs/ligand_scaleup_suite_status_current.json` | `commercialization_ready_suite_count=3`, `pending_suite_ids=[]` | 제한된 scale evidence이며 broad discovery parity 주장은 아닙니다. |
| T. cruzi PDE translation | Blocked | `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json` | `candidate_pool_row_count=29568`, `energy_pass=16`, `core_pass=0` | wetlab/all-atom promotion은 차단 상태입니다. |
| T. cruzi PDE 다음 blocker | Blocked | `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json` | `atomized_ligand_draft=7/7`, `parameterization=0/7`, `local_minimization=0/7` | 좌표 초안은 있으나 상용 pose/local-min evidence는 없습니다. |

## T. cruzi PDE 데이터 흐름

현재 PDE 경로는 의도적으로 fail-closed입니다. 후보 확장, metric 진단, atomization, 상용 promotion evidence를 분리해 두었기 때문에 energy row가 좋아 보여도 geometry, stability, atomization, parameterization, local minimization이 닫히기 전에는 claim을 올리지 않습니다.

| 단계 | 로컬 artifact | 현재 데이터 | 읽는 법 |
| --- | --- | --- | --- |
| Translation evidence scan | `runs/wetlab_tcruzi_pde_translation_evidence_probe_current.json` | 후보 score row `29568`, energy-pass row `16`, unique energy-hit ligand `7`, core-pass ligand `0` | energy evidence는 있지만 energy + distance + stability를 동시에 닫은 row는 없습니다. |
| Translation quality gate | `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json` | `claim_promotion_allowed=false`, `candidate_pool_geometry_stability_blocked=true` | broad wetlab/all-atom promotion은 계속 blocked입니다. |
| Metric-scale diagnosis | `runs/wetlab_tcruzi_pde_metric_scale_gap_packet_current.json` | selected pseudo-allatom review row는 geometry/stability `4/4`를 유지하지만 energy `0/4`; 외부 homolog/BindingDB row는 energy `16`이나 geometry-stability/core `0` | blocker는 단순 compound 부족이 아니라 metric-scale과 pose-preservation split입니다. |
| Pose/backmapping closure queue | `runs/wetlab_tcruzi_pde_pose_backmapping_closure_queue_current.json` | unique energy-hit PDE seed `7`개 queue | 다음 측정값은 pose-preservation RMSD, backmapping consistency, local-minimization survival, replicate-pass fraction입니다. |
| Ligand atomization check | `runs/wetlab_tcruzi_pde_ligand_atomization_gap_packet_current.json` | `atomization_ready_count=0/7`; 현재 pseudo-backmap은 ligand atom `2`개, 예상 heavy atom `34-43`개 | 기존 pseudo-backmap은 all-atom ligand pose evidence로 취급하면 안 됩니다. |
| Atomized ligand draft | `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json` | RDKit all-atom draft `7/7`, pseudo-anchor orientation `6/7`, parameterization `0/7`, protein-ligand local minimization `0/7` | coordinate draft substep은 닫혔고, parameterization과 local minimization이 다음 상용 blocker입니다. |

고정 PDE hard threshold는 아래와 같습니다.

| Metric | Pass threshold |
| --- | ---: |
| `binding_energy_proxy` | `<= -0.55` |
| `mean_min_distance_A` | `<= 3.10 A` |
| `stability_score` | `>= 0.32` |

## 로컬 결과 데이터 읽는 법

artifact를 다시 만든 뒤에는 아래 명령으로 큰 trajectory payload 없이 핵심 summary field만 확인할 수 있습니다.

```bash
python3 - <<'PY'
import json
for path in [
    "runs/local_delivery_verdict_gate_current.json",
    "runs/accuracy_parity_scorecard_current.json",
    "runs/wetlab_tcruzi_pde_translation_quality_packet_current.json",
    "runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json",
]:
    data = json.load(open(path, encoding="utf-8"))
    print("\n##", path)
    for key, value in (data.get("summary", {}) or {}).items():
        if key in {
            "status",
            "delivery_ready",
            "verdict",
            "candidate_pool_row_count",
            "candidate_pool_energy_pass_count",
            "candidate_pool_core_pass_count",
            "atomization_draft_ready_count",
            "parameterization_ready_count",
            "protein_local_minimization_ready_count",
            "claim_promotion_allowed",
            "next_required_step",
        }:
            print(f"{key}: {value}")
PY
```

## 주장 범위

현재 사용할 수 있는 표현:

- selected family 기준의 제한 로컬 납품 분석 파이프라인은 green gate를 통과했습니다.
- T. cruzi PDE는 local evidence packet과 RDKit atomized ligand draft를 보유합니다.
- T. cruzi PDE commercial wetlab/all-atom promotion은 parameterization, protein-ligand local minimization, pose preservation, backmapping consistency, replicate evidence 전까지 blocked입니다.

아직 쓰면 안 되는 표현:

- broad commercial drug-discovery platform parity
- OpenMM, Schrodinger, GALAXY급 broad equivalence
- wetlab-proven T. cruzi PDE hit claim
- AQP1 functional surrogate row에서 직접 binding kcal claim

## 개발 및 저장 루틴

```bash
git status
python3 -m pytest -q <관련 테스트>
git add <변경한 source/docs/tests>
git commit -m "변경 내용 요약"
git push
```

push 전에 생성된 MD 데이터, checkpoint, log, local delivery output이 staged 되지 않았는지 확인하는 흐름을 유지하면 됩니다.

## 현재 GitHub 저장 상태

현재 GitHub에는 로컬 납품 workflow를 재현하는 데 필요한 구현, 테스트, 설정, 문서가 올라가 있습니다. 실행 데이터는 설계상 로컬에 남습니다. 파트너나 리뷰어에게 evidence package를 전달해야 할 때는 raw trajectory나 model output을 커밋하지 말고, 로컬에서 delivery bundle을 생성한 뒤 검토된 산출물만 공유하는 방식이 안전합니다.

현재 제한 로컬 납품 범위의 delivery status는 green입니다. verdict gate는 `summary.delivery_ready=true`와 clear commercialization queue를 보고합니다. delivery-ready package를 공유하기 전에는 제한 로컬 납품 bundle을 다시 만들고 `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`로 bundle fingerprint까지 확인합니다.

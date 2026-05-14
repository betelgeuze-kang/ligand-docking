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

### 현재 P0 메모

- 상용툴 대비 현재 수준은 제한된 로컬 납품형 분석 서비스 기준으로는 delivery-ready 수준까지 올라왔지만, wetlab selected-allatom translation/commercial hard gate 때문에 현재 추적 중인 상용화 accounting은 다시 fail-closed입니다. 풀 상용 플랫폼 claim, broad transporter/CA2/PXR/IDP 확장, unattended decision-making, broad all-atom/structure validation은 여전히 별도 claim review 대상입니다.
- `runs/local_delivery_verdict_gate_current.json`는 현재 `delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0`, `commercialization_queue_clear=true`를 보고합니다. `accuracy_gate`, requirements/environment lock, 최신 GPU/HIP nightly top-level smoke(`2026-05-13_goal_closure2`), 그리고 wetlab selected-allatom(`mean_min_distance_A=2.120 <= 2.500`)이 green입니다.
- 단, 위 wetlab selected-allatom green은 제한된 metric evidence 범위입니다. 현재 all-atom commercial review는 `commercial_hard_gate_pass_v2=false`이며, translation evidence probe에서 `29568`개 후보 score row 중 `binding_energy_proxy <= -0.55` 통과 row는 3-bead rescore, GPU ADRESS rescue, contact-aware GPU rescue, BindingDB similarity-seed screen 포함 `16`개지만 unique ligand는 `7`개이고, geometry/stability까지 동시에 통과한 core ligand는 `0`개입니다. 이 후보들은 homolog/similarity 기반 candidate-pool expansion evidence이므로 broad wetlab/all-atom promotion은 계속 금지됩니다.
- `runs/wetlab_tcruzi_pde_metric_scale_gap_packet_current.md`는 현재 PDE blocker를 `blocked_metric_scale_split`으로 분류합니다. selected pseudo-allatom review row는 geometry/stability가 `4/4`로 유지되지만 energy-pass는 `0/4`이고, 외부 homolog/BindingDB row는 energy hit `16`개를 만들었지만 geometry-stability/core pass는 `0`개입니다. 다음 closure는 claim promotion이 아니라 all-atom-style pose preservation/backmapping 및 local-minimization normalization입니다.
- `runs/wetlab_tcruzi_pde_pose_backmapping_closure_queue_current.md`는 이 closure를 unique energy-hit PDE seed `7`개 실행 큐로 구체화합니다. 필수 측정값은 pose-preservation RMSD, backmapping consistency, local-minimization survival, replicate-pass fraction이며, 큐는 claim-locked 상태로 고정 energy/distance/stability threshold를 유지합니다.
- `runs/wetlab_tcruzi_pde_ligand_atomization_gap_packet_current.md` 기준으로 이 `7`개 seed는 아직 ligand atomization blocked입니다. 현재 pseudo-backmap ligand atom은 `2`개뿐인데 SMILES 기준 예상 heavy atom은 `34-43`개라 `0/7`만 atomization-ready입니다. 상용 pose-preservation/local-minimization claim 전에는 화학적으로 충실한 all-atom ligand coordinates/parameters가 필요합니다.
- `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.md`는 RDKit all-atom ligand draft를 `7/7`개 생성했고, 이 중 `6/7`개를 기존 two-point pseudo anchor에 방향 정렬했습니다. 다만 이는 coordinate draft substep만 닫은 것이며 ligand parameterization과 protein-ligand local minimization은 아직 `0/7`이라 promotion은 계속 blocked입니다.
- `commercialization_status_report.md`는 현재 `all_tracked_commercialization_accounting_closed=false`, `platform_accounting_closed=false`, `local_engine_queue_clear=false`를 보고합니다. transporter placeholder rows는 `0`이고 CA2/PXR review-only policy closure는 허용되지만, wetlab selected-allatom translation/commercial hard gate가 다시 fail-closed 상태라 delivery claim을 넓히지 않습니다.
- `/goal` 이후의 다음 active lane은 상용툴 정확도 parity입니다. `runs/accuracy_parity_scorecard_current.md`는 아직 `blocked_accuracy_parity`이고, `runs/gpcr_a1_accuracy_repair_queue_current.md`는 `a1_accuracy_repair_queue_cleared_claim_locked`입니다. `guarded_100k_claim_review_rerun` metric은 통과했고 `runs/gpcr_a1_independent_repeat_packet_current.md`는 `independent_repeat_ready_claim_locked` 상태로 validate-only가 통과했지만, 독립 반복 본 실행과 broader scorecard closure 전까지 claim promotion은 금지됩니다.
- ligand scale-up suite는 현재 `commercialization_ready_suite_count=3/3`, `pending_suite_ids=[]`입니다. 1M blind package는 `set3_operational_smoke`, `set1_core_blind`, `set2_expanded_ood`가 모두 pass이고, 주요 PR-AUC는 `gpcr_core_full=0.8958`, `ion_trpv1_chembl20_full=0.9585`, `kinase_core_full=1.0000`, `gpcr_chembl50_full=0.8093`, `ion_trpv1_chembl50_full=0.9867`, `kinase_strict_full=1.0000`입니다.
- 1M guardrail 상태는 `claim_safe_size_shift_speed_diagnostic`입니다. 즉 정확도/품질 guardrail은 claim-safe이고, throughput claim은 equal-size speedpack A/B가 담당하며 1M speed는 scale evidence/진단값으로 둡니다.
- 최신 focused 테스트는 nightly gate discovery, keep-green trend, commercialization status reporting, AQP1 functional kcal surrogate/negative evidence gates, transporter negative closure, platform gap taxonomy, local verdict, ligand scale-up regression 범위를 포함합니다.
- 다음 단계는 `python3 tools/build_local_delivery_bundle.py`와 `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`를 다시 돌려 번들 fingerprint까지 green인지 확인하는 것입니다.
- `transporter` negative-evidence lane은 accounting closure 상태지만 `restricted local-delivery scope` 밖에 둡니다. AQP1 kcal은 functional IC50-derived surrogate로만 쓰고 direct binding kcal claim은 금지합니다.
- `fake-pass`, threshold relaxation, `수동 pass`, `delivery-ready` 문구는 verdict gate와 bundle validator가 둘 다 green일 때만 사용합니다.

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

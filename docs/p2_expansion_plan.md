# P2 · 확장·신뢰도 작업계획표

작성일: 2026-06-06 KST  
상태: **CLOSED** (2026-06-06)  
선행: [P0/P1 closure](p0_p1_closure_plan.md) **CLOSED** — PR [#2](https://github.com/betelgeuze-kang/ligand-docking/pull/2)  
범위: 상용 신뢰도·운영 속도를 올리는 **P2(확장·신뢰도)**. P0/P1에서 제외된 항목 + D4 잔여(Docker runtime) 포함.  
제외: CAMEO 등록/이메일 발송, CA2/PXR/transporter claim 확대, wetlab 실행, broad platform wording (→ post-P0 expansion queue).

---

## 0. 요약

| ID | 병목 | 목표 상태 | 분류 |
|----|------|-----------|------|
| P2-1 | 로컬 데이터 lifecycle (repo 인접 ~52G: `runs` 30G, `data` 12G, `models` 6G, `casp17` 4G) | keep/archive/externalize/delete 분류 + approval-gated 실행 | 운영 |
| P2-2 | 외부 해석가능 metric 부재 (DockQ, LDDT-PLI, MolProbity 등) | restricted scope용 공개 scorecard surface + 테스트 | 신뢰도 |
| P2-3 | 상태보고 자기참조 (`commercialization_status_report` green ≠ 코드 게이트) | 리포트가 pytest/API smoke에서 재생성·검증됨 | 메타 |
| P2-4 | Docker runtime 미검증 (P1 D4 잔여) | `docker build` + compose smoke green | 배포 |

처리 순서: **F(데이터) → G(metric) → H(리포트) → I(Docker)**  
(F가 끝나야 G/H 검증용 artifact 경로가 안정되고, I는 독립 병렬 가능)

---

## Phase F — P2-1: 데이터 lifecycle & externalize

**문제**: 대용량 산출물이 repo/worktree 인접에 남아 iteration·백업·협업을 느리게 함. cleanup CLI는 **읽기 전용**이며 `externalize_executed=false` 고정.

**현재 자산**
- `betelgeuze-cleanup` CLI — approval/payload artifact 읽기만
- `tools/cleanup/apply_runs_cleanup_manifest.py` — manifest apply (operator gate 필요)
- `tools/accounting/build_runs_cleanup_manifest.py`, `build_transition_cleanup_manifest.py`

### 작업
- [x] F1. **Inventory**: `runs/`, `data/`, `models/`, `casp17/` top-level 용량·파일수·중복(trajectory frame vs final PDB) 스냅샷을 `runs/p2_data_lifecycle_inventory_current.json`으로 고정.
- [x] F2. **Manifest v1**: 각 경로를 `keep | archive | externalize | delete | review`로 분류. 최소 keep: final PDB/mmCIF, representative model, sha256 manifest, validation report, viewer index.
- [x] F3. **Protected rows**: ligand-heavy / wetlab / delivery bundle 경로는 `protected-policy` gate 연동 (`betelgeuze-cleanup protected-policy` artifact 확인).
- [x] F4. **Externalize target**: 1차 후보 — `runs/archive/`, `casp17/massivefold_external_pool_intake/`(있다면), 반복 `stage2_traj_frames`, `rust_engine/target/`, `.venv/`(로컬만).
- [x] F5. **Dry-run apply**: `dry_run_p2_data_lifecycle.py` + snapshot artifact 생성. `externalize_executed=false` until operator approval token.
- [x] F6. **Postcheck**: externalize 후 repo/worktree 크기 before/after, keep 목록 checksum 유지 확인 (`build_p2_data_lifecycle_postcheck.py`).

### 수용 기준
- Manifest JSON + human-readable MD 존재.
- delete/externalize **실행 전** approval dossier + payload lock green.
- Git 추적 파일 수/용량 변화 없음(로컬 데이터만 이동).

### 검증
```bash
betelgeuze-cleanup snapshot-preflight --root .
betelgeuze-cleanup approval-gate --root .
python3 tools/cleanup/apply_runs_cleanup_manifest.py --dry-run --manifest runs/runs_cleanup_manifest_current.json
du -sh runs data models casp17
```

> **R4 게이트**: `externalize`/`delete`/`archive` 실제 실행은 operator approval 후에만.

---

## Phase G — P2-2: 외부 해석가능 metric surface

**문제**: 영업/투자자/파트너가 검증하기 어려운 내부 gate-only metric. CASP17 쪽에 DockQ/LDDT 언급은 있으나 **제품 scorecard에 통합 surface 없음**.

**Claim boundary (고정)**
- metric은 **restricted local-delivery scope** (`kinase`, `gpcr`, `ion_channel`) 비교·회귀용.
- OpenMM/Schrödinger급 parity claim 금지 (P0-2 claim guard 유지).

### 작업
- [x] G1. **Metric contract**: `docs/p2_external_metric_contract.md` — 입력(pose PDB, native, interface definition), 출력(DockQ proxy, LDDT-PLI, MolProbity clashscore), fail-closed 규칙.
- [x] G2. **Scorecard builder**: `tools/product/build_external_metric_scorecard.py` + `benchmark/external_metric_scorecard.py` — 기존 `build_accuracy_parity_scorecard`와 분리된 P2 surface.
- [x] G3. **DockQ / LDDT-PLI**: complex/ligand pose set에 대해 batch runner + `runs/external_metric_scorecard_current.json` 출력. CASP17 win-tier dashboard row schema 재사용 검토.
- [x] G4. **MolProbity**: structure quality (clashscore, Ramachandran outliers) — all-atom/exported PDB subset only; placeholder topology 산출물 제외 (`topology_fidelity=placeholder_alanine` gate).
- [x] G5. **API/CLI exposure**: `betelgeuze-product external-metrics` + `/product/external-metrics` — read-only status JSON.
- [x] G6. **Tests**: fixture PDB 1~2건 golden threshold; placeholder fidelity 산출물은 scorecard에 **blocked** row.

### 수용 기준
- Scorecard JSON에 `metric_family`, `claim_scope`, `topology_fidelity`, `pass|blocked|missing` per row.
- `claim_promotion_allowed=false` unless restricted-scope thresholds met (explicit in summary).
- Unit tests green for contract + blocked placeholder path.

### 검증
```bash
python3 -m pytest -q tests -k "external_metric or dockq or molprobity or lddt"
betelgeuze-product public-benchmark --root .  # after G5 wiring
```

---

## Phase H — P2-3: 상태보고 fidelity (메타-병목)

**문제**: `commercialization_status_report.md`(.gitignore)가 스스로 green/closed를 주장. P0/P1에서 코드 게이트는 맞췄으나 **리포트 ↔ 런타임 재검증 루프** 없음.

### 작업
- [x] H1. **Source of truth split**:  
  - *Generated*: `runs/commercialization_readiness_current.json`, scorecard packets  
  - *Human index*: `docs/commercialization_status_summary.md` (짧은 요약만, git 추적)
- [x] H2. **Regeneration chain**: `tools/accounting/build_commercialization_readiness_report.py` → report MD는 **항상** JSON packet에서 derive; hand-edit 금지 CI check.
- [x] H3. **Parity test**: `tests/unit/test_commercialization_report_parity.py` — report summary fields ⊆ `{pytest smoke, api import, simulate scope, claim guard}` 실측 결과.
- [x] H4. **Meta gate**: `top_blocker_family=none_*` 주장 시 `api/simulation_scope.py`, `core/claim_boundary.py`, P0/P1 tests pass를 전제조건으로 assert.

### 수용 기준
- Hand-written green claim 없음; JSON packet + test가 single path.
- Parity test CI에서 fail-closed.

### 검증
```bash
python3 -m pytest -q tests/unit/test_commercialization_report_parity.py
python3 tools/accounting/build_commercialization_readiness_report.py --out-json runs/commercialization_readiness_current.json
```

---

## Phase I — P2-4: Docker runtime 검증 (P1 D4 잔여)

**문제**: `Dockerfile.product`는 package install로 갱신됐으나 dev 환경에 docker CLI 없어 runtime build 미실행.

### 작업
- [x] I1. **Local/CI build script**: `deploy/verify_product_image.sh` — build, `betelgeuze-product --help`, `curl /simulate` 422 (no profile), optional health.
- [x] I2. **GitHub Actions job** (optional): `.github/workflows/product-image-smoke.yml` — push to branch 시 build only.
- [x] I3. **compose smoke**: `deploy/docker-compose.product.yml` + env example; worker + server same image.

### 수용 기준
- `docker build -f Dockerfile.product .` success (환경에 docker 있을 때).
- Container内 `python -c "import api.main"` + CLI `--help`.

### 검증
```bash
bash deploy/verify_product_image.sh
docker compose -f deploy/docker-compose.product.yml config
```

---

## 의존성

```
P0/P1 CLOSED ──▶ F(데이터 manifest)
                      │
                      ▼
                 G(metric scorecard) ──▶ H(report parity)
                      │
                      └──────────▶ I(Docker)  [parallel OK]
```

| Phase | 규모 | 위험 | 비고 |
|-------|------|------|------|
| F | 1~2일 | **R4** (externalize/delete) | approval 필수 |
| G | 2~4일 | R2~R3 | claim boundary 엄수 |
| H | 0.5~1일 | R2 | test-only, no external state |
| I | 0.5~1일 | R2 | CI/docker daemon 필요 |

---

## 전역 수용 기준 (P2 닫힘 정의)

- [x] `runs/p2_data_lifecycle_inventory_current.json` + cleanup manifest v1 존재; externalize dry-run green.
- [x] External metric scorecard JSON + tests; placeholder topology rows blocked.
- [x] Commercialization report parity test green; no self-referential green without code gate.
- [x] `deploy/verify_product_image.sh` (or CI) documents successful product image build.

---

## P2 이후 (P3 후보 — 본 계획 제외)

| Lane | 출처 | 비고 |
|------|------|------|
| CAMEO registration & receiver | `docs/cameo_transition_prd.md` | outbound email, result fetcher |
| B2B pilot packaging | `구현` | ligand HTVS + local delivery 파일럿 |
| Science expansion | `docs/post_p0_commercial_expansion_queue.md` | GPCR CI-low, transporter direct binding |
| Tools batch3 migration | `docs/improvement_items_remaining_work.md` §13~14 | batch2 이후 잔여 |

---

## 즉시 착수 (Phase F1)

```bash
# 1) 용량 스냅샷 (readonly)
du -sh runs data models casp17 archives rust_engine/target .venv 2>/dev/null | sort -rh

# 2) cleanup readiness (readonly)
betelgeuze-cleanup all --root .

# 3) existing manifest builders (readonly)
python3 tools/build_runs_cleanup_manifest.py --help
python3 tools/build_transition_cleanup_manifest.py --help
```

다음 커밋 단위: **F1 inventory JSON** → **F2 manifest v1** → operator review → F5 dry-run.

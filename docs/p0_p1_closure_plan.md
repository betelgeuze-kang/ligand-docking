# P0 · P1 병목 해소 코드구현 작업계획표

작성일: 2026-06-06 KST
범위: 독립기능 → 상용제품 전환을 막는 **P0(제품 차단)·P1(속도 차단)** 병목만 다룬다. P2(확장·신뢰도)는 본 계획에서 제외.
근거: 실측(`api/tasks.py`, `api/validated_runner.py`, `core/topology.py`, `tools/`, `git status`, `pyproject.toml`).

---

## 0. 요약

| ID | 병목 | 목표 상태 | 분류 |
|----|------|-----------|------|
| P0-1 | 범용 실행 경로 부재 (`/simulate` 일반 MD = NotImplementedError) | 제품 scope를 ligand 경로로 명시 락 + API 계약 정합 | 차단 |
| P0-2 | 과학 엔진 placeholder (전 residue Alanine, AdResS simplified) | claim 경계 코드/스키마로 강제, 범용 MD claim 차단 | 차단 |
| P1-3 | 코드 비대 (`api/product.py` 9,353줄 = API 76%, `tools/build_*` 1,187개) | 회계 surface를 제품 코드에서 격리 | 속도 |
| P1-4 | Git 위생 (워킹트리 1,548개 미커밋) | 클린 트리 + 의미단위 커밋 + CI 게이트 | 속도 |
| P1-5 | 패키징 경계 불일치 (CLI가 비패키징 `tools/`에 shell-out 의존) | 런타임 의존 고정 + 설치형 검증 | 속도 |

처리 순서(의존성 기준): **P1-4 → P0-1 → P0-2 → P1-5 → P1-3**
(먼저 트리를 정리해야 이후 변경이 리뷰 가능해지고, scope 락(P0)을 먼저 해야 패키징/격리(P1-5/P1-3)의 경계가 확정된다.)

---

## Phase A — P1-4: Git 위생 복구 (선결)

**문제**: 워킹트리에 1,548개 미커밋 변경 (`tools/` 한정 modified 646 + untracked 125 포함). 리뷰·릴리스·롤백 불가.

### 작업
- [x] A1. 현재 변경을 카테고리 분류: `code(api/core/betelgeuze_*)`, `accounting(tools/build_*, runs/, *_packet_current.md)`, `state(.betelgeuze/trace.jsonl)`, `data(대용량)`.
- [x] A2. `.betelgeuze/trace.jsonl`, `runs/**`, 대용량 산출물이 `.gitignore`에 있는지 확인하고 누락분 추가. 추적 중인 생성 아티팩트는 `git rm --cached`로 인덱스에서 제외(파일 보존).
- [ ] A3. 코드 변경(`api/`, `core/`, `betelgeuze_*`)을 의미단위로 분리 커밋.
- [ ] A4. `tools/build_*` 자동생성 변경은 Phase D 격리 전까지 별도 커밋으로 묶어 일단 트리를 클린화.
- [ ] A5. `git status --short | wc -l` 결과를 0(또는 의도된 ignore만 남김)으로 만든다.

### 산출물 / 수용 기준
- `git status` 클린(또는 ignored만 dirty).
- `.gitignore`에 `runs/`, `.betelgeuze/trace.jsonl`, 생성형 packet 경로 포함.
- 커밋 로그가 카테고리별로 분리되어 있음.

### 검증
```bash
git status --short | wc -l        # 0 목표
git check-ignore runs/ .betelgeuze/trace.jsonl
```

> 안전 게이트: `git rm --cached`, `.gitignore` 변경은 사용자 확인 후 실행. `git add .` / force 금지.

---

## Phase B — P0-1: 실행 경로 정합 (제품 scope 락)

**문제**: `/simulate` 일반 경로는 `NotImplementedError`(`api/tasks.py:54`). 실제 제품 경로는 `validated_runner`의 allowlist 2개 스크립트뿐(`api/validated_runner.py:17`). 계약과 실제가 불일치.

### 결정사항(고정)
제품 = **ligand HTVS + backmapping scoring 로컬 분석 패키지**. "범용 MD 시뮬레이션 엔진" claim은 비제품.

### 작업
- [x] B1. `/simulate` 요청 모델(`api/models.py`)에서 `runner_profile_id`를 1급 필드로 승격하고, profile 미지정 generic 경로는 명시적 `400 Unsupported`로 응답(조용한 `NotImplementedError` 대신).
- [x] B2. `api/tasks.py`의 generic 분기 정리: `pdb_content`/`pdb_id` 일반 MD 경로는 "지원하지 않음 + 사유" 구조화 응답으로 대체. 가짜 결과 거부 로직은 유지.
- [x] B3. allowlist 러너 프로파일(`run_ligand_htvs_pipeline.py`, `run_ligand_backmapping_scoring.py`)에 대한 **end-to-end smoke 테스트** 추가: 프로파일 로드 → 실행 → `runner_result.json` + sha256 + status=completed 검증.
- [x] B4. OpenAPI/`README` API 섹션을 ligand 경로 중심으로 수정. 일반 MD 엔드포인트 약속 제거.
- [x] B5. `/simulate` → `/status/{job_id}` → `/results/{job_id}` 해피패스 통합 테스트 1건.

### 산출물 / 수용 기준
- generic 경로 요청 시 구조화된 4xx(사유 포함), 500/예외 누출 없음.
- ligand 2경로 smoke 테스트 green.
- API 문서에 범용 MD claim 부재.

### 검증
```bash
python3 -c "import api.main"
python3 -m pytest -q tests -k "runner or simulate or validated" 2>&1 | tail
```

---

## Phase C — P0-2: 과학 claim 경계 강제

**문제**: `core/topology.py:45-47` 전 residue Alanine placeholder, `:84/:104/:167` AdResS/all-atom "simplified/placeholder". 범용 MD 정확도 claim 불가.

### 작업
- [x] C1. `core/topology.py`의 placeholder 지점에 **claim-scope 가드** 추가: 실제 residue 매핑이 주입되지 않은 경우 결과 객체/매니페스트에 `topology_fidelity="placeholder_alanine"` 플래그를 강제 기록.
- [x] C2. 결과 매니페스트 스키마(`api/result_manifest.py`)에 `claim_scope` / `fidelity` 필드를 필수화하고, placeholder fidelity인 산출물은 "general-MD-accuracy" 등급으로 승격 불가하도록 게이트.
- [x] C3. 사용자/영업 노출 표면(README, viewer, product CLI 출력)에서 정확도 문구를 `restricted local-delivery scope`로 제한하는 텍스트 가드(상수/검사) 추가.
- [x] C4. placeholder 경계를 검증하는 단위 테스트: 매핑 미주입 시 fidelity 플래그가 반드시 세팅됨을 단언.

### 산출물 / 수용 기준
- placeholder topology 산출물이 절대 "범용 정확" 등급으로 표기되지 않음(테스트로 강제).
- 매니페스트에 fidelity/claim_scope 필수 필드 존재.

### 검증
```bash
python3 -m pytest -q tests -k "topology or manifest or claim or fidelity" 2>&1 | tail
```

---

## Phase D — P1-5: 패키징 경계 정리

**문제**: `pyproject.toml`은 `betelgeuze_product/cameo/cleanup` 3개 CLI만 패키징. CLI가 비패키징 `tools/`·`core/`에 shell-out/import 의존 → 설치형/온프렘 배포 시 깨질 수 있음.

### 작업
- [x] D1. 3개 CLI가 실제로 의존하는 `tools/`·`core/`·`api/` 자산 목록 추출(import + subprocess 호출 grep).
- [x] D2. 제품 런타임에 필요한 최소 모듈을 패키지 포함 대상으로 승격하거나, 명시적 런타임 의존(엔트리포인트/리소스 경로 상수)으로 고정.
- [x] D3. 클린 venv에서 `pip install .` 후 3개 콘솔 스크립트(`betelgeuze-product`, `betelgeuze-cameo`, `betelgeuze-cleanup`) `--help` 및 1개 dry-run 실행 검증.
- [ ] D4. `Dockerfile.product` / `docker-compose.product.yml`로 동일 검증(설치형 이미지에서 CLI 동작).

### 산출물 / 수용 기준
- 클린 환경 `pip install .` 후 3개 CLI 정상 기동 + dry-run 성공.
- 누락 런타임 의존 0.

### 검증
```bash
python3 -m venv /tmp/p1_5 && /tmp/p1_5/bin/pip install . \
  && /tmp/p1_5/bin/betelgeuze-product --help \
  && /tmp/p1_5/bin/betelgeuze-cameo --help \
  && /tmp/p1_5/bin/betelgeuze-cleanup --help
```

---

## Phase E — P1-3: 회계 surface 격리

**문제**: `api/product.py` 9,353줄(API의 76%, 함수 14개 = 초대형 함수)이 `*_placeholder_count` 등 상태/회계 코드. `tools/build_*` 1,187개가 일회성 packet 생성기(타깃당 다수). 제품 로직보다 상태 기계가 큼.

### 작업
- [x] E1. `api/product.py`를 책임별 모듈로 분해: `product_api(엔드포인트 핸들러)` vs `product_accounting(status/placeholder 집계)` 분리. 동작 동일(behavior-preserving) 리팩토링.
- [x] E2. `tools/build_*` 생성기를 별도 네임스페이스(`tools/accounting/` 또는 `reporting/`)로 이동하고, 출력은 `.gitignore` 처리된 생성 디렉토리로 보낸다(소스만 추적).
- [x] E3. 타깃별 중복 생성기(예: `build_alk2_*` 5종)는 파라미터화된 단일 생성기 + 타깃 설정으로 통합(가능한 것부터 점진).
- [x] E4. 격리 후 `api/product.py` 라인수와 `tools/` 추적 파일수 before/after를 기록.

### 산출물 / 수용 기준
- 엔드포인트 동작 불변(기존 product 관련 테스트 green).
- `api/product.py` 핸들러/회계 분리, 단일 파일 크기 대폭 감소.
- 생성형 산출물이 git 추적에서 제외.

### 검증
```bash
python3 -c "import api.main"
python3 -m pytest -q tests -k "product or accounting or commercial" 2>&1 | tail
git status --short | wc -l   # 생성물 누출 없음 확인
```

> 주의: E1/E3은 R2~R3(다파일·동작 영향). behavior-preserving 단위로 쪼개고 각 단계마다 테스트.

---

## 의존성 / 일정 가이드

```
A(git 정리) ──▶ B(P0-1 scope락) ──▶ C(P0-2 claim가드)
                     │                     │
                     └────────┬────────────┘
                              ▼
                     D(P1-5 패키징) ──▶ E(P1-3 격리 리팩토링)
```

| Phase | 규모(거칠게) | 위험 | 비고 |
|-------|------|------|------|
| A | 0.5~1일 | 중 | git rm --cached/ignore는 확인 게이트 |
| B | 1~2일 | 중 | API 계약·테스트 |
| C | 1~2일 | 중 | 스키마 필수필드 추가 |
| D | 0.5~1일 | 저 | 설치형 검증 |
| E | 3~5일+ | 고 | 대형 리팩토링, 점진 분해 |

---

## 전역 수용 기준 (P0·P1 닫힘 정의)

- [ ] `git status` 클린, 생성 아티팩트 미추적. *(partial: ignore + untrack done; legacy WIP remains)*
- [x] `/simulate` generic 경로가 구조화 4xx, ligand 2경로 smoke green, API 문서에 범용 MD claim 없음.
- [x] placeholder topology 산출물이 매니페스트에서 general-accuracy 등급 승격 불가(테스트 강제).
- [x] 클린 venv `pip install .` 후 3개 CLI 기동.
- [x] `api/product.py` 핸들러/회계 분리, 기존 product 테스트 green.
- [x] `commercialization_status_report.md`의 "closed/green"이 실제 실행경로·claim 가드와 정합(메타-병목 해소). *(코드 경로 정합; report file itself is generated/local)*

상세: `docs/p0_p1_closure_status.md`

## 비고

- 본 계획은 **코드 구현 작업표**이며, 실제 착수 시 Phase 단위로 별도 커밋/검증.
- 안전 게이트(P1-4의 git 인덱스 조작, P1-5의 설치형 변경)는 실행 전 확인.
- P2(데이터 externalize, DockQ/MolProbity 등 외부 metric, 상태보고 자기참조성 일부)는 후속 계획에서 다룬다.

# CI Verification Checklist (PRs #7-#12)

Purpose: track tests added/modified and CI runner verification steps for the product docking pipeline hardening sequence (PRs #7 through #12).

## Test Inventory by PR

| PR | Title | New Test Files | Modified Test Files | New Modules |
|----|-------|---------------|--------------------:|-------------|
| #7 | Add encrypted private payload at-rest store + fix dispatcher outbox event | `tests/unit/test_private_payload_store.py` (17 tests) | `tests/unit/test_api_job_store.py` (+3 outbox tests) | `betelgeuze_product/private_payload_store.py` |
| #8 | Slim/group docking API response; repair contract analyzer | `tests/unit/test_product_docking_response_contract.py` (8 tests) | `tests/unit/test_build_product_api_contract.py` (fixed assertions) | `betelgeuze_product/docking_response.py` |
| #9 | Document docking state machine, runner modes, payload security, release ladder | -- | -- | -- (docs only) |
| #10 | Add release claim evidence-ladder decision gate | `tests/unit/test_build_release_claim_evidence_ladder_gate.py` (8 tests) | -- | `tools/product/build_release_claim_evidence_ladder_gate.py` |
| #11 | Wire encrypted private payload store into submit + materialization (end-to-end) | `tests/unit/test_docking_private_payload.py` (9 tests) | `tests/unit/test_docking_pipeline_hardening.py` (+3 materializer tests) | `betelgeuze_product/docking_private_payload.py` |
| #12 | Structure docking reasons into reason_code + reason_detail | `tests/unit/test_structured_reason.py` (10 tests) | `tests/unit/test_docking_pipeline_hardening.py` (+2 structured reason tests) | `betelgeuze_product/structured_reason.py`, `betelgeuze_product/docking_materialization_errors.py` |

## CI Self-Hosted Runner Verification Checklist

Commands the runner should execute (Python 3.11, deps from `requirements.txt` + `requirements-api.txt`):

### 1. Syntax validation (py_compile)

```bash
python3 -m py_compile betelgeuze_product/private_payload_store.py
python3 -m py_compile betelgeuze_product/docking_response.py
python3 -m py_compile betelgeuze_product/docking_private_payload.py
python3 -m py_compile betelgeuze_product/structured_reason.py
python3 -m py_compile betelgeuze_product/docking_materialization_errors.py
python3 -m py_compile tools/product/build_release_claim_evidence_ladder_gate.py
```

### 2. Lint (ruff)

```bash
ruff check betelgeuze_product/ tools/product/ api/
```

### 3. Unit tests (pytest)

```bash
python3 -m pytest tests/unit/test_private_payload_store.py -q
python3 -m pytest tests/unit/test_api_job_store.py -q
python3 -m pytest tests/unit/test_product_docking_response_contract.py -q
python3 -m pytest tests/unit/test_build_product_api_contract.py -q
python3 -m pytest tests/unit/test_build_release_claim_evidence_ladder_gate.py -q
python3 -m pytest tests/unit/test_docking_private_payload.py -q
python3 -m pytest tests/unit/test_docking_pipeline_hardening.py -q
python3 -m pytest tests/unit/test_structured_reason.py -q
```

### 4. Profile validation

```bash
python3 -m pytest tests/unit/ -k "profile" -q
```

### 5. Worker smoke

```bash
python3 -m pytest tests/unit/ -k "worker_smoke or worker" -q
```

## GPU / Runtime-Only Verification

The following require the ROCm self-hosted runner and are **not** part of the standard `product-api-worker.yml` workflow:

- Restricted-production HTVS profile tests (require GPU acceleration)
- ROCm image build (`Dockerfile.product` with `product-image-smoke.yml`)

# OpenCode Worker Slice: Product ROCm Requirements And CI Audit

## Goal

Audit the current uncommitted Docker/requirements/GitHub Actions product-runtime changes and apply only a narrow fix if required.

The product lane must remain ROCm/HIP/Rust-first. CPU PyTorch may exist for local/default development requirements, but it must not be pulled into the product ROCm container path or unlock product readiness.

## Scope

- Inspect current uncommitted changes in:
  - `Dockerfile.product`
  - `.github/workflows/product-image-smoke.yml`
  - `requirements-base.txt`
  - `requirements.txt`
  - `requirements-rocm.txt`
  - `requirements-product-rocm.txt`
  - `tools/product/build_product_image_smoke_preflight.py`
  - `tests/unit/test_product_runtime_reality.py`
- Check the referenced plan in `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`, especially P0-1 and P0-4.
- Verify that `requirements-rocm.txt` does not include the CPU `requirements.txt`/`torch==2.6.0` path.
- Verify that the product Dockerfile copies the split requirement files and installs the ROCm product profile.
- Verify that the product-image workflow triggers when the new requirements file changes.
- If a narrow issue is found, patch it and update focused tests.

## Boundaries

- Web access: disabled.
- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not commit, stage, push, delete, deploy, publish, or mutate external state.
- Do not broaden into engine refactors, runner rewrites, or CI settings outside this product image smoke lane.
- Docker is likely unavailable locally; do not treat lack of a local Docker daemon as a reason to weaken the ROCm/HIP/Rust gate.

## Suggested Verification

Run:

```bash
python3 -m py_compile tools/product/build_product_image_smoke_preflight.py
python3 -m pytest -q tests/unit/test_product_runtime_reality.py tests/unit/test_build_product_image_smoke_preflight.py
python3 tools/product/build_product_image_smoke_preflight.py
git diff --check
```

If you touch workflow syntax, run the repo's existing lightweight verification if it is cheap:

```bash
./scripts/ai-verify.sh
```

## Return Summary

Return only:

- changed files
- whether any issue was found
- tests run and pass/fail
- key diff summary
- blockers or residual risks

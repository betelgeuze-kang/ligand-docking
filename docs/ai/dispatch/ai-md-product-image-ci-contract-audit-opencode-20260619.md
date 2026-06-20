# OpenCode Slice: Product Image CI Contract Audit

Web access: disabled.

## Goal

Audit whether the product image GitHub Actions and preflight contracts clearly separate hosted build smoke from ROCm/HIP/Rust runtime smoke, without allowing build-only CI to be interpreted as product runtime readiness.

## Scope

Read only. Do not edit, stage, commit, push, delete, or mutate external state.

Inspect:

- `.github/workflows/product-image-smoke.yml`
- `deploy/verify_product_image.sh`
- `tools/product/build_product_image_smoke_preflight.py`
- `tests/unit/test_build_product_image_smoke_preflight.py`
- `tests/unit/test_product_runtime_reality.py`
- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`

## Audit Questions

1. Does hosted CI run only `PRODUCT_IMAGE_VERIFY_MODE=build`, and is that visibly not a product runtime claim?
2. Is there a manual/self-hosted path for `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime`, or is that only documented outside workflow inputs?
3. Does preflight fail closed if the workflow loses build/rocm separation?
4. Does `deploy/verify_product_image.sh` only emit `product_image_smoke_ready` for `rocm-runtime` with container runtime proof and runner claim metadata?
5. What minimal change would most improve CI contract clarity without pretending GitHub-hosted runners can prove ROCm hardware readiness?

## Verification Commands

Use focused read-only checks:

```bash
bash -n deploy/verify_product_image.sh
python3 -m pytest -q tests/unit/test_build_product_image_smoke_preflight.py tests/unit/test_product_runtime_reality.py
python3 tools/product/build_product_image_smoke_preflight.py
```

## Return Summary

Return concise summary only:

- files inspected
- commands run and pass/fail
- P0/P1 findings, if any
- recommended minimal patch, if any
- specific line references Codex should inspect

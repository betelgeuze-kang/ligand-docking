# Cursor Worker Slice: Product AI Surface Router Extraction

Web access: disabled

## Goal

Extract AI decision/report/pose/registry product endpoints from the legacy `api/product.py` monolith into a dedicated feature router while preserving behavior and direct import compatibility.

## Scope

- Create a new module, likely `api/product_ai_surface.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/ai-decision-graph`
  - `/product/pose-sampling-readiness`
  - `/product/ai-report-ux`
  - `/product/residual-model-registry`
- Keep compatibility imports available through `api.product` for:
  - `get_product_ai_decision_graph`
  - `get_product_pose_sampling_readiness`
  - `get_product_ai_report_ux`
  - `get_product_residual_model_registry`
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns all four paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with this extraction status.

## Non-Goals

- Do not change endpoint response schemas, artifact names, claim boundaries, or safety booleans.
- Do not move production AI checkpoint/gpu/promotion endpoints in this slice.
- Do not alter Tier-beta scientific service behavior.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Notes

`api/product.py` may still need `RESIDUAL_MODEL_REGISTRY_ARTIFACT` and related production AI constants for later endpoints. It is acceptable for the new router to define its own artifact path constants while the monolith keeps constants used by endpoints that remain there.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_ai_surface.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_ai_surface.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

# Cursor Worker Slice: Product Benchmark Router Extraction

Web access: disabled

## Goal

Extract benchmark, trajectory SLA, external metrics, and rollout smoke receipt product endpoints from the legacy `api/product.py` monolith into a dedicated feature router while preserving existing behavior.

## Scope

- Create a new module, likely `api/product_benchmark.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/external-metrics`
  - `/product/public-benchmark`
  - `/product/trajectory-sla-contract`
  - `/product/rollout-execution-smoke-receipt`
- Keep compatibility imports available through `api.product` for:
  - `get_product_external_metrics`
  - `get_product_public_benchmark`
  - `get_product_trajectory_sla_contract`
  - `get_product_rollout_execution_smoke_receipt`
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns all four paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with this extraction status.

## Non-Goals

- Do not change endpoint response schemas, artifact names, claim boundaries, or safety booleans.
- Do not split unrelated endpoints in this slice.
- Do not alter Tier-beta scientific service behavior.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_benchmark.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_benchmark.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

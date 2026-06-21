# Cursor Worker Slice: Product CAMEO and Runner Promotion Router Extraction

Web access: disabled

## Goal

Extract CAMEO validation/fetch and API runner profile promotion endpoints from the legacy `api/product.py` monolith into a dedicated feature router while preserving behavior and direct import compatibility.

## Scope

- Create a new module, likely `api/product_cameo_runner.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/cameo-live-validation`
  - `/product/cameo-official-result-fetch-preflight`
  - `/product/api-runner-profile-promotion-operator-receipt`
  - `/product/api-runner-profile-promotion-operator-staging-apply`
- Keep compatibility imports available through `api.product` for:
  - `get_product_cameo_live_validation`
  - `get_product_cameo_official_result_fetch_preflight`
  - `get_product_api_runner_profile_promotion_operator_receipt`
  - `get_product_api_runner_profile_promotion_operator_staging_apply`
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns all four paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with this extraction status.

## Non-Goals

- Do not change endpoint response schemas, artifact names, claim boundaries, or safety booleans.
- Do not move license endpoints, production AI endpoints, or scope/commercial-readiness endpoints in this slice.
- Do not alter Tier-beta scientific service behavior.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Notes

It is acceptable for the new router to define local copies of artifact path constants used by these endpoints. Preserve `api.product` as a compatibility facade.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_cameo_runner.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_cameo_runner.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

# Cursor Worker Slice: Product Operational Router Extraction

Web access: disabled

## Goal

Extract the product operational/security readiness endpoints from the legacy `api/product.py` monolith into a feature router while preserving all existing behavior and compatibility imports.

## Scope

- Create a new module, likely `api/product_operational.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/operational-quality`
  - `/product/security-deployment-contract`
- Keep `api.product.get_product_operational_quality` and `api.product.get_product_security_deployment_contract` available as compatibility imports.
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns both paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with the extraction status.

## Non-Goals

- Do not change endpoint response schemas or artifact semantics.
- Do not alter Tier-beta scientific service behavior.
- Do not split unrelated endpoints in this slice.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_operational.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_operational.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

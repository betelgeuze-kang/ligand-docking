# Cursor Worker Slice: Product Release Operations Router Extraction

Web access: disabled

## Goal

Extract release operations, commercial independence, release readiness, and job orchestration product endpoints from the legacy `api/product.py` monolith into a dedicated feature router while preserving behavior and direct import compatibility.

## Scope

- Create a new module, likely `api/product_release_ops.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/operations`
  - `/product/commercial-independence`
  - `/product/release-readiness`
  - `/product/job-orchestration-contract`
- Keep compatibility imports available through `api.product` for:
  - `get_product_operations`
  - `get_product_commercial_independence`
  - `get_product_release_readiness`
  - `get_product_job_orchestration_contract`
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns all four paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with this extraction status.

## Non-Goals

- Do not change endpoint response schemas, artifact names, claim boundaries, or safety booleans.
- Do not move license endpoints, CAMEO endpoints, production AI endpoints, or scope/commercial-readiness endpoints in this slice.
- Do not alter Tier-beta scientific service behavior.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Notes

If helper functions or artifact constants are still used by endpoints remaining in `api/product.py`, leave compatible definitions there and define the needed local copies in the new router. Preserve `api.product` as a compatibility facade.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_release_ops.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_release_ops.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

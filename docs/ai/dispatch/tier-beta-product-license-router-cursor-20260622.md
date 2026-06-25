# Cursor Worker Slice: Product License Router Extraction

Web access: disabled

## Goal

Extract license decision/work-order/audit product endpoints from the legacy `api/product.py` monolith into a dedicated feature router while preserving behavior and direct import compatibility.

## Scope

- Create a new module, likely `api/product_license.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/license-decision`
  - `/product/license-file-work-order`
  - `/product/self-hosted-license-distribution-audit`
  - `/product/license-options`
- Keep compatibility imports available through `api.product` for:
  - `get_product_license_decision`
  - `get_product_license_file_work_order`
  - `get_product_self_hosted_license_distribution_audit`
  - `get_product_license_options`
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns all four paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with this extraction status.

## Non-Goals

- Do not change endpoint response schemas, artifact names, claim boundaries, fingerprint computation, or safety booleans.
- Do not write or modify any LICENSE file.
- Do not move production AI endpoints, scope endpoints, commercial-readiness endpoints, or evidence endpoints in this slice.
- Do not alter Tier-beta scientific service behavior.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Notes

It is acceptable for the new router to define local copies of artifact path constants and import the existing license decision constants. Preserve `api.product` as a compatibility facade.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_license.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_license.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

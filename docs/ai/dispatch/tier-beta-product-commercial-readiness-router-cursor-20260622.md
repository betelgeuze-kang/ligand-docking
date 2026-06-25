# Cursor Worker Slice: Tier Beta Product Commercial Readiness Router Extraction

Web access: disabled.

## Goal

Extract the commercial-readiness product endpoints from `api/product.py` into a focused router module while preserving legacy compatibility imports and endpoint behavior.

## Scope

Create `api/product_commercial_readiness.py` with `router = APIRouter(prefix="/product", tags=["product"])` and move exactly these endpoints from `api/product.py`:

- `GET /product/commercial-readiness-operator-packet`
- `GET /product/commercial-readiness-operator-packet-freshness`
- `GET /product/commercial-readiness-execution-ladder`
- `GET /product/commercial-readiness-handoff-bundle`

Keep the moved function names unchanged:

- `get_product_commercial_readiness_operator_packet`
- `get_product_commercial_readiness_operator_packet_freshness`
- `get_product_commercial_readiness_execution_ladder`
- `get_product_commercial_readiness_handoff_bundle`

## Requirements

- Preserve response schemas, default missing-artifact payloads, claim boundaries, safety booleans, accounting-field expansions, and artifact paths exactly unless ruff formatting requires line wrapping.
- Do not acquire evidence, widen claims, run docking, promote scope, mutate external state, read `.env*`, stage, commit, push, or delete unrelated files.
- Register the new router in `api/main.py` before the legacy `api.product` router.
- Update `api/product.py` into a compatibility facade for these functions by importing/re-exporting them from `api.product_commercial_readiness`.
- Remove the moved route decorators and implementations from `api/product.py`; no duplicate routes should remain.
- Move only helper imports/constants needed for these four endpoints. Leave the remaining evidence/goal endpoints in `api/product.py`.
- Update `tests/unit/test_api_product_import.py` route ownership checks so the new router is counted and duplicate registrations are rejected.
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with a short note that commercial-readiness product routes are now split into `api/product_commercial_readiness.py`.

## Verification

Run:

```bash
python3 -m ruff check api/main.py api/product.py api/product_commercial_readiness.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If either fails, repair within this slice and rerun. Return a concise summary with changed files, tests run, failures if any, and blockers.

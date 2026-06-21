# Cursor Worker Slice: Tier Beta Product Scope Router Extraction

Web access: disabled.

## Goal

Extract the remaining scope/evidence-intake product endpoints from `api/product.py` into a focused router module while preserving legacy compatibility imports and endpoint behavior.

## Scope

Create `api/product_scope.py` with `router = APIRouter(prefix="/product", tags=["product"])` and move exactly these endpoints from `api/product.py`:

- `GET /product/scope-breadth-contract`
- `GET /product/scope-claim-guard`
- `GET /product/scope-evidence-priority`
- `GET /product/scope-evidence-intake-readiness`
- `GET /product/transporter-manual-review-intake`
- `GET /product/pxr-exact-review-intake`
- `GET /product/aqp1-operator-validation-candidate`
- `GET /product/aqp1-direct-binding-procurement-packet`

Keep the moved function names unchanged:

- `get_product_scope_breadth_contract`
- `get_product_scope_claim_guard`
- `get_product_scope_evidence_priority`
- `get_product_scope_evidence_intake_readiness`
- `get_product_transporter_manual_review_intake`
- `get_product_pxr_exact_review_intake`
- `get_product_aqp1_operator_validation_candidate`
- `get_product_aqp1_direct_binding_procurement_packet`

## Requirements

- Preserve response schemas, default missing-artifact payloads, claim boundaries, safety booleans, and artifact paths exactly unless a ruff-only formatting change is necessary.
- Do not acquire evidence, widen claims, run docking, promote scope, mutate external state, read `.env*`, stage, commit, push, or delete unrelated files.
- Register the new router in `api/main.py` before the legacy `api.product` router.
- Update `api/product.py` into a compatibility facade for these functions by importing/re-exporting them from `api.product_scope`.
- Remove the moved route decorators and implementations from `api/product.py`; no duplicate routes should remain.
- If helper functions/constants are only needed by the moved endpoints, put them in `api/product_scope.py`. If they are still needed by remaining endpoints, share by importing or leave local helpers in place without circular imports.
- Update `tests/unit/test_api_product_import.py` route ownership checks so the new router is counted and duplicate registrations are rejected.
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with a short note that scope/evidence intake product routes are now split into `api/product_scope.py`.

## Verification

Run:

```bash
python3 -m ruff check api/main.py api/product.py api/product_scope.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If either fails, repair within this slice and rerun. Return a concise summary with changed files, tests run, failures if any, and blockers.

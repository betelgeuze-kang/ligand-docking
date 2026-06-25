# Cursor Worker Slice: Tier Beta Product Evidence/Goal Router Extraction

Web access: disabled.

## Goal

Extract the final evidence/goal-audit product endpoints from `api/product.py` into a focused router module, leaving `api/product.py` as a compatibility facade with no product route implementations.

## Scope

Create `api/product_evidence_goal.py` with `router = APIRouter(prefix="/product", tags=["product"])` and move exactly these endpoints from `api/product.py`:

- `GET /product/scope-breadth-evidence-receipt`
- `GET /product/full-commercial-blocker-evidence-matrix`
- `GET /product/engine-refinement-claim-evidence-receipt`
- `GET /product/engine-refinement-claim-evidence-priority`
- `GET /product/goal-completion-audit`

Keep the moved function names unchanged:

- `get_product_scope_breadth_evidence_receipt`
- `get_product_full_commercial_blocker_evidence_matrix`
- `get_product_engine_refinement_claim_evidence_receipt`
- `get_product_engine_refinement_claim_evidence_priority`
- `get_product_goal_completion_audit`

## Requirements

- Preserve response schemas, default missing-artifact payloads, claim boundaries, safety booleans, artifact paths, readiness rollup fields, and sorting behavior exactly unless ruff formatting requires line wrapping.
- Move the local JSON helpers and `_goal_readiness_rollup_lane_surface` if they are no longer needed in `api/product.py`.
- Do not acquire evidence, widen claims, run docking or MD, promote scope, mutate external state, read `.env*`, stage, commit, push, or delete unrelated files.
- Register the new router in `api/main.py` before the legacy `api.product` router.
- Update `api/product.py` into a compatibility facade for these functions by importing/re-exporting them from `api.product_evidence_goal`.
- Remove the moved route decorators and implementations from `api/product.py`; no duplicate routes should remain.
- If `api/product.py` no longer needs `json`, `Path`, `Any`, or local artifact constants/helpers after the move, remove the unused imports/constants.
- Update `tests/unit/test_api_product_import.py` route ownership checks so the new router is counted and duplicate registrations are rejected.
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with a short note that evidence/goal product routes are now split into `api/product_evidence_goal.py`.

## Verification

Run:

```bash
python3 -m ruff check api/main.py api/product.py api/product_evidence_goal.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If either fails, repair within this slice and rerun. Return a concise summary with changed files, tests run, failures if any, and blockers.

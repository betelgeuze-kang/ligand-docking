# Cursor Worker Slice: Product Production AI Router Extraction

Web access: disabled

## Goal

Extract production-AI checkpoint, GPU-worker, promotion, and registry-promotion product endpoints from the legacy `api/product.py` monolith into a dedicated feature router while preserving behavior and direct import compatibility.

## Scope

- Create a new module, likely `api/product_production_ai.py`.
- Move these endpoints out of `api/product.py`:
  - `/product/production-ai-checkpoint-readiness`
  - `/product/production-ai-gpu-worker-dispatch-manifest`
  - `/product/production-ai-gpu-worker-dispatch-bundle`
  - `/product/production-ai-gpu-worker-execution-runbook`
  - `/product/production-ai-gpu-return-intake`
  - `/product/production-ai-promotion-workbench`
  - `/product/production-ai-registry-promotion-operator-receipt`
  - `/product/production-ai-registry-promotion-priority`
- Keep compatibility imports available through `api.product` for all moved `get_product_*` handlers.
- Register the new router in `api/main.py`.
- Update `tests/unit/test_api_product_import.py` to assert:
  - the new router owns all eight paths
  - each path is registered exactly once in `main.app.routes`
  - existing direct calls through `api.product` still work
- Update `docs/tier_beta_vertical_slice_current.md` and `docs/tier_beta_vertical_slice_gap_audit.md` with this extraction status.

## Non-Goals

- Do not change endpoint response schemas, artifact names, claim boundaries, readiness logic, sorted priority logic, or safety booleans.
- Do not run production AI, train models, create checkpoints, promote registries, execute GPU workers, edit profiles/registries, write artifacts, or mutate external state.
- Do not move scope/commercial-readiness/evidence endpoints in this slice.
- Do not alter Tier-beta scientific service behavior.
- Do not stage, commit, push, delete, deploy, publish, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Notes

The existing production-AI handlers are long. Move behavior verbatim with local copies of the artifact path constants and small helpers needed by this router. Preserve `api.product` as a compatibility facade.

If a helper is shared with endpoints that remain in `api/product.py`, leave that helper in `api/product.py` and define a local copy in the new router only if needed.

## Likely Files

- `api/product.py`
- `api/main.py`
- `tests/unit/test_api_product_import.py`
- `docs/tier_beta_vertical_slice_current.md`
- `docs/tier_beta_vertical_slice_gap_audit.md`
- new `api/product_production_ai.py`

## Verification

Run at least:

```bash
python3 -m ruff check api/main.py api/product.py api/product_production_ai.py tests/unit/test_api_product_import.py
python3 -m pytest -q tests/unit/test_api_product_import.py
```

If those pass and time permits, also run:

```bash
python3 -m pytest -q tests/unit/test_biodiscovery_screening.py tests/unit/test_tier_beta_vertical_slice.py tests/unit/test_api_product_import.py tests/unit/test_product_capability_matrix.py
```

Return a concise summary with changed files, tests run, failed tests if any, key diff summary, and blockers.

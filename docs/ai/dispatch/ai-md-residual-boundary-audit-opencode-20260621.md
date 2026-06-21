# OpenCode Worker Slice: Residual Boundary Audit

Web access: disabled.

## Goal

Audit the product runner residual paths and recommend the narrowest safe next code change.

## Context

- Preserve allowlisted runner paths as shims.
- Preserve `core/` compatibility. Migration direction is `betelgeuze_engine` first, then `core` calls engine, then runners call engine directly when semantics are real.
- Every bounded correction must be abstainable and claim-safe.
- The product KPI already exercises `betelgeuze_engine.residual` guarded force residual.
- `tools/product/run_ligand_backmapping_scoring.py` still imports `core.score_residual.apply_score_residual`.

## Scope

Inspect only:

- `tools/product/run_ligand_backmapping_scoring.py`
- `core/score_residual.py`
- `betelgeuze_engine/residual/`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- related unit tests if needed

Do not edit files unless the change is a tiny, obvious compatibility shim with matching tests. Prefer audit-only.

## Questions To Answer

1. Is `core.score_residual.apply_score_residual` semantically a score/ranking heuristic rather than the product guarded force residual?
2. Is there an existing real `betelgeuze_engine` API that the product runner can import for this score residual without semantic drift?
3. If not, what KPI/bundle guard should Codex add so score residual cannot be mistaken for product force residual?
4. What exact tests should Codex run after the change?

## Return Summary

Keep it concise:

- changed files, if any
- recommendation
- risky snippets or line references
- tests run
- blockers

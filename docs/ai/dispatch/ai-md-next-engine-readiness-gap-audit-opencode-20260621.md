# OpenCode Worker Slice: Next Engine Readiness Gap Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex is continuing the persistent AI-MD product/runtime/engine objective. Recent work strengthened:

- Product forcefield aggregate `EnergyForces` contract.
- Force-term bounded correction caps and claim rows.
- Neighbor-list parity validation.
- Topology pocket boundary metadata.
- H-bond/chemistry/pose evidence gates.
- Guarded residual applied-report caps.
- Product evidence bundle fail-closed gates.

The user wants orchestration actively used, with Codex owning final slicing, verification, and acceptance.

## Audit Scope

Find the next smallest high-value implementation gap aligned with the objective:

- Keep validated runner shims intact.
- Keep `core/` as compatibility layer.
- Ensure all physics terms return energy + forces + metadata.
- Ensure every correction/residual is bounded with claim-safe metadata.
- Ensure product/PM KPI evidence fails closed for runtime, physics, chemistry, and product readiness.
- Continue the engine promotion sequence: Topology -> ForceTerm -> ONSPS Evidence -> Guarded Residual -> Benchmark.

Prioritize gaps that can be closed with a focused local change and focused tests. Do not recommend broad refactors, GUI work, external state mutation, GitHub billing fixes, CASP/public-structure lookup, or web research.

Relevant files to inspect first:

- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
- `betelgeuze_engine/contracts/result.py`
- `betelgeuze_engine/physics/forcefield.py`
- `betelgeuze_engine/validation/force_checks.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

## Return Summary Format

Return only:

- Recommended next slice, one sentence.
- Why it is aligned with the objective.
- Exact files likely to change.
- Current evidence or line references showing the gap.
- Suggested focused tests.
- Any P0/P1 risk if left open.

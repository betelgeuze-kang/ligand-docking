# OpenCode Worker Slice: Post-PocketWall Next Gap Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex has just promoted the planned v1 guarded `PocketWallTerm` and strengthened product KPI/evidence bundle gates so both `pocket_wall` and `screened_electrostatics` are required guarded terms. The persistent objective is to keep moving through:

`Topology -> ForceTerm -> ONSPS Evidence -> Guarded Residual -> Benchmark`

Product runtime/Docker/runner surfaces are already evidenced locally; remote GitHub Actions green remains externally blocked by billing/spending-limit and is not an implementation slice.

## Audit Scope

Find the next smallest high-value implementation gap after the PocketWall slice, prioritizing ONSPS Evidence, Guarded Residual, or Benchmark/Product KPI evidence. Do not recommend broad refactors, GUI work, external mutation, web research, GitHub billing fixes, CASP/public structure lookup, or any work needing `.env`.

Look for a focused gap that:

- Makes the requested final state more true.
- Can be closed with local code/tests/artifact refresh.
- Strengthens fail-closed product evidence rather than only adding documentation.
- Preserves runner shims and keeps `core/` as compatibility layer.

Inspect first:

- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
- `betelgeuze_engine/backmapping/onsps.py`
- `betelgeuze_engine/interactions/hbond_evidence.py`
- `betelgeuze_engine/residual/guarded_force.py`
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

# OpenCode Worker Slice: AI-MD Engine Next Gap Audit After CI Green

Web access: disabled.

## Role

You are a scoped OpenCode implementation worker for repository exploration only.
Do not edit files, stage, commit, push, delete, or mutate external state.
Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex has made `product-api-worker` and `product-image-smoke` green on main.
The active objective now moves from product runtime reality into engine promotion:

- preserve runner shims and `core/` compatibility
- keep all force terms returning energy + forces + diagnostics/metadata
- enforce bounded corrections/caps
- connect claim-safe metadata to engine results
- continue `Topology -> ForceTerm -> ONSPS Evidence -> Guarded Residual -> Benchmark`

Primary reference:

- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`

## Task

Perform a read-only audit to identify the single highest-value next coding slice.

Check the current implementation and tests around:

- `betelgeuze_engine/interactions/hbond_evidence.py`
- `betelgeuze_engine/backmapping/onsps.py`
- `betelgeuze_engine/physics/force_term.py`
- `betelgeuze_engine/physics/forcefield.py`
- `betelgeuze_engine/physics/terms/*.py`
- `betelgeuze_engine/residual/guarded_force.py`
- `betelgeuze_engine/benchmark/runtime_scaling.py`
- `betelgeuze_engine/product/runners/backmapping_scoring.py`
- `api/result_manifest.py`
- relevant tests under `tests/unit/`

## Return Summary Only

Return a concise summary with:

1. What is already implemented and appears covered.
2. The most important missing or weak requirement from the reference doc.
3. Exact files/functions likely to change.
4. Focused tests to run or add.
5. Any blocker or risk.

Do not include full logs or giant grep output.

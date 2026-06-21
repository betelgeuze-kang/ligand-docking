# TASK-ID: BioDiscovery Platform Audit Inventory Slice

## Goal

Produce a concise, evidence-grounded first-pass repository inventory for the BioDiscovery commercial platform transition goal.

## Worker Path

Use OpenCode as a scoped implementation worker. Web access is disabled for this slice.

## Scope

- Use `git ls-files` to inventory tracked files with extensions `.py`, `.rs`, `.hip`, `.c`, `.cpp`, `.h`, `.js`, `.ts`, `.sh`, `.yml`, `.yaml`, `.toml`.
- Classify files into these buckets where possible: `core`, `adapter`, `runner`, `API`, `train`, `benchmark`, `test`, `deploy`, `generated`.
- Inspect representative source files only when needed to identify responsibility, caller surface, duplicate/dead-code risk, monolith risk, external dependency risk, and whether the file is on a tested/product path.
- Write or update `docs/code_architecture_inventory_current.md` with:
  - inventory method and explicit exclusions
  - summary counts by bucket
  - high-signal tables for major source areas
  - current-level validation notes separating accounting/product gates from scientific validity
  - likely P0 candidates that do not require external data

## Strict Boundaries

- Follow `AGENTS.md`.
- Do not read, print, summarize, or request secret environment files.
- Do not open or modify `runs/**`.
- Do not open large CASP/generated data or binary artifacts. File names from `git ls-files` are OK.
- Do not use AlphaFold, ColabFold, ESMFold, OmegaFold, public/template structures, public PDB target lookup, or other-team models.
- Do not mutate external state, stage, commit, push, submit, deploy, publish, or delete files.
- Preserve existing dirty worktree changes. In particular, do not modify or remove untracked `betelgeuze_engine/physics/dense_guard.py`.

## Likely Files Or Search Targets

- `api/product.py`, `api/product_accounting.py`
- `betelgeuze_ai_md/contracts/**`
- `betelgeuze_engine/contracts/**`, `betelgeuze_engine/topology/**`, `betelgeuze_engine/product/runners/**`
- `betelgeuze_product/**`
- `core/topology.py`, selected `core/*.py` files only if needed
- `benchmark/**`, `deploy/**`, `.github/workflows/**`
- `tools/product/run_product_full_implementation_regeneration.py`
- Existing product docs such as `docs/product_full_implementation_plan.md`

## Verification

- Run lightweight syntax/format checks only if directly relevant to files you changed.
- Do not run full pytest.

## Return Summary

Return at most 80 lines:

- changed files
- checks run and result
- high-signal inventory findings
- blockers or uncertainty

Do not include full logs or full diffs.

## Risk Level

R3 local / R4 external boundary, but this slice must remain local-only and documentation-only.

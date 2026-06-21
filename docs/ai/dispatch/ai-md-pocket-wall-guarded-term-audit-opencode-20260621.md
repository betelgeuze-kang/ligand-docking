# OpenCode Worker Slice: PocketWall Guarded Term Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex promoted the planned v1 guarded `PocketWallTerm` from legacy coarse MD behavior into the new `betelgeuze_engine` force-term surface. The term is opt-in guarded only; default registry and runner shims must remain unchanged.

Relevant changed files for this slice:

- `betelgeuze_engine/physics/terms/pocket_wall.py`
- `betelgeuze_engine/physics/terms/__init__.py`
- `betelgeuze_engine/physics/forcefield.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `runs/ai_md_engine_kpi_report_current.json`
- `runs/ai_md_engine_kpi_report_current.md`
- `runs/ai_md_product_evidence_bundle_current.json`
- `runs/ai_md_product_evidence_bundle_current.tar.gz`

## Audit Scope

Review whether:

- `PocketWallTerm` returns energy, forces, diagnostics, and claim metadata under the existing `TermResult` contract.
- Missing pocket/ligand metadata fails closed with zero energy/forces and non-claim-safe metadata.
- Policy cap exceedance fails closed and does not leak non-zero correction forces.
- `guarded_force_term_registry()` includes `pocket_wall` without changing `default_force_term_registry()`.
- Product KPI smoke requires both `pocket_wall` and `screened_electrostatics`.
- Product evidence bundle validation fails closed if `pocket_wall` guarded rows or aggregate claim rows are missing.
- No runner shim, `core/` compatibility path, or product Docker/runtime gate is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py` -> passed
- `python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py` -> passed
- `python3 -m pytest -q tests/unit/test_build_ai_md_product_evidence_bundle.py` -> passed
- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_engine_transition_shims.py` -> `122 passed, 1 warning`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `python3 tools/product/build_ai_md_engine_kpi_report.py` -> `status=ai_md_engine_kpi_report_ready`
- `python3 tools/product/build_ai_md_product_evidence_bundle.py` -> `status=ai_md_product_evidence_bundle_ready`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

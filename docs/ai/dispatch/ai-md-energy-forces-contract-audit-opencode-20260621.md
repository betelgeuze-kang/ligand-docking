# OpenCode Worker Slice: EnergyForces Aggregate Contract Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex strengthened the aggregate product forcefield result contract:

- Added `validate_energy_forces_contract()` for `EnergyForces`.
- Exported it from `betelgeuze_engine.contracts`.
- `ProductForceField.energy_forces()` now validates the aggregate before returning it.
- Added positive/negative scaffold tests for aggregate shape, finite term values, diagnostics, and force-term claim rows.

Relevant changed files for this slice:

- `betelgeuze_engine/contracts/result.py`
- `betelgeuze_engine/contracts/__init__.py`
- `betelgeuze_engine/physics/forcefield.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`

Other dirty files are earlier topology pocket, neighbor parity, bounded correction, residual, and H-bond/product-gate work. Only inspect them for interaction risk.

## Audit Scope

Review whether:

- Aggregate `EnergyForces` now fails closed on wrong energy/force shape, nonfinite energy/forces, nonfinite term values, missing diagnostics, term count mismatch, missing required claim metadata, `claim_safe` with non-empty blocker, missing force-term claim metadata readiness, and claim row count mismatch.
- `ProductForceField.energy_forces()` still returns the same valid aggregate for existing callers.
- The new public export is coherent.
- No runner shim, core compatibility path, force-term contract, topology claim gate, or product evidence gate is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py` -> `118 passed`
- Manual KPI smoke:
  - `status=ai_md_engine_kpi_report_ready`
  - `force_term_result_contract_ready=True`
  - `core_forcefield_bridge_ready=True`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

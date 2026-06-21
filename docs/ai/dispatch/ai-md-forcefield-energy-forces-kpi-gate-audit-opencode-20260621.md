# OpenCode Worker Slice: Forcefield EnergyForces KPI Gate Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex had already added `validate_energy_forces_contract()` for aggregate `EnergyForces`. This slice exposes that aggregate contract as an explicit product KPI/evidence gate:

- `tools/product/build_ai_md_engine_kpi_report.py` now records `forcefield_energy_forces_contract_ready` and detailed aggregate fields in `force_term_claim_metadata_smoke`.
- `tools/product/build_ai_md_product_evidence_bundle.py` now fails closed if this aggregate contract or its PM summary gate is missing.
- Tests now cover normal export and a fail-closed product bundle path when the aggregate contract is broken.

Relevant changed files for this slice:

- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

Other dirty files are earlier contract/topology/parity/H-bond/residual work. Only inspect them for interaction risk.

## Audit Scope

Review whether:

- The new product KPI clearly exposes aggregate `EnergyForces` contract readiness.
- Product evidence bundle validation fails closed if the aggregate contract is absent or invalid.
- PM product summary includes the same gate.
- Current artifact convergence did not leave stale source/bundle errors.
- No runner shim, core compatibility path, force-term contract, topology claim gate, or product claim gate is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py` -> `119 passed`
- Regenerated current artifacts until converged:
  - `engine_status=ai_md_engine_kpi_report_ready`
  - `engine_bundle_pass=True`
  - `bundle_status=ai_md_product_evidence_bundle_ready`
  - `bundle_validation_pass=True`
  - `product_claim_ready=True`
  - `forcefield_energy_forces_contract_ready=True`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

# OpenCode worker slice: WaterDisplacementProxyTerm guarded force audit

Web access: disabled.

## Goal

Audit the current local diff for the new guarded `WaterDisplacementProxyTerm` and the related KPI/product evidence bundle wiring. This is review-only.

## Scope

Focus only on:

- `betelgeuze_engine/physics/terms/water_displacement_proxy.py`
- `betelgeuze_engine/physics/terms/__init__.py`
- `betelgeuze_engine/physics/forcefield.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`

## Review questions

- Does `WaterDisplacementProxyTerm` fail closed unless topology is sequence-mapped, ligand topology is valid/claim-safe, `water_displacement_model_valid` is true, and explicit ligand/site indices are present?
- Are ligand/site overlap, invalid optional weights, missing metadata, invalid topology, unvalidated model, and cap exceedance all blocked?
- Is the energy differentiable and based only on state-coordinate indices, preserving finite-difference, translation invariance, and rotation equivariance?
- Are bounded cap metadata and claim metadata consistent with the existing guarded terms?
- Do KPI and product bundle gates cover valid execution plus blocker rows and forcefield aggregate claim rows?
- Are there any P0/P1 issues: data loss/corruption, claim leakage, unsafe execution enablement, missing tests for changed behavior, CASP boundary violation, or scope drift?

## Verification to run if practical

```bash
python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py
python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py
```

## Return format

Return only a concise summary:

- changed files if you changed anything
- tests run
- P0/P1 findings, if any
- P2/nits, if any
- blockers, if any

Do not broaden scope. Do not read `.env*`. Do not commit, push, delete, deploy, upload, or mutate external state.

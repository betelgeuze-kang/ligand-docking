# OpenCode Slice: Torsion Prior Guarded Term Audit

## Goal

Audit the current working tree changes for the new guarded `TorsionPriorTerm` slice.

## Scope

- Inspect only current diff relevant to:
  - `betelgeuze_engine/physics/terms/torsion_prior.py`
  - `betelgeuze_engine/physics/terms/__init__.py`
  - `betelgeuze_engine/physics/forcefield.py`
  - `tools/product/build_ai_md_engine_kpi_report.py`
  - `tools/product/build_ai_md_product_evidence_bundle.py`
  - `tests/unit/test_betelgeuze_engine_scaffold.py`
  - `tests/unit/test_build_ai_md_engine_kpi_report.py`
  - `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- Check that the term returns energy + forces + diagnostics + claim metadata, is bounded, fail-closes on missing/invalid inputs and cap violations, is guarded opt-in only, and is validated by PM/product evidence gates.
- Web access: disabled.

## Constraints

- Audit only. Do not edit files.
- Do not stage, commit, push, delete, deploy, publish, submit, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not broaden into topology penalty, water displacement, benchmark expansion, or GUI work.

## Verification Context

Codex has already run:

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py -k "torsion or guarded_force_term_registry"`
- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `python3 tools/product/build_ai_md_engine_kpi_report.py`
- `python3 tools/product/build_ai_md_product_evidence_bundle.py`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`

## Return Summary

Return only:

- Findings, ordered by severity, with file/line references.
- Test gaps or residual risks.
- If no blocking issue is found, say that clearly.

# OpenCode Worker Slice: Topology Pocket Boundary Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex strengthened topology claim metadata so `ComplexTopology.pocket_residue_indices` participates in product claim safety:

- Valid pocket indices are preserved in claim metadata.
- Out-of-range pocket indices fail closed with `invalid_pocket_residue_indices`.
- Product KPI smoke and product evidence bundle validation now require the invalid-pocket blocker.

Relevant changed files for this slice:

- `betelgeuze_engine/topology/validity.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

Other dirty files are earlier H-bond/chemistry/pose, bounded correction, residual, and neighbor parity work. Only inspect them for interaction risk.

## Audit Scope

Review whether:

- Valid pocket indices keep claim metadata claim-safe when all other topology inputs are valid.
- Out-of-range pocket indices fail closed and produce `blocked_reason=invalid_pocket_residue_indices`.
- Empty pocket lists remain allowed, preserving current runner behavior.
- KPI report and product evidence bundle validator require both the valid-pocket and invalid-pocket rows.
- No runner shim, core compatibility layer, force-term contract, or product claim gate is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py` -> `112 passed`
- Regenerated current artifacts in converged order:
  - `python3 tools/build_ai_md_engine_kpi_report.py`
  - `python3 tools/build_ai_md_product_evidence_bundle.py`
  - extra convergence reruns until `engine_status=ai_md_engine_kpi_report_ready` and `bundle_status=ai_md_product_evidence_bundle_ready`
- Artifact smoke:
  - `engine_bundle_pass=True`
  - `bundle_validation_pass=True`
  - `product_claim_ready=True`
  - `invalid_pocket_blocked_reason=invalid_pocket_residue_indices`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

# OpenCode Worker Slice: Neighbor Parity Validator Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex strengthened `betelgeuze_engine.validation.neighbor_list_parity_error()` so the Physics KPI "neighbor-list parity" checks more than pair-mask equality. It now fails closed on shape mismatch/non-finite distances and includes distance/index parity in the returned error.

Relevant changed files for this slice:

- `betelgeuze_engine/validation/force_checks.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`

Other dirty files are earlier product-gate and bounded-correction work. Only inspect them for interaction risk.

## Audit Scope

Review whether:

- Candidate neighbor lists with corrupted distance values now produce nonzero parity error.
- Candidate neighbor lists with corrupted indices now produce nonzero parity error.
- Non-finite candidate distances fail closed.
- The default KPI path still reports exact zero parity for generated full neighbor pairs.
- The implementation does not weaken force-term, runner shim, core compatibility, or product claim safety.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py` -> `111 passed`
- Manual KPI smoke:
  - `status=ai_md_engine_kpi_report_ready`
  - `neighbor_list_parity_error=0.0`
  - `pm_kpi_summary.physics.neighbor_list_parity_pass=True`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

# OpenCode Worker Slice: Force-Term Claim Row Blocker Bundle Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex strengthened the product evidence bundle validator so forcefield claim rows fail closed when a row is marked `claim_safe=True` but still carries a non-empty `blocked_reason`.

Relevant changed files for this slice:

- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

Other dirty files are earlier engine contract, KPI, topology, neighbor parity, bounded correction, residual, and H-bond readiness work. Only inspect them for interaction risk.

## Audit Scope

Review whether:

- `forcefield_claim_rows` now fail closed on claim-safe rows with non-empty `blocked_reason`.
- The added negative test would catch a regression in that bundle-level validation.
- The change does not weaken existing force-term claim row checks for `claim_safe`, `force_term_name`, or `force_term_status`.
- No runner shim, core compatibility path, product KPI, or evidence bundle gate is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py` -> `120 passed`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

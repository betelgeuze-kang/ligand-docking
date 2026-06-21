# OpenCode Worker Slice: Guarded Residual Applied Cap Validator Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex has strengthened the product evidence bundle validator so the guarded force residual `last_report` success row must prove it is actually claim-safe, top-k eligible, and within bounded correction caps before the bundle can pass product claim gates.

Relevant changed files:

- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- Existing H-bond/chemistry/pose validator changes remain in the same dirty diff.

## Audit Scope

Review the dirty diff for:

- Whether the applied residual validator fails closed when `last_report` is missing, unsafe, outside top-k, non-finite, or above force/displacement/energy caps.
- Whether the new test fixtures represent the current KPI artifact contract.
- Whether the negative test covers the intended product safety boundary.
- Whether the change accidentally weakens existing nonfinite/top-k/abstention gates.
- Any P0/P1 issues, especially claim metadata leakage, unsafe execution enablement, scope drift, or missing tests.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py` -> `84 passed`
- `python3 tools/build_ai_md_product_evidence_bundle.py`
- `python3 tools/build_ai_md_engine_kpi_report.py`
- `python3 tools/build_ai_md_product_evidence_bundle.py`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only a concise summary:

- P0/P1 findings, if any, with file and line references.
- Any test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

# OpenCode Worker Slice

You are OpenCode acting as a scoped implementation worker. Codex owns risk boundaries, targeted review, verification, and final acceptance.

## Task

Strengthen the product-visible guarded force residual contract gate so PM/product evidence can prove that multiple residual scenarios were contract-validated, not just that a single boolean is true.

## Files In Scope

- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_guarded_residual.py` only if a direct engine contract test is clearly needed
- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md` only for a short status note if implementation changes a product KPI surface

## Acceptance Criteria

- `runtime_kpi.top10_force_residual` exposes explicit contract-count fields, for example:
  - `contract_expected_report_count`
  - `contract_validated_report_count`
  - `contract_validation_ready`
  - product-visible required claim metadata keys/caps, if not already present
- The product evidence bundle validator fails closed when the count fields are missing, too low, or inconsistent with `contract_ready`.
- Tests cover both the ready case and at least one fail-closed case.
- Do not broaden architecture, change runner paths, delete compatibility shims, or touch external state.

## Verification

Run focused tests if safe:

```bash
python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_betelgeuze_engine_guarded_residual.py
```

If that is too broad or fails for unrelated pre-existing reasons, run the narrowest relevant subset and report exactly what passed/failed.

## Web Access

Web access: disabled

Do not use web search/fetch for this slice. Do not access active CASP17 target lookup, public/template/native structures, other-team models, secrets, `.env` content, author codes, or external mutation.

## Constraints

- Follow `AGENTS.md`.
- Do not expand scope.
- Do not redesign architecture.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not run push, merge, deploy, publish, release, production migration, billing, cloud mutation, secret rotation, permission escalation, deletion, or CASP submission commands.
- Keep return summary under 80 lines.

## Return Format

- changed files
- tests/checks run with pass/fail status
- failed test names, if any
- key diff summary in 10 bullets or fewer
- blockers or risks
- web sources consulted, only if web access was enabled

# OpenCode Worker Slice: Bounded Force-Term Contract Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex strengthened the product engine `TermResult` contract so force terms that request bounded correction validation must include:

- `force_term_active_pair_count_within_cap`
- finite numeric policy caps for `max_abs_energy`, `max_force_norm`, and `max_active_pair_count`

This is intended to make the senior-engineering rule “all corrections are bounded” true at the engine contract level, not only at the product bundle validator level.

Relevant changed files:

- `betelgeuze_engine/contracts/result.py`
- `betelgeuze_engine/contracts/__init__.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`

Other dirty files in the worktree are from earlier H-bond/chemistry/pose and guarded residual product-gate work. Do not audit them deeply except for interaction risk.

## Audit Scope

Review the dirty diff for:

- Whether bounded correction validation now fails closed if active-pair cap evidence is missing.
- Whether policy caps are required and finite without breaking existing guarded `ScreenedElectrostaticsTerm`.
- Whether public contract exports remain coherent.
- Whether the tests cover both valid and invalid bounded correction contract cases.
- Any P0/P1 issue, especially scope drift, weakened claim safety, or breaking runner/core compatibility.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py` -> `28 passed`
- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py` -> `114 passed`

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

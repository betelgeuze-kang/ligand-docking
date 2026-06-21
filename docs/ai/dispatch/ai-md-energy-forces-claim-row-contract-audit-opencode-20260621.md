# OpenCode Worker Slice: EnergyForces Claim Row Contract Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex strengthened `validate_energy_forces_contract()` so aggregate `EnergyForces.claim_metadata["force_term_claim_rows"]` is not only counted but structurally tied to the aggregate term values:

- Every force-term claim row must be a dict.
- Every row must have `force_term_name`, `force_term_status`, boolean `claim_safe`, and no blocker when `claim_safe=True`.
- Claim row names must match `EnergyForces.terms` exactly.

Relevant changed files for this slice:

- `betelgeuze_engine/contracts/result.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`

Other dirty files are earlier KPI/product gate, topology, neighbor parity, bounded correction, residual, and H-bond work. Only inspect them for interaction risk.

## Audit Scope

Review whether:

- Aggregate claim rows now fail closed on non-dict rows.
- Aggregate claim rows now fail closed on missing/mismatched term names.
- Claim-safe rows with non-empty blockers fail closed.
- Existing `ProductForceField` output still satisfies the stronger aggregate contract.
- No runner shim, core compatibility path, product KPI, or evidence bundle gate is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py` -> `119 passed`
- Manual KPI smoke:
  - `status=ai_md_engine_kpi_report_ready`
  - `forcefield_energy_forces_contract_ready=True`
  - `force_term_claim_metadata_smoke.forcefield_energy_forces_contract_ready=True`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

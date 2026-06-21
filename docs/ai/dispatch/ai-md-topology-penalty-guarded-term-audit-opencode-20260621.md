# OpenCode worker slice: TopologyPenaltyTerm guarded force audit

Web access: disabled.

## Goal

Audit the current local diff for the new guarded `TopologyPenaltyTerm` and the related KPI/product evidence bundle wiring.

## Scope

Focus only on:

- `betelgeuze_engine/physics/terms/topology_penalty.py`
- `betelgeuze_engine/physics/terms/__init__.py`
- `betelgeuze_engine/physics/forcefield.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

## Review questions

- Does `TopologyPenaltyTerm` fail closed unless topology is `sequence_mapped`, ligand topology is valid/claim-safe, and explicit edge/target metadata is present?
- Are force/energy results bounded, finite, differentiable, and contract-compatible with existing guarded terms?
- Do KPI and product bundle gates cover valid execution plus missing metadata, invalid topology, and cap-exceeded blockers?
- Does the bundle/KPI self-freshness recovery stay narrow and avoid hiding real stale-source or bundle validation failures?
- Are there any P0/P1 issues: data loss/corruption, claim leakage, CASP boundary violation, unsafe execution enablement, missing tests for changed behavior, or scope drift?

## Verification to run if practical

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py -k "topology_penalty or guarded_force_term_registry"`
- `python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py`

## Return format

Return only a concise summary:

- changed files if you changed anything
- tests run
- P0/P1 findings, if any
- P2/nits, if any
- blockers, if any

Do not broaden scope. Do not read `.env*`. Do not commit, push, delete, deploy, upload, or mutate external state.

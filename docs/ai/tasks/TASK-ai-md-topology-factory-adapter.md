# TASK-ID: ai-md-topology-factory-adapter

## Goal

Bridge the existing `core.topology.TopologyFactory` fidelity/accounting surface into the typed AI-MD `TopologyValidityReport` contract.

## Non-goals

- Do not widen restricted/local-delivery or full-commercial claims.
- Do not run docking, GPU jobs, external fetches, web calls, or production mutations.
- Do not redesign `core.topology`.
- Do not enable AdResS production paths.

## User Impact

Existing topology factories can now feed typed evidence bundles without relying on ad hoc dictionaries. Placeholder topology remains fail-closed, while sequence-mapped topology gets explicit validity rows.

## Risk Level

R2

## Relevant Files

- `betelgeuze_ai_md/contracts/topology_adapter.py`
- `betelgeuze_ai_md/contracts/__init__.py`
- `tools/product/build_ai_md_contract_source_of_truth_gate.py`
- `tests/unit/test_betelgeuze_ai_md_topology_adapter.py`
- `tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Constraints

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries.
- Keep placeholder topology fail-closed.
- Keep full-commercial/general-MD claim promotion blocked.

## Acceptance Criteria

- Add a lightweight adapter from topology-like objects or metadata dicts to `TopologyValidityReport`.
- Placeholder topology emits `status="not_assessed"` or equivalent fail-closed status with claim blockers.
- Sequence-mapped topology emits a passing typed report with validity rows and no claim blockers when residue counts are coherent.
- The adapter avoids importing heavy optional dependencies.
- The adapter is exported from `betelgeuze_ai_md.contracts`.
- AI-MD source-of-truth gate checks the adapter surface.

## Required Tests

- `python3 -m pytest -q tests/unit/test_betelgeuze_ai_md_topology_adapter.py tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`
- `python3 -m py_compile betelgeuze_ai_md/contracts/*.py tools/product/build_ai_md_contract_source_of_truth_gate.py`

## Review Focus

- No claim widening.
- No production AdResS enablement.
- No external state mutation.
- Adapter handles duck-typed topology objects and plain metadata.

## Rollback Plan

Remove the adapter module, export, gate check, and focused tests from this task; keep prior typed topology contract work intact.

## Notes

This task continues R2 by connecting the existing core topology factory surface to the AI-MD contract layer.

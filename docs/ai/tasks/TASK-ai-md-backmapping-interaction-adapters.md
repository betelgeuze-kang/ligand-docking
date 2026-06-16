# TASK-ID: ai-md-backmapping-interaction-adapters

## Goal

Bridge existing ONSPS/backmapping and interaction metadata into typed AI-MD `BackmappedPose` and `InteractionReport` contracts.

## Non-goals

- Do not widen restricted/local-delivery or full-commercial claims.
- Do not run docking, GPU jobs, external fetches, web calls, or production mutations.
- Do not redesign scoring, force fields, or ONSPS math.
- Do not make API evidence bundles claim-safe.

## User Impact

Backmapping and interaction evidence can enter delivery bundles through a stable typed contract instead of ad hoc dictionaries, while missing or weak evidence remains visibly fail-closed.

## Risk Level

R2

## Relevant Files

- `betelgeuze_ai_md/contracts/backmapping_adapter.py`
- `betelgeuze_ai_md/contracts/interaction_adapter.py`
- `betelgeuze_ai_md/contracts/__init__.py`
- `tools/product/build_ai_md_contract_source_of_truth_gate.py`
- `tools/product/build_product_release_source_of_truth_gate.py`
- `tests/unit/test_betelgeuze_ai_md_backmapping_interaction_adapters.py`
- `tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Constraints

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries.
- Keep API evidence bundles review-only.
- Keep general-MD/full-commercial claim promotion blocked.
- Avoid heavy optional imports at module import time; numpy is acceptable if already used for ONSPS metadata handling.

## Acceptance Criteria

- Add a typed adapter from ONSPS/backmapping metadata to `BackmappedPose`.
- ONSPS `backmap_status="ok"` with sites emits chemical-validity pass metadata and bounded confidence.
- Empty/missing/no-site backmapping emits `chemical_validity_summary.status="not_assessed"` or another non-passing fail-closed status.
- Add a typed adapter from interaction/backmapping metadata to `InteractionReport`.
- Missing interactions emit `interaction_evidence_missing`.
- Role-invalid or unsupported interaction rows add claim blockers.
- Export adapter symbols from `betelgeuze_ai_md.contracts`.
- AI-MD source-of-truth gate checks both adapter surfaces.
- Product release source-of-truth tracks the new adapter files and tests.

## Required Tests

- `python3 -m py_compile betelgeuze_ai_md/contracts/*.py tools/product/build_ai_md_contract_source_of_truth_gate.py tools/product/build_product_release_source_of_truth_gate.py`
- `python3 -m pytest -q tests/unit/test_betelgeuze_ai_md_backmapping_interaction_adapters.py tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Review Focus

- No claim widening.
- Fail-closed behavior on missing/weak evidence.
- Deterministic hashes and stable typed output.
- No broad unrelated refactors.

## Rollback Plan

Remove the new adapter modules, exports, gate checks, and focused tests from this task; keep prior topology contract/adapter work intact.

## Notes

This task starts R3 from `.betelgeuze/ai_md_refactor_commercial_audit_2026-06-16.md`.

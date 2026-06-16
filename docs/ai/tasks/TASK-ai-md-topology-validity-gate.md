# TASK-ID: ai-md-topology-validity-gate

## Goal

Promote AI-MD topology validity from a loose `dict` into a typed fail-closed contract used by `EvidenceBundle` and the API evidence-bundle adapter.

## Non-goals

- Do not widen restricted/local-delivery or full-commercial claims.
- Do not run docking, GPU jobs, external fetches, web calls, or production mutations.
- Do not refactor unrelated `core/` physics or API product projection modules.

## User Impact

Customer-facing AI-MD evidence bundles become safer: placeholder or unassessed topology cannot accidentally satisfy claim-safe bundle validation.

## Risk Level

R2

## Relevant Files

- `betelgeuze_ai_md/contracts/output_schema.py`
- `betelgeuze_ai_md/contracts/manifest.py`
- `betelgeuze_ai_md/contracts/api_adapter.py`
- `betelgeuze_ai_md/contracts/__init__.py`
- `tools/product/build_ai_md_contract_source_of_truth_gate.py`
- `tests/unit/test_betelgeuze_ai_md_contracts.py`
- `tests/unit/test_betelgeuze_ai_md_api_adapter.py`
- `tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Constraints

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries if the task touches CASP readiness.
- Keep the API adapter review-only; it must not set `claim_safe=True`.
- Keep general-MD and full-commercial claim promotion blocked.

## Acceptance Criteria

- A typed `TopologyValidityReport` contract exists and is exported.
- `EvidenceBundle` accepts either a `TopologyValidityReport` instance or a compatible dict and serializes deterministically.
- `claim_safe=True` requires passing topology, no topology claim blockers, and non-placeholder topology fidelity.
- API fallback topology reports are explicit fail-closed/not-assessed reports with claim blockers.
- AI-MD source-of-truth gate checks the topology validity contract surface.

## Required Tests

- `python3 -m pytest -q tests/unit/test_betelgeuze_ai_md_contracts.py tests/unit/test_betelgeuze_ai_md_api_adapter.py tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`
- `./scripts/ai-verify.sh`

## Review Focus

- No claim widening.
- Placeholder alanine topology remains blocked for claim-safe bundles.
- No broad unrelated refactors.
- Existing unstructured API result fallback remains compatible.

## Rollback Plan

Revert only the topology contract files and tests from this task; leave prior AI-MD contract/API bundle work intact.

## Notes

This task continues the R2 recommendation from `.betelgeuze/ai_md_refactor_commercial_audit_2026-06-16.md`.

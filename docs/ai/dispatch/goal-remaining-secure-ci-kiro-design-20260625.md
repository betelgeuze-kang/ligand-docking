# Kiro Design Slice: Remaining Secure CI Closure

## Goal

Design the next scoped implementation plan for the active objective, preserving the requested order:

1. existing test expected error/string or current expectation drift fix
2. RDKit-missing lightweight CI synthetic smoke handling
3. private payload round-trip, tamper, and expiry tests
4. transactional outbox recovery tests
5. secure API submission E2E tests
6. GitHub Actions workflow connection for the new tests
7. full diff code review
8. PR creation, main merge, Docker/ROCm runtime verification

Current observed evidence:
- `python3 -m pytest tests/unit -q --maxfail=1` currently fails first at `tests/unit/test_api_cameo_import.py::test_api_app_imports_with_cameo_router`.
- Failure: `/cameo/architecture-validation` returns `cameo_architecture_validation_ready: False`, but the test expects `True`.
- The endpoint payload reports `status: cameo_architecture_validation_contract_ready`, `blocked_lane_count: 0`, `approval_required_lane_count: 0`, but `validation_evidence_ready: False`, `performance_scorecard_evidence_ready: False`, `official_results_ready: False`, `official_cameo_results_used: False`, `public_registration_authorized: False`.
- Modified P0 tests currently pass in the focused batch.

## Context To Inspect

- `AGENTS.md`
- `docs/ai/ORCHESTRATION.md`
- `api/cameo.py`
- `tests/unit/test_api_cameo_import.py`
- `tools/accounting/build_cameo_architecture_validation_contract.py`
- `betelgeuze_cameo/architecture_validation.py`
- likely private payload / outbox / secure submission modules and tests discovered by grep
- `.github/workflows/product-image-smoke.yml` and any focused CI workflow that should run the new tests

## Design Output

Return a concise design draft for Codex to review:

- goal and non-goals
- proposed smallest implementation slice(s), in the requested order
- likely files
- risk level and safety boundaries
- verification plan
- open questions or blockers

Prefer a plan that Cursor Composer 2.5 can implement as one narrow slice first, then leave later PR/merge/runtime steps as gated follow-up if local test work is not yet complete.

## Hard Constraints

- Design only. Do not edit files.
- Do not stage, commit, push, delete, deploy, publish, submit to CASP, or mutate external state.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not use external predictors, public/template/native structures, public PDB target lookups, or other-team models for active CASP17 work.
- Do not store CASP author code in docs, configs, prompts, state, trace, or commits.
- Web access disabled.

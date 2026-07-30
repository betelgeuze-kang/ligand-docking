# TASK-engine-v2-stage0-blind-admission: Freeze Blind Admission

## Goal

Prevent any fresh 128-case internal holdout execution until result-independent acceptance,
environment, custody, and review conditions are frozen and verified.

## Scope

- Add a machine-readable Stage 0 freeze contract and fail-closed verifier.
- Require it before `fresh-internal-blind-holdout` execution and reject the
  invalidated historical `primary-blind-holdout` subset.
- Bind metric thresholds to non-smoke, non-holdout provenance.
- Bind source hashes, exact runtime versions, artifact retention, suite
  classification, independent review, operator separation, and legal review.
- Document that runtime is descriptive and diagnostic results select a track.

## Non-goals

- Do not execute or inspect the 298 holdout.
- Do not invent numeric thresholds or fill human attestations.
- Do not tune scorer, charge, pocket, budget, proposal, or refinement behavior.
- Do not merge, publish, deploy, or mutate external state.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/blind_stage0.py`
- `tools/run_engine_v2_public_redocking_300.py`
- `tools/verify_engine_v2_public_redocking_stage0.py`
- `config/engine_v2_public_redocking_stage0_freeze.template.json`
- `tests/unit/test_engine_v2_blind_stage0.py`
- `docs/engine_v2_public_redocking_300.md`

## Verification

- Focused Stage 0 and runner tests.
- `./scripts/ai-verify.sh`.

## Stop Conditions

- Follow `AGENTS.md`; preserve all no-leak and external-mutation boundaries.
- A missing evidence source or human decision remains an explicit blocker.

## Risk Level

R2

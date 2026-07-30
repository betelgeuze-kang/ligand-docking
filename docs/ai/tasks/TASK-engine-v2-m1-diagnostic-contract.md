# TASK-engine-v2-m1-diagnostic-contract: Blind-Run Diagnostic Contract

## Goal

Freeze and verify the result-independent diagnostic contract required before the
one-time 298-case primary blind-holdout run.

## Scope

- Define preparation, proposal-oracle, scoring-regret, validity,
  charge/H-bond, failure, and size/rotor/ring diagnostics.
- Bind every report-consumed diagnostic to authenticated case execution
  receipts and reject missing, substituted, or inconsistent rows.
- Advance the capability snapshot and independent distribution release
  candidate for the frozen diagnostic schema.
- Keep the two observed cases in the engineering-smoke partition.
- Verify the contract from an empty output root before opening the 298 holdout.

## Non-goals

- Do not execute the 298-case holdout in this slice.
- Do not tune search, scoring, candidate budget, preparation, or refinement.
- Do not merge PR #210 or make performance claims.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py`
- `tools/run_engine_v2_public_redocking_300.py`
- `tests/unit/test_engine_v2_public_redocking_*_stage7.py`
- `docs/engine_v2_public_redocking_300.md`
- `config/independent_engine_v2_capabilities.yaml`
- `packaging/engine-v2/pyproject.toml`
- `CHANGELOG.md`

## Verification

- Focused public-redocking benchmark and runner tests.
- Empty-root two-case engineering smoke with evaluator error count zero.
- `./scripts/ai-verify.sh` from a checkout that carries the verifier.

## Stop Conditions

- Follow `AGENTS.md`; preserve the frozen archive and no-leak boundaries.
- Stop before any primary-holdout execution until the diagnostic schema,
  receipts, candidate budget, and report definitions are frozen and reviewed.
- Do not mutate external state without explicit human approval.

## Risk Level

R2

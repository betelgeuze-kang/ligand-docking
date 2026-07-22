# TASK-ID: v2-minimization-production-comparison-evidence

## Goal

Freeze receipt-verifiable checkpoint/restart and operational-versus-independent trajectory comparison evidence before any production result is observed.

## Scope

- Bind uninterrupted, paused-checkpoint, resumed-result, and trajectory digests for all three checkpoint cases.
- Align evaluated operational and independent steps by exact evaluation index, iteration, trial, and outcome; retain explicit non-comparable dispositions for expected fail-closed traces.
- Predefine per-step and aggregate raw/evaluated coordinate max/RMS error, energy max/RMS error, trace-length, branch, rejection-sequence, and count dispositions.
- Reuse the frozen final-coordinate `1e-8 angstrom` and final-energy `1e-10 kcal/mol` upper bounds for trajectory max/RMS checks; do not tune after observing production results.
- Carry comparison rows through the canonical observation, result receipt, and independent result-review verifier with omission, reorder, cross-wire, non-finite, and digest-tamper rejection.

## Current Progress

- The frozen comparison contract, runner/writer/review binding, three checkpoint evidence rows, exact alignment, per-step and aggregate metrics, explicit expected-failure non-comparability, and tamper rejection are implemented.
- A non-production in-process 14-case implementation check passes all 14 trajectory rows, including both fixed-Born rows, and exact uninterrupted/paused/resumed equality for all three checkpoint cases.
- The observed implementation-only maxima are `3.907985046680551e-14 kcal/mol` for trajectory energy and `1.6653345369377348e-15 angstrom` for raw/evaluated coordinates, within the frozen pre-observation bounds. Six expected fail-closed rows remain explicitly non-comparable and there are no unexpected failures.
- No production receipt or independent human disposition exists; S0 and S1 remain closed.

## Non-goals

- No production execution, key provisioning, second-host claim, external solver result, S0 approval, S1 work, fitting, or product/scientific promotion.

## Likely Files Or Search Targets

- Minimization validation protocol, runner, receipts, writer, and result-review modules
- Focused runner/writer/result-review tests and evidence-roadmap/capability records

## Verification

- Valid aligned/rejected/fail-closed comparisons plus missing, reordered, coordinate/energy tamper, count, branch, checkpoint, and receipt cross-wire tests.
- Complete minimization contract-chain tests, Ruff, capability/YAML equality, architecture guard, and `git diff --check`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop before changing a claim flag or using observed production values to set a threshold.

## Risk Level

R3

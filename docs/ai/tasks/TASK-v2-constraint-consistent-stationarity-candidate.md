# TASK-v2: Constraint-Consistent Stationarity Candidate

## Goal

Add a versioned, claim-closed CPU-float64 constrained minimization candidate that
can satisfy distance-constraint and tangent-force thresholds at the same coordinates.

## Scope

- Preserve the frozen 14-case protocol, native OpenMM 6/8 receipt, and failure disposition.
- Use strict deterministic equal-weight distance projection with a `1e-14 Å` internal bound.
- Retain the public acceptance bounds `constraint <= 1e-10 Å` and
  `tangent force <= 1e-8 kcal/mol/Å`.
- Permit stationarity-polish acceptance only when tangent force strictly decreases
  and energy is no more than `1e-10 kcal/mol` above the best accepted energy.
- Bound iterations, backtracks, displacement, projection sweeps, and all failure rows.
- Provide exact checkpoint/restart and same-coordinate Engine/OpenMM comparison.

## Non-goals

- Do not rewrite or supersede an existing frozen receipt.
- Do not claim native OpenMM L-BFGS convergence, scientific validation, or S0 completion.
- Do not broaden force-field chemistry, constraint weighting, or periodic fixed-Born scope.

## Likely Files Or Search Targets

- New `betelgeuze_engine_v2/physics/` candidate module.
- New `betelgeuze_engine_v2/offline/` same-coordinate comparison module.
- Focused unit tests and claim-closed evidence documentation.

## Verification

- Candidate config/hash, strict projection, both constrained aliases, fixed-Born aliases,
  exact restart, fail-closed/tamper behavior, and independent OpenMM evaluation.
- Focused pytest, Ruff, architecture checks, package build/install smoke, and
  `./scripts/ai-verify.sh` when present.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop if the frozen receipts or their source-bound modules would need modification.

## Risk Level

R3

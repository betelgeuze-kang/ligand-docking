# TASK-v2: Minimization Stationarity Successor Protocol

## Goal

Add a separate, claim-closed 14-case successor execution that applies the
constraint-consistent stationarity candidate to the four constrained aliases.

## Scope

- Reuse the frozen 14-case inputs and retain their semantic order.
- Keep the four unconstrained-v1 rows on the frozen operational and independent paths.
- Run the four constrained-v2 aliases with the stationarity candidate and a
  standard-library, tuple-arithmetic independent oracle.
- Re-execute all six expected fail-closed rows with exact dispositions.
- Record absolute tangent force, constraint residual, energy/coordinate oracle error,
  accepted/rejected/evaluation counts, complete traces, and restart equality.
- Bind the existing same-coordinate Engine/OpenMM candidate receipt.

## Non-goals

- Do not alter or supersede a frozen protocol, production receipt, or native OpenMM result.
- Do not claim S0 completion, two-host reproduction, independent review, or validation.
- Do not broaden chemistry, periodic fixed-Born, or equal-weight constraint scope.

## Likely Files

- New independent stationarity oracle and successor protocol modules.
- Focused unit tests and claim-closed roadmap/status documentation.

## Verification

- All 14 rows retained; 8 pass rows and 6 exact fail-closed rows.
- Constrained absolute tangent force `<= 1e-8 kcal/mol/Å` and constraint residual
  `<= 1e-10 Å`; independent final energy/coordinate errors within frozen bounds.
- Complete energy/coordinate/failure traces and exact checkpoint/restart.
- Focused pytest, Ruff, architecture checks, and `./scripts/ai-verify.sh` if present.

## Risk Level

R3

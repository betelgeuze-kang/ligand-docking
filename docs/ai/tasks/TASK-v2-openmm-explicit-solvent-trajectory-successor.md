# TASK-v2: OpenMM Explicit-Solvent Trajectory Successor

## Goal

Add a separate claim-closed OpenMM Reference successor for materialized TIP3P
water, Na/Cl ions, constrained NVE, and bounded direct-Ewald convergence.

## Scope

- Preserve the frozen NVE/OpenMM candidate source and receipt unchanged.
- Materialize three exact 12 Å cases: two waters only, two waters plus NaCl,
  and a +1 solute neutralized by Cl.
- Run four nominal `1e-6 ps` steps with Ewald indices `(2,2,2)` and restart at 2.
- Reuse the preregistered same-coordinate energy `1e-9`, force max/RMS
  `1e-7/1e-8`, coordinate/velocity `1e-7/1e-6`, constraint
  `1e-9/1e-8`, drift `1e-6`, and restart thresholds.
- On the salted case, compare the same `8e-6 ps` horizon at
  `4e-6×2`, `2e-6×4`, and `1e-6×8`; require medium-to-fine coordinate and
  velocity errors `<=2.5e-7 Å` and `<=2.5e-5 Å ps^-1` and no larger than
  coarse-to-fine.
- At identical salted coordinates compare reciprocal bounds 2, 3, and 4;
  require bound-3 to bound-4 energy/force-max gaps `<=5e-2` in kcal units
  and no larger than bound-2 to bound-4.
- Retain non-neutral, boxed-source, missing-mass, and >16-atom oracle failures.

## Non-goals

- Do not claim equilibrated liquid, density/diffusion/RDF/dielectric evidence,
  accepted long-time drift, PME, triclinic, two-host review, GPU parity, or P2.

## Likely Files

- New offline successor/receipt module, focused tests, CLI packaging, and docs.

## Verification

- Exact preparation replay, all traces/metrics/failures, robust reexecution,
  secure no-overwrite I/O, focused pytest, Ruff, architecture, and wheel smoke.

## Risk Level

R3

## Observed Disposition — 2026-07-24

The reviewed input-only configuration is frozen at
`e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5`.
No threshold or physical input was changed after observation.

- All three rigid-water rows exceed the preregistered `1e-9 Å` position
  constraint threshold. The pinned OpenMM Reference source automatically maps
  closed three-atom constraint loops to SETTLE and narrows the constraint
  distances to `float`; the largest observed residual is about `4.67e-8 Å`.
- The water/no-ion and charged-solute/counterion inputs contain a charged pair
  exactly at the `4 Å` cutoff. Engine neighbor inclusion and OpenMM
  `step(rc-r)` differ at equality, so those rows also retain the predefined
  force-max, force-RMS, and trajectory-velocity failures.
- Both implementations pass the absolute timestep-convergence bounds. The
  Engine coordinate max-error sequence is non-monotone at approximately the
  `1e-11 Å` numerical floor, so the preregistered monotonic check remains
  failed and dispositioned rather than relaxed.
- Both implementations pass all direct-Ewald bound-3 versus bound-4 absolute
  and monotonic checks. All four negative rows fail closed as specified.

This result is failure-inclusive implementation evidence only. It does not
open explicit-solvent, long-time NVE, Ewald, scientific, product, or P2 claims.

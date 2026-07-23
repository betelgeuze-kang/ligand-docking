# TASK-v2: OpenMM Reference NVE Trajectory Comparison

## Goal

Add a claim-closed, same-input OpenMM Reference comparison for the existing
CPU-float64 velocity-Verlet, SHAKE/RATTLE, and neutral direct-Ewald path.

## Scope

- Freeze one unconstrained ion-pair case and one coupled-constraint water-like case.
- Use orthorhombic PBC, require-neutral direct Ewald, and a finite reciprocal lattice.
- Map the same force terms independently into OpenMM custom forces.
- Use OpenMM's documented velocity-Verlet/RATTLE `CustomIntegrator` sequence.
- Record every-step coordinates, velocities, energies, forces, constraint residuals,
  NVE drift, engine exact restart, and OpenMM split-run restart comparison.
- Include exact failure dispositions for nonperiodic, net-charged, and triclinic inputs.
- Pre-register bounds: energy `1e-9 kcal/mol`, force max/RMS `1e-7/1e-8`,
  coordinate/velocity `1e-7 Å / 1e-6 Å ps^-1`, constraint position/velocity
  `1e-9 Å / 1e-8 Å ps^-1`, per-run drift `1e-6 kcal/mol`, and OpenMM restart
  coordinate/velocity/energy `1e-12/1e-11/1e-12` in their corresponding units.

## Non-goals

- Do not alter frozen NVE, SHAKE/RATTLE, Ewald, minimization, or OpenMM receipts.
- Do not claim PME, net-charge background, triclinic, GPU parity, two-host
  reproduction, independent review, production validation, or P2 completion.

## Likely Files

- New `betelgeuze_engine_v2/offline/` comparison and receipt module.
- Focused unit tests, package CLI wiring, and claim-closed status documentation.

## Verification

- Configuration digest, two pass rows, three failure rows, all metrics and traces,
  source/runtime identity, robust receipt verification, secure no-overwrite I/O,
  installed CLI, focused pytest, Ruff, architecture check, and `ai-verify` if present.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop if the comparison requires changing a frozen source-bound module or receipt.

## Risk Level

R3

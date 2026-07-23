# TASK-v2: OpenMM-Force Double-RATTLE Successor

## Goal

Add a separate claim-closed trajectory oracle that combines independently
mapped OpenMM Reference forces with a double-precision, Engine-independent
SHAKE/RATTLE implementation on fresh non-cutoff-boundary TIP3P/ion inputs.

## Evidence Status

This is a development successor, not a confirmatory scientific protocol.
Thresholds are frozen only after exploratory implementation work exposed the
native OpenMM SETTLE and exact-cutoff limitations in the preserved predecessor
receipt. A future fresh holdout, two-host run, and independent review are still
required before any scientific acceptance.

## Scope

- Preserve both predecessor NVE/OpenMM modules and receipts unchanged.
- Materialize three exact systems in a `13.5 Å` cubic cell using lattice
  spacing `3.4 Å`, four TIP3P waters, and source cutoff/switch values `4/3 Å`:
  neutral solute, neutral solute plus NaCl, and +1 solute plus Cl.
- Require atom counts `13/15/14`, neutrality, full orthorhombic PBC, and at
  least `0.25 Å` separation between every force-active pair distance and the
  cutoff at the input and at every retained Engine/oracle frame.
- Use deterministic nonzero binary64 velocities derived only from atom index.
- Run 16 steps at `1e-4 ps`, direct-Ewald alpha `0.35 Å^-1` and reciprocal
  indices `(2,2,2)`, with restart at step 7.
- Evaluate forces with the pinned OpenMM Reference mapping, but integrate with
  a separate binary64 sequential mass-weighted Gauss--Seidel projection:
  position SHAKE corrections use the previous constrained pair vector,
  velocity RATTLE corrections use the projected current pair vector, and both
  use minimum-image vectors, `1e-12` internal residual tolerances, and at most
  500 sweeps.
- The oracle implementation must not import or call Engine v2 NVE,
  SHAKE/RATTLE, neighbor-list, or force evaluators.
- Retain every Engine and oracle energy, force, coordinate, velocity,
  constraint residual, projection sweep, restart, and checkpoint identity.

## Frozen Development Metrics

- Same-coordinate energy error: `<=1e-9 kcal/mol`.
- Same-coordinate force max/RMS error: `<=1e-7/1e-8 kcal/mol/Å`.
- Trajectory coordinate error: `<=2e-7 Å`.
- Trajectory velocity error: `<=2e-4 Å/ps`.
- Trajectory total-energy error: `<=2e-6 kcal/mol`.
- Per-implementation position/velocity residual:
  `<=1e-9 Å` and `<=1e-8 Å/ps`.
- Per-implementation energy drift: `<=1e-6 kcal/mol`.
- Engine restart must remain bit-exact.
- Oracle serialized checkpoint/resume must remain bit-exact in coordinates,
  velocities, energy, trace head, and projection counts.

## Failure Rows

- cutoff-margin violation
- non-neutral direct Ewald
- missing explicit mass
- more than 16 atoms
- exhausted position-projection sweep budget
- tampered oracle checkpoint

## Non-goals

- Do not reinterpret or supersede the rejected SETTLE receipt.
- Do not claim an independent external full integrator, equilibrated liquid,
  liquid/ion observables, accepted long-time drift, PME, two-host
  reproducibility, GPU parity, scientific validation, product readiness, or P2.

## Likely Files

- New standalone double-RATTLE oracle.
- New offline comparison/receipt CLI.
- Focused tests, packaging guards, and evidence-bound documentation.

## Verification

- Import-separation test.
- Exact input audit and replay.
- Complete metric/failure/restart reproduction.
- Secure mode-0600 no-overwrite receipt.
- Focused pytest, Ruff, architecture, deterministic wheel, and installed CLI
  verification.

## Risk Level

R3

## Preserved Development v1 Result

The first input-only configuration
`332e675b2c45a6fffca102559ddd4bca2a11e24e592d0daaca6807417af36682`
used current-vector nonlinear position corrections. Observation
`478745074eb22318fad3cdd7427c0cdb77511bb299cd7413770eaee5ec71fab8`
passed two of three physical rows and all six failure rows. The +1 solute/Cl
row retained an oracle drift failure of approximately
`1.59e-6 kcal/mol` against the unchanged `1e-6` gate. Its mode-0600
superseded-development receipt has file SHA-256
`c1cadc22ffe8b55e8ac810097868d617ba4517bfc7ab8df26474b69181009ede`.

This result is preserved rather than rewritten. Algorithm revision `1.1.0`
replaces the position-correction direction with the previous constrained pair
vector used by standard SHAKE while keeping the same corpus and metrics. It
must receive a new configuration and observation identity.

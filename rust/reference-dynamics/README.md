# Betelgeuze reference dynamics

This crate is an independent scalar `f64` oracle for minimization, short
molecular dynamics, distance constraints, and checkpoints. It does not import
the native runtime, the C++/HIP production evaluators, an external solver, or
the independent energy-oracle crate. A caller supplies potential energy and
forces through a small callback trait.

Canonical units are angstrom, kcal/mol, dalton, femtosecond, and kelvin. The
frozen conversion from force to acceleration is `4.184e-4`, and the molar gas
constant is `0.0019872042586408316 kcal/(mol K)`.

The deterministic algorithms are:

- steepest descent with bounded Armijo backtracking;
- velocity Verlet;
- BAOAB Langevin with an exact Ornstein-Uhlenbeck update;
- canonical-order, mass-weighted SHAKE/RATTLE distance projection;
- Philox4x32-10 normals keyed by seed, absolute step, and atom index; and
- a canonical little-endian checkpoint with SHA-256 topology and payload
  digests.

Positions remain unwrapped. Only constraint displacement uses the half-open
orthorhombic minimum image `[-L/2, L/2)`. All public operations validate finite
inputs and update caller-owned state transactionally.

Minimization leaves the absolute step unchanged. It preserves unconstrained
velocity bits; for constrained systems it RATTLE-projects velocities against
the accepted final geometry before committing the state.

For a non-empty integration call, the initial state is SHAKE/RATTLE projected
before the initial report values are measured. A zero-step call is a strict
state no-op and reports the unmodified state. The temperature convention
`dof = 3*N - C` requires independent instantaneous constraint-Jacobian rows;
the oracle checks this rank and rejects singular/redundant constraint states.

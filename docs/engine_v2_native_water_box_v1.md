# Engine V2 native two-water CPU development slice v1

This slice moves the frozen two-water development fixture from a Python-only
oracle into the shared native molecular state and dynamics owners. It is
engineering evidence, not a production or scientifically validated MD model.

## Frozen identity and units

The public profile is
`config/engine_v2_native_water_box_profile_v1.json`, SHA-256
`2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e`.
The Rust runtime embeds those exact bytes, and its focused test freezes the same
digest. The profile records angstrom, kcal/mol, dalton, femtosecond, and
elementary-charge units.

The rigid-water successor is
`config/engine_v2_native_water_box_constraints_profile_v1.json`, SHA-256
`8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507`.
It binds the unconstrained profile's exact digest rather than changing that
already-merged identity. The runtime embeds and independently hashes these
successor bytes as well.

The periodic CPU traversal successor is
`config/engine_v2_native_periodic_neighbor_list_profile_v1.json`, SHA-256
`ee2c64b3e40ec1905a97b0c2646e36c59fe30f674adfd019dde016e2637e3628`.
It binds the rigid-water successor's exact digest and is embedded into the
runtime without changing either earlier profile identity.

The bounded ion successor is
`config/engine_v2_native_water_ion_profile_v1.json`, SHA-256
`409902e5f6776bd58c76f80a572c9cf978f7e2f4938003e5609036bfe91c631f`.
It admits only the explicit identities `(atomic_number=11, formal_charge=+1)`
and `(atomic_number=17, formal_charge=-1)`. Their TIP3P-targeted `Rmin/2` and
epsilon values are bound to Joung and Cheatham,
[DOI 10.1021/jp8001614](https://doi.org/10.1021/jp8001614), and converted to the
native sigma convention by `sigma = 2 * (Rmin/2) / 2^(1/6)`. Every other
element/charge identity returns a domain-specific typed error rather than an
implicit fallback.

The profile is an explicit successor to the Python development profile merged
in PR #340. It binds that predecessor's exact SHA-256 and records the semantic
changes: the canonical native ABI Coulomb constant plus native cutoff and
switch settings. This provenance does not assert independent review,
calibration, or applicability of a named published water force field.

## Native path

The single-water entry point evaluates one frozen unconstrained water with the
same native owners and requires C++ reference/Rust CPU energy and force parity.
`DevelopmentWaterBoxV1` constructs six atoms, four harmonic O-H bonds, two
harmonic H-O-H angles, intrawater nonbonded exclusions, and a fully periodic
14-angstrom orthorhombic cell through the shared native `System`, `ForceField`,
and `Simulation` types. Interwater Lennard-Jones and Coulomb terms use a
6.99-angstrom cutoff and a quintic switch beginning at 6.5 angstrom.

Only the C++ CPU reference and Rust CPU backends are admitted. The profile does
not silently select HIP, and this work performs no HIP-device execution.

Fully periodic orthorhombic CPU evaluations now build a deterministic cell
list on every nonbonded evaluation. Each cell width is at least
`max(cutoff, minimum_pair_distance)`; the 27 wrapped neighboring cell keys are
deduplicated; exact minimum-image candidates within that search radius are
emitted in ascending `(atom_i, atom_j)` order. Evaluation then validates the
minimum distance before applying the inclusive cutoff, preserving fail-closed
behavior when the configured minimum exceeds the cutoff. Mixed-axis and
nonperiodic systems retain the canonical all-pairs path. The common ordering
preserves binary64 accumulation parity with the independent all-pairs oracle.
Both CPU implementations use a conservative squared-distance comparison while
admitting cell candidates, so candidates beyond the search radius do not
require a square root. The one-ULP outward bound preserves the exact inclusive
binary64 boundary. The C++ reference stores cell assignments in one sorted
contiguous array, matching the Rust CPU traversal shape and avoiding per-cell
tree nodes. These are implementation changes under the same mathematical
profile and do not constitute timing evidence or an acceleration claim.
The v1 profile remains the immutable every-evaluation builder baseline.

The two CPU evaluators also expose an internal, non-public path that consumes a
caller-owned canonical neighbor-pair slice. Both implementations require
strictly increasing, unique, in-range `atom_i < atom_j` rows and reject the
slice for non-fully-periodic systems. The Rust path crosses a separate hidden
provider symbol and remains transactional on malformed rows. Buffered slices
may contain pairs outside the force cutoff because the ordinary pair evaluator
still applies exclusions, minimum-distance validation, and the exact cutoff in
canonical order. The native dynamics dispatcher constructs one canonical slice
per fully periodic CPU evaluation and supplies the same representation to the
selected C++ or Rust evaluator. The public stateless context continues to use
the backend-owned builder on every call.

The v2 successor adds a private `Simulation`-owned cache for fully periodic
CPU dynamics only. It builds canonical pairs to
`max(cutoff, minimum_pair_distance) + 1.0` angstrom and reuses that slice only
while every atom remains strictly below 0.5 angstrom from its unwrapped build
reference. The existing pair evaluator still applies minimum-distance and
exact-cutoff semantics. Cache mutations follow the existing transactional
integrate/minimize boundary; failed operations cannot commit semantic cache
payloads or counters.
The cached reference coordinates and canonical pairs live in one immutable
shared payload, so an operation rollback snapshot retains that payload rather
than deep-copying its atom and pair arrays; a rebuild publishes a new payload
only after it succeeds. Periodic CPU rebuilds also retain simulation-owned
cell-key, sorted-assignment, neighbor-cell, and candidate-index scratch storage.
The public stateless evaluator still uses call-local scratch, while an
internally shared simulation scratch detaches before rebuilding. Failed
operations may consume only scratch state/capacity; pair payloads and cache
counters retain their rollback semantics.
The immutable publication path retains three simulation-owned buffers: one
published payload and two reusable scratch payloads. A transaction snapshot
may pin the previously published buffer while every later rebuild in that same
call alternates the other two. After their first allocation, all three
reference-coordinate vectors plus the canonical-pair vector retain storage.
On failure the original publication is restored and the failed publication
becomes derived scratch. This preserves cache payload and counter rollback
without reallocating the steady-state publication graph, including calls that
cross the rebuild threshold more than once.
Reuse inspection also has an exact component-wise interior fast path. If every
absolute displacement component is below binary64
`0x1.279a74590331cp-2` angstrom, the compile-time bound `3*t*t < 0.25` proves
the atom is strictly inside the existing 0.5-angstrom Euclidean reuse sphere,
so no square root is evaluated. Conversely, any absolute component at or above
0.5 angstrom proves the Euclidean displacement reaches the rebuild boundary and
is rejected without a square root. NaNs and the finite shell between these
component bounds retain the original `hypot` decision, including the strict
boundary rule.
Checkpoint bytes and the static fingerprint do not include this derived state,
and a successful checkpoint load invalidates it. Mixed/nonperiodic and HIP
paths do not consume the cache. This behavior has no timing threshold or
performance/acceleration claim.

CPU dynamics also retain one simulation-owned set of force-vector allocations
across repeated force evaluations and later transactional integrate or
minimize calls. Zero-step integration does not consume or initialize this
storage. The scratch is derived state excluded from checkpoint bytes and
semantic rollback; an internal evaluation failure may consume its contents or
capacity. The public stateless evaluator remains transactional, C++ reference
and Rust CPU use the same lifetime rule, and HIP evaluation is unchanged. This
structural allocation reuse carries no measured timing evidence or acceleration
claim.

Constrained CPU minimization also retains one per-atom projected-force
magnitude vector. A projection sweep computes each atom norm once per distinct
direction state, reuses the same binary64 value for every corrected constraint
endpoint, and returns the same cached maximum to the minimizer instead of
evaluating those norms again.
Failed operations may consume this derived scratch, while unconstrained and
HIP calls leave the persistent vector untouched. Checkpoint bytes, semantic
rollback, per-constraint tolerances, and projection updates are unchanged.
This structural reuse has no timing or acceleration claim.

Constraint correction also reuses exact binary64 residual scalars inside each
CPU iteration. RATTLE computes the displacement/relative-velocity dot product
once before using it for both the radial tolerance and the accepted correction,
and constrained force projection applies the same rule. Final constraint-state
validation computes the displacement norm once for both position and velocity
residuals. Each distance constraint also retains the two exact inverse masses
and their exact sum derived from immutable simulation-owned particle masses, so
SHAKE and RATTLE do not repeat those divisions during correction sweeps. The
derived values are copied into checkpoint-validation candidates but remain
outside checkpoint bytes and the static fingerprint. Constraint order,
tolerances, corrections, failures, and HIP behavior are unchanged; this compute
reduction is untimed.

The CPU minimizer likewise retains its three projected-force direction vectors
across later minimize calls. Each projection still copies the current force
channels before applying the same bounded constraint projection, so no prior
scratch values participate in a result. This derived storage is excluded from
checkpoint and rollback semantics and may be consumed on failure. HIP
minimization continues to use call-local direction storage. This lifetime
change is untimed and carries no acceleration claim.

The integrator likewise skips unconstrained-coordinate snapshots when no
distance constraints exist. When constraints are present, the simulation
retains one three-channel snapshot buffer across every drift in an integrate
call, including both BAOAB half-drifts, and across later integrate calls.
SHAKE/RATTLE ordering and binary64 updates are unchanged. This is derived
scratch excluded from checkpoint and rollback semantics, and it carries no
timing evidence or acceleration claim.

Public integrate and minimize transactions operate in place behind an RAII
rollback. Nonzero integration and minimization snapshot only the six mutable
position and velocity channels, the absolute step, and semantic neighbor-cache
metadata; immutable particle, force-field, constraint, and integrator
configuration are not copied. The simulation retains the six rollback-vector
allocations across later nonzero calls, including calls that fail and restore
state. Checkpoint validation constructs its transaction candidate without
copying this derived scratch. A zero-step integration snapshots only the
scalar/cache metadata.
Failures restore the six channels in place, preserving every borrowed
particle-view address, while success needs no second six-channel copy. These are
unmeasured lifetime properties and carry no acceleration claim.

Constrained simulations also retain the Gram-matrix and normalized-direction
storage used to revalidate constraint-Jacobian independence after integration,
minimization, and checkpoint loading. The constraint count is immutable, so
later validations resize to the same logical shape without replacing capacity.
This derived scratch is excluded from checkpoint bytes and semantic state; its
contents may change on a failed validation. The elimination order, pivot rule,
rank tolerance, and accepted or rejected states are unchanged.

The CPU minimizer retains one simulation-owned candidate `System` across all
bounded Armijo attempts, iterations, and later minimize calls. The first active
call copies the complete system once; later calls refresh only the three
velocity channels, while immutable mass, charge, and unit state retain their
original storage. Calls already converged before line search do not initialize
the candidate. Each trial overwrites every position channel from the unchanged
accepted state; an accepted trial swaps those three buffers into the active
simulation under a position-storage guard. At exit the guard restores the
original borrowed-view storage, copying final positions once only when the
alternate buffer holds the accepted state. The candidate is derived scratch
excluded from checkpoint and rollback semantics, and a failed call may alter
this derived candidate without changing semantic state. HIP minimization
retains its call-local candidate. Evaluation order, constraint projection,
accepted coordinates, and transaction semantics are unchanged. This also
carries no timing evidence or acceleration claim.

## Frozen development observations

The independently implemented Python oracle and both native CPU backends agree
within the focused binary64 tolerance. The frozen observations are:

- standalone single-water equilibrium energy is below `1e-24` kcal/mol and its
  force components preserve C++ reference/Rust CPU parity;
- initial two-water potential energy: `-2.235452238349433` kcal/mol;
- 100-step Velocity Verlet initial total energy:
  `-2.2354281465712305` kcal/mol;
- 100-step final total energy: `-2.2354282714680176` kcal/mol;
- absolute total-energy drift: `-1.2489678713478725e-7` kcal/mol;
- 128-step BAOAB state is repeatable for the frozen explicit seed and preserves
  C++ reference/Rust CPU parity;
- a Rust checkpoint restores all positions, velocities, masses, charges,
  integrator state, absolute step, and RNG continuation exactly.

The rigid-water lane adds six frozen distance rows: two O-H and one H-H row per
water. Its H-H target is `1.5139006545273224` angstrom, derived from the frozen
coordinates; both SHAKE position and RATTLE radial-velocity tolerances are
`1e-10`, with at most 100 deterministic sweeps. Focused tests require 12
degrees of freedom, residuals within the frozen tolerances, C++ reference/Rust
CPU state parity after 100 NVE and 128 seeded BAOAB steps, and bit-exact 32-step
continuation from a Rust checkpoint.

The periodic cell-list test freezes a cutoff-boundary pair, a pair crossing the
box boundary, canonical ordering, and invariance to independent integer-box
translations and atom permutations. The existing native water and
independent-oracle tests then
exercise the cell-list path through both CPU evaluators for energy, force, NVE,
BAOAB, constraints, and checkpoint parity.

A separate neutral static fixture adds one Na+ and one Cl- to the two-water
box. The independent all-pairs oracle checks every analytic force component by
central difference and both CPU evaluators. It is deliberately not integrated
as a trajectory, concentration model, or equilibrium observation.

These are tiny-fixture development observations. They are not equilibrium NVT
statistics, stability validation, throughput measurements, or acceleration
evidence.

## Remaining boundaries

The slice has functional neighbor-list reuse but no performance evidence,
general ion preparation, PME/Ewald,
NPT/barostat, peptide or protein system, public benchmark, production-MD,
free-energy, scientific-claim, product, Stage 0, Fresh-128, reservation, or
performance-claim authority. The rigid-water checks are synthetic CPU
development validation only; those broader dependencies remain separate.

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
This first functional list has no skin or reuse cache.

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
the backend-owned builder on every call. Neither path reuses a list yet; this
shared dynamics boundary is the prerequisite for a later `Simulation`-owned
skin/reuse cache.

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

The slice has no neighbor-list reuse or performance evidence, general ion
preparation, PME/Ewald,
NPT/barostat, peptide or protein system, public benchmark, production-MD,
free-energy, scientific-claim, product, Stage 0, Fresh-128, reservation, or
performance-claim authority. The rigid-water checks are synthetic CPU
development validation only; those broader dependencies remain separate.

# Engine V2 direct-Ewald scalar reference v1

Issue #434 begins the long-range electrostatics dependency after the bounded
short-range composition slice merged in PR #433. Its first artifact is an
actual direct-Ewald energy-and-force evaluator, not a PME placeholder or a
documentation-only contract.

The evaluator lives in the standalone `rust/reference-ewald` crate so that it
cannot mutate the consumed native fixed64 CPU-v7 source closure. It accepts a
neutral, fully periodic orthorhombic system and explicitly freezes the Coulomb
constant, real-space cutoff, Ewald splitting parameter, reciprocal integer
bounds, traversal order, minimum-image tie rule, exclusions, and Coulomb pair
scales. The result separates real, reciprocal, self, and local pair-correction
energies and returns analytic forces for every atom.

All positions are reduced per axis into the primary cell before minimum-image
subtraction and reciprocal phase construction. This prevents trigonometric
range-reduction drift for long unwrapped trajectories; the property suite
includes an image displaced by one million box lengths.

The immutable profile is
`config/engine_v2_direct_ewald_reference_profile_v1.json`. Its four-charge
fixture includes one excluded pair and one half-scaled pair. Debug and release
produce identical frozen IEEE-754 values. All 12 analytic force components are
checked against central finite differences. Additional properties cover global
translation, integer images, complete atom permutation, global charge
inversion, near-zero net force, bitwise repetition, reciprocal-bound
convergence, and typed malformed inputs.

The exact profile SHA-256 is
`5d0d46f737edd30f86a20346371198d1ca158b57841416098d44caa7d593b439`.
The profile separately binds the evaluator source, frozen fixture, and
standalone Cargo lockfile hashes.

The reciprocal-bound values are finite development observations, not an error
guarantee: relative to bound 9, the absolute total-energy differences for
bounds 3, 5, and 7 are approximately `2.181e-1`, `1.196e-3`, and `1.612e-6`
kcal/mol. Native CPU integration must allocate a separately versioned ABI and
must compare against this independent evaluator before dynamics integration.

## Claim boundary

This is a deterministic four-charge CPU reference fixture. It is direct Ewald,
not PME. It grants no bulk-solvent, equilibration, production-MD, accuracy at
scale, scientific, performance, acceleration, HIP-device, product, reservation,
Stage 0, Fresh-128, public-benchmark, or operational molecular authority. The
four external reservation/historical-execution blockers and 32 unresolved
operational decisions remain controlling.

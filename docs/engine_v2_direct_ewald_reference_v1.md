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

Real-space image selection uses strict comparisons after primary-cell reduction,
which preserves atom-swap antisymmetry on both sides of the half-cell boundary.
An exact half-cell real-space tie uses the canonical positive primary-cell
representation. An exact half-cell local pair correction is rejected with a
typed `AmbiguousPairCorrectionImage` error because no single-image force
direction can preserve both translation and permutation invariance. A unit pair
scale or any pair rule involving a zero charge is a semantic no-op and skips
that image selection entirely.

The scalar contract admits a bounded physical/numerical envelope: coordinates
through `1e12` angstrom; cell lengths from `1e-6` through `1e9` angstrom;
nonzero charge magnitudes from `1e-12` through `16` elementary charge; and
bounded alpha, cutoff, dielectric, and minimum-distance settings recorded in
the immutable profile. The minimum pair distance must be below the cutoff. This
keeps charge products and the squared minimum distance normal before inverse-
distance arithmetic while preserving the frozen ordinary-input operation order.

Neutrality uses a canonical absolute-magnitude/total order and Neumaier
compensated sum, avoiding input-order-dependent admission. Cell volume uses a
canonical min-times-max-then-middle product to avoid axis-order intermediate
overflow for finite mathematical volumes. Validation also caps the combined
real-pair and twice-per-vector atom phase work at 10,000,000 work units.

The immutable profile is
`config/engine_v2_direct_ewald_reference_profile_v1.json`. Its four-charge
fixture includes one excluded pair and one half-scaled pair. Debug and release
produce identical frozen IEEE-754 values. All 12 analytic force components are
checked against central finite differences. Additional properties cover global
translation, integer images, complete atom permutation, global charge
inversion, near-zero net force, bitwise repetition, reciprocal-bound
convergence, near-half-cell atom swaps, rounded upper-bound primary-cell
reduction, unit-scale and zero-charge no-ops, the numeric envelope, and typed
malformed inputs.

The exact profile SHA-256 is
`f68ba0f048a770c77eb05126ff6e7e52a0bd688ad0a2b8a69e8658cf3fe26041`.
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

# Engine V2 direct-Ewald scalar reference v1

Issue #434 begins the long-range electrostatics dependency after the bounded
short-range composition slice merged in PR #433. Its first artifact is an
actual direct-Ewald energy-and-force evaluator, not a PME placeholder or a
documentation-only contract.

The evaluator lives in the standalone `rust/reference-ewald` crate so that it
cannot mutate the consumed native fixed64 CPU-v7 source closure. It accepts a
representationally exact-neutral, fully periodic orthorhombic system and explicitly freezes the Coulomb
constant, real-space cutoff, Ewald splitting parameter, reciprocal integer
bounds, traversal order, minimum-image tie rule, exclusions, and Coulomb pair
scales. The result separates real, reciprocal, self, and local pair-correction
energies and returns analytic forces for every atom.

All positions are reduced per axis before minimum-image subtraction and
reciprocal phase construction. This prevents trigonometric range-reduction
drift for long unwrapped trajectories; the property suite includes an image
displaced by one million box lengths. If `rem_euclid` rounds a supported
negative boundary residual up to the cell length, every nonzero signed residual
is recovered instead of collapsing a distinct position to zero. Only an actual
signed zero is canonicalized to positive zero.

Real-space image selection uses an error-free separation comparison after
periodic reduction, preserving atom-swap antisymmetry on both sides of and at
the half-cell boundary. An exact half-cell local pair correction is rejected with a
typed `AmbiguousPairCorrectionImage` error because no single-image force
direction can preserve both translation and permutation invariance. A unit pair
scale or any pair rule involving a zero charge is a semantic no-op and skips
that image selection entirely. Exact ties use an error-free two-difference
expansion before comparing with half the cell, so a representable separation
just below half is not rejected even when its rounded difference equals half.

The scalar contract admits a bounded physical/numerical envelope: coordinates
through `1e12` angstrom; cell lengths from `1e-6` through `1e9` angstrom;
nonzero charge magnitudes from `1e-12` through `16` elementary charge; and
bounded alpha, cutoff, dielectric, and minimum-distance settings recorded in
the immutable profile. The minimum pair distance must be below the cutoff. This
keeps charge products and the squared minimum distance normal before inverse-
distance arithmetic while preserving the frozen ordinary-input operation order.

Every exponential, sine/cosine pair, complementary error function, and square
root is supplied by the exactly pinned `libm` 0.2.16 dependency rather than a
platform standard-library implementation. Reciprocal structure factors scale
charges by the minimum supported nonzero magnitude, retaining tiny phases that
would underflow if multiplied by charge first. Force terms then incorporate each
wave component before the structure/phase products and pinned exponential,
retaining contributions whose phase-scaled quotient would otherwise vanish.
Real-space energy divides `erfc` first for sub-unit distances and multiplies the
charge/Coulomb prefactor first otherwise. Radial forces use distance-adaptive
damping division and then distance-adaptive Cartesian component scaling. This
retains supported strongly damped energy/forces and subnormal Cartesian force
components whenever the completed value is representable.

Neutrality uses a canonical absolute-magnitude/total order and Neumaier
compensated sum, avoiding input-order-dependent admission, and requires that
sum to be exactly zero because this API defines no neutralizing background.
Cell volume uses a
canonical min-times-max-then-middle product to avoid axis-order intermediate
overflow for finite mathematical volumes. Pair corrections iterate only the
sorted declared rules, not every possible pair. Validation caps real pairs,
declared correction rules, and twice-per-vector atom phase work together at
10,000,000 work units, first using raw rule-row counts before allocating trees
and then the canonical unique-rule count.

The immutable profile is
`config/engine_v2_direct_ewald_reference_profile_v1.json`. Its four-charge
fixture includes one excluded pair and one half-scaled pair. Debug and release
produce identical frozen IEEE-754 values. All 12 analytic force components are
checked against central finite differences. Additional properties cover global
translation, integer images, complete atom permutation, global charge
inversion, near-zero net force, bitwise repetition, reciprocal-bound
convergence, near-half-cell atom swaps, preservation of every rounded nonzero
signed boundary residual, multidimensional boundary translation invariance,
rounded-difference tie classification, tiny-phase structure preservation,
reciprocal wave rescue before phase underflow, representable strongly damped
real energy/forces, pre-allocation rule-work rejection, exact-neutral admission,
subnormal Cartesian force components, unit-scale and zero-charge no-ops, the
numeric envelope, and typed malformed inputs. The exact force bits are those of
the pinned math and operation-order contract.

The exact profile SHA-256 is
`072595df59178a91158a51759694c6ad1cdbaf6898a2dedaaa79ac937ebe0ff8`.
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

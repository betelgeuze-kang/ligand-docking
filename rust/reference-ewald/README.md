# Betelgeuze direct-Ewald reference

This standalone crate is the independent scalar binary64 definition of the
first Engine V2 periodic direct-Ewald development slice. It is intentionally
outside the production Rust workspace and the consumed fixed64 CPU-v7 source
closure. It imports no native compute, accelerator, runtime, Python, or
external molecular-dynamics implementation.

The supported domain is a representationally exact-neutral, fully periodic orthorhombic cell. Canonical
units are angstrom, elementary charge, kcal/mol, and kcal/(mol·angstrom).
With Coulomb conversion `K`, dielectric `epsilon`, splitting parameter `alpha`,
volume `V`, charges `q_i`, and reciprocal vector `k`, the frozen components are:

```text
E_real = K/epsilon sum(i<j,r<=rc) qi qj erfc(alpha r) / r
E_recip = K/epsilon (2 pi/V) sum(k!=0) exp(-k^2/(4 alpha^2))/k^2 |sum_j qj exp(i k.rj)|^2
E_self = -K/epsilon alpha/sqrt(pi) sum_i qi^2
E_pair_correction = K/epsilon sum(sij-1) qi qj/r_ij
```

The last term removes or scales the local full Coulomb interaction for explicit
excluded/scaled pairs after the periodic Ewald sum. Real-space pairs traverse
`i < j`. Reciprocal integer vectors traverse `nx`, `ny`, then `nz`, each from
the negative configured maximum through the positive maximum, omitting only
zero. Forces are analytic negative energy gradients accumulated in the same
order. Positions are reduced with the bounded Euclidean remainder. Binary64
addition can discard the original primary-coordinate bits in a represented
`x + nL`, so periodic-equivalent representations use a frozen `5e-12` relative
comparison tolerance rather than a bitwise-identity claim. A real-space pair
whose distance is within that relative tolerance of the cutoff is rejected with
`AmbiguousRealSpaceCutoff`, preventing image rounding from changing inclusion.
A distance within the same tolerance of the minimum-distance threshold is
rejected with `AmbiguousMinimumPairDistance` before the safety decision.
A supported negative boundary residual that rounds to the upper
boundary is preserved regardless of magnitude; only an actual signed zero is
canonicalized to positive zero. Real-space minimum images then subtract or add one box
length with an error-free expansion only when the exact expanded displacement is above or below the
half-cell boundary. Exact real-space ties retain atom-order antisymmetry. A local
pair correction within the periodic-image tolerance of half-cell is rejected
because a stable single-image force direction cannot be selected. A pair scale of exactly one
or any pair rule involving a zero charge is a semantic no-op and skips local-
correction image selection.

An error-free two-difference expansion supplies the local-correction separation
used by the half-cell tolerance comparison.

Neutrality is checked with a canonical order and Neumaier compensated sum and
must be exactly zero because no neutralizing-background convention is defined.
Cell volume multiplies sorted minimum and maximum lengths before the middle
length. Corrections traverse only sorted declared pair rules. A combined seven-times-real-pair,
seven-times-declared-correction, reciprocal-phase, and phase-origin signature work cap prevents the scalar
reference's individually valid maxima from creating an unbounded evaluation;
raw rule rows are bounded before any pair-rule tree allocation.
The API also rejects finite values outside its documented numeric envelope:
absolute coordinates above `1e12` angstrom, cell lengths outside `[1e-6,1e9]`
angstrom, nonzero charge magnitudes outside `[1e-12,16]` elementary charge,
alpha outside `[1e-12,1e6]` per angstrom, cutoff outside `[1e-8,1e8]`
angstrom, dielectric outside `[1e-12,1e12]`, or minimum pair distance outside
`[1e-8,1e3]` angstrom. The minimum pair distance must also be below the cutoff.
These bounds keep charge products and squared minimum-distance checks normal
before any inverse-distance operation.

All exponential, logarithm, sine/cosine, complementary-error-function, and square-root
operations use the exactly pinned `libm` 0.2.16 dependency. Reciprocal structure
factors normalize charges by the exactly reversible power of two `2^-40`,
canonically order and compensate their cosine and sine terms, and retain tiny
phases without perturbing represented charges. Phases use minimum-image positions
relative to a maximum-absolute-charge atom, with exact magnitude ties resolved by
a nonzero-charge-only rooted signature of relative charge and signed minimum-image
geometry. Their three axis products use a canonical compensated sum; zero-charge atoms
bypass both origin signatures and phase construction. Forces
incorporate each wave component before the structure/phase products, preventing
a small phase-scaled quotient from underflowing before the wave restores a
representable result. Self energy canonically orders and compensates charge-square
accumulation so it is atom-order independent. Real-space energies and per-atom/axis
forces, plus pair-correction energies and forces, use the same canonical compensated
strategy across their pair terms.
Real-space energy divides `erfc` first for sub-unit distances and multiplies the
Coulomb/charge prefactor first otherwise. Force magnitudes use distance-adaptive
damping division and distance-adaptive Cartesian component scaling, preserving
supported subnormal energy and Cartesian force components that are still
representable while damping itself remains normal. A nonzero-charge real-space
pair whose pinned `erfc` or exponential result is subnormal or zero is rejected
with `DampingUnderflow` instead of amplifying a quantized damping value.
Real-space pairs with a signed-zero charge product bypass distance and damping
checks entirely.
Subnormal or exact-zero reciprocal exponentials are combined with each undamped
energy and force in the pinned-log domain. Every completed value that can round
nonzero is reconstructed; only values below the binary64 half-minimum threshold
become zero. A nonzero wave-coordinate product that is subnormal or rounds to
zero is rejected with `PhaseUnderflow` before reciprocal scaling can amplify it.
A vector whose maximum possible completed energy and force are conservatively
bounded below the half-minimum-subnormal threshold is skipped before phase
construction, so irrelevant phase underflow does not reject the input.

`fixtures/direct_ewald_v1.tsv` freezes all four energy components, their total,
and all 12 force components as IEEE-754 bit patterns. The observation example
recomputes the values, finite-difference error, and reciprocal-bound sequence:

```bash
cargo run --manifest-path rust/reference-ewald/Cargo.toml \
  --example profile_observation --locked
```

This is direct Ewald, not particle-mesh Ewald. The four-charge fixture and its
truncation observations do not validate PME, bulk solvent, equilibration,
production MD, accuracy at scale, performance, HIP execution, or any scientific
or product claim.

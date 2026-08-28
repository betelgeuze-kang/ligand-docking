# Engine V2 scalar particle-mesh reciprocal reference v1

Issue #434 step 4 begins with a standalone scalar reference for the reciprocal
particle-mesh calculation. This slice does not implement or validate a complete
particle-mesh Ewald method. Real-space screening, self energy, excluded/scaled
pair corrections, native ABI/runtime integration, dynamics, virial, and
performance work remain outside this boundary.

The implementation is the standalone `rust/reference-pme` workspace. Its
public schema is
`betelgeuze.reference_particle_mesh_reciprocal/1.0.0`. Inputs own four-charge
binary64 positions and charges, an exact-neutral fully periodic orthorhombic
cell, and reciprocal settings. The only returned energy is
`reciprocal_space_kcal_per_mol`; forces are the analytic derivative of that
same mesh energy.

## Frozen numerical method

The primary development fixture uses a `16 x 16 x 16` mesh, order-4 cardinal
B-spline assignment, `alpha = 0.31 / Angstrom`, dielectric 1, and a mesh
origin at the cell origin. Coordinates are reduced per axis before assignment.
The reciprocal zero mode is omitted and no neutralizing background convention
is defined, so neutrality must be exactly representable under the frozen
canonical accumulation.

The scalar radix-2 transform uses z-fast storage and deterministic z, y, then x
axis traversal. Forward transforms use the negative sign and no normalization.
Each inverse one-dimensional transform applies its own `1/N_axis` factor, for
a net `1/(Nx Ny Nz)` normalization. Signed frequencies use the exact mapping
`m = index` when `index < N/2` else `m = index - N`, so the even-grid Nyquist
representative is the negative half-dimension. Discrete cardinal B-spline
modulus deconvolution and all accumulation orders are part of the versioned
contract.

Before assignment or grid allocation, checked arithmetic evaluates the work
signature

`M * (1 + log2(Nx) + log2(Ny) + log2(Nz)) + N * 4^3 * (1 + 3)`.

Here `M` is the mesh-point count and `N` the particle count. The forward and
inverse radix-2 transforms together count
`M * (log2(Nx) + log2(Ny) + log2(Nz))` butterflies. The additional `M` counts
the influence traversal, and the assignment term counts one spread plus three
force-derivative gathers. Inputs above the frozen 16,000,000-unit cap fail with
`CapacityExceeded` before those allocations.

Every normal and rescued influence-spectrum mode shares one exact binary64
power-of-two scale `S = 2^256`. Normal components are stored as
`(influence * Qhat_component) * S`. For a nonzero charge mode, a non-normal
damping value, influence, regular energy term, or corresponding nonzero
influence-spectrum component selects the log-domain path. With
`D = Dx * Dy * Dz`, rescued magnitudes use

```text
log(S * E_component) = log(energy_prefactor) - log(k^2) - 2 log(D)
                       + damping_exponent + 2 log(abs(Qhat_component))
                       + 256 * LN_2
log(S * influence * Qhat_component) = -log(k^2) - 2 log(D)
                                      + damping_exponent
                                      + log(abs(Qhat_component))
                                      + 256 * LN_2
```

`S` itself is exact; the log offset is the frozen binary64 expression
`256 * core::f64::consts::LN_2`. The component's original sign is restored
after exponentiation. Completed scaled log magnitudes at or below
`-745.1332191019411`, the frozen log of half the minimum positive binary64
subnormal, round to zero; larger values use the pinned `libm` exponential.

The common scaled spectrum receives exactly one inverse transform. The force
gather applies
`(-q_i * N_axis/L_axis) * (2 * energy_prefactor * M/S)` only after the
assignment-derivative sum, so normal and rescued force modes have one final
rounding. Energy retains the direct compensated normal path when no mode needs
rescue. Otherwise, `(energy_prefactor * S)` times the normal sum and all scaled
rescued components are compensated together, then divided by `S` once. This
prevents separate normal and rescue lanes from independently rounding away a
representable total.

The work cap bounds accepted meshes to at most `2^19` points and therefore
fewer than `2^20` positive real/imaginary energy components. The 256-bit scale
leaves a 236-bit aggregation margin. Envelope bounds are
`|Qhat| <= 2^16`, `1/k^2 < 2^55`, `1/D^2 < 2^10`, and
`energy_prefactor < 2^111`. The scaled influence spectrum is below `2^337`
(`2^356` under a conservative full-mesh intermediate-growth allowance), and
the scaled energy sum is below `2^484`. Also
`2 * energy_prefactor * M < 2^131` and `|q| * N_axis/L_axis < 2^31`, so the
post-inverse force multiplier is below `2^-94`. With derivative-stencil L1
weight at most `3/2`, a scaled value that rounds to zero cannot later combine
or amplify into a representable unscaled energy or force.

The synthetic rescue regression uses two charges `[16, -16]` at
`[0, 0, 0]` and `[4e8, 0, 0]` Angstrom in a
`[1e9, 1e-6, 1e-6]` Angstrom cell, a `4^3` mesh, alpha `1.15e-10`, and
dielectric `1e-12`. Its first-wave raw damping has all-zero bits, while the
completed reciprocal energy and particle-1 x force are normal and nonzero:
approximately `7.4746417761e-287` and `-1.6999574664e-295`, respectively.
The regression checks both against those references without a unit floor at
relative tolerance `1e-8`, and checks the force against a central energy
difference with a `1000` Angstrom step. It also exercises the half-grid
charge/potential identity and the independent full 3-D direct DFT path.

A second two-charge regression uses positions `[0, 0, 0]` and
`[4e-7, 0, 0]` Angstrom in a `[1e-6, 1e-6, 1e-6]` Angstrom cell, alpha
`1.15e5`, and a `4^3` mesh. At dielectric `1e12`, both raw damping and energy
have all-zero bits while particle-1 x force remains a negative subnormal near
`-1.6999574664e-319` at relative tolerance `1e-3`. At dielectric `2.5e10`,
the same family combines individually underflowing positive components into
energy bits `0000000000000001`. Focused arithmetic tests independently require
that eight rescue-only components and mixed regular/rescue lanes each round
only after combination to that same minimum-subnormal bit pattern.

The point-count ceiling alone would permit a 16 MiB complex grid, but the work
cap rejects every 1,048,576-point mesh. The largest accepted power-of-two mesh
has 524,288 points, subject to particle work. Production therefore holds one
8 MiB complex mesh buffer; a test-only diagnostic charge-grid copy is not
compiled into the public library.

Forces differentiate the assignment weights rather than using an independent
`i k` field. Tests therefore compare all 12 force components with central
finite differences of the same reciprocal mesh energy. A simultaneous
translation by an integral number of mesh cells is a property test. Arbitrary
translations and total-force residuals are bounded mesh-phase accuracy
observations, not exact translation or momentum-conservation claims.

## Independent checks and frozen fixture

The synthetic fixture has positions

```text
[1.25, 2.5, 3.75]
[5.1, 3.2, 8.4]
[10.2, 12.3, 7.7]
[15.4, 17.1, 19.3]
```

in an `[18, 20, 22]` Angstrom cell, with charges
`[0.7, -0.4, -0.6, 0.30000000000000004]`. It is synthetic and exactly
neutral. The fixture TSV freezes one reciprocal energy and 12 Cartesian force
bit patterns. It contains no molecular topology or operational input.

Internal checks cover:

- scalar radix-2 FFT round trip, conjugate symmetry, signed-mode/Nyquist
  mapping, and an independently implemented full three-dimensional triple-sum
  direct DFT;
- B-spline partition of unity, derivative sum zero, periodic boundary
  assignment, and deposited-grid charge conservation;
- the `E = 1/2 sum(rho_grid * phi_grid)` normalization identity;
- all-axis central finite differences, periodic images, integer-grid-cell
  translation, atom permutation, charge inversion, and repeatability;
- typed malformed-input, mesh-capacity, exact-neutrality, and non-finite-result
  failures, including the checked pre-allocation combined work cap;
- raw-damping-underflow rescue to normal nonzero energy and force, rescued
  force/energy finite-difference agreement, rescued half-grid identity, and
  rescued FFT/full-3-D-direct-DFT parity;
- common-scale preservation of a subnormal force when unscaled energy and
  influence-spectrum components round to zero, physical minimum-subnormal
  energy aggregation, and focused rescue-only/mixed-lane exact-bit sums;
- reciprocal-energy accuracy and a numerical reciprocal-force comparison
  against the immutable direct-Ewald reference at reciprocal bound 9 for the
  `8^3`, `16^3`, and `32^3` mesh sequence.

The direct-Ewald API exposes reciprocal energy but only combined analytic
forces. Consequently the independent comparison force is the central
difference of its exposed reciprocal-energy component; its combined force is
never used as a reciprocal oracle.

## Immutable evidence

The generated evidence files are:

- `config/engine_v2_pme_reciprocal_reference_profile_v1.json`;
- `config/engine_v2_pme_reciprocal_reference_profile_v1_sources.json`.

The source manifest is canonical ASCII JSON with sorted unique path,
byte-count, and SHA-256 rows. It binds every non-build file under the
standalone crate, the root workspace exclusion boundary, the immutable
direct-Ewald semantic-oracle inputs, the current immutable PR #438 prerequisite
profile and source manifest, `tools/__init__.py`, and the verifier.
The generated profile and manifest, Python unit consumer, this document, and
workflow are explicitly outside the acyclic source closure.

The profile also freezes the 31-line debug/release observation SHA-256 as
`899845a391e23da253a5f0e2bdb5a78794ec7beb4dabee1f04726d6af1492144`.
CI requires byte-identical debug and release output and compares the observed
digest with that profile field.

Normal verification is read-only:

```bash
python3 tools/verify_engine_v2_pme_reciprocal_reference_v1.py
```

Regeneration is explicit and is permitted only after all bound source and
fixture bytes are stable:

```bash
python3 tools/verify_engine_v2_pme_reciprocal_reference_v1.py --refresh
```

Refresh stages and fsyncs both evidence files, atomically replaces them, runs a
complete post-write verification, and restores both originals after any commit
or verification failure. Symlink/path checks and fault-injection unit tests
cover partial replacement, post-write failure, base exceptions, and temporary
cleanup.

## Frozen predecessors

The repository-local implementation prerequisite is reviewed PR #438:

- reviewed head `581a17a135d75ddf085c4edd29f3763c2f691fcf`;
- squash merge `e434295b1711f612e0f7e9fac2d95de92abf19a8`;
- exact tree `3546ef29ae708c16c7af1e3be4925d2d7ad1f6b5`;
- profile SHA-256
  `42aad2692719d3d0233d9b71e24e6b49fe50a27fbc150d31fb4d9688ae84215f`;
- 113-input manifest SHA-256
  `1a7a284467958e7c153edb0afd86cc5ea4ad07b659266ecf59d9da7549a19d15`.

The independent semantic oracle is reviewed PR #435:

- reviewed head `b94e4c008db1c8414f5d0f24fa266c85c828d13c`;
- squash merge `ba008fcaa75891bca45e7b3d33b67449d80fb7d4`;
- exact tree `0530a50af2cceeff02341ccb6fab141fd8c43726`;
- profile SHA-256
  `dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c`;
- scalar source SHA-256
  `2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e`;
- frozen fixture SHA-256
  `a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338`;
- standalone lock SHA-256
  `cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d`.

The verifier reads historical bytes directly from those merge objects,
requires both merges to be ancestors, checks reviewed/merged tree identity,
and requires the current direct-Ewald oracle inputs to remain byte-identical
to PR #435. The hosted workflow explicitly fetches the GitHub-managed,
read-only PR #435 and #438 pull refs and checks their exact reviewed-head
object IDs before running the verifier. A missing or moved pull ref therefore
fails CI closed instead of silently removing that tree comparison from a clean
checkout.

## Claim and execution boundary

All 15 authority fields are false. The controlling blockers remain
`external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false`; 32 operational decisions
remain unresolved.

This tiny scalar reciprocal development fixture grants no complete-PME,
bulk-solvent, equilibration, NPT, production-MD, accuracy-at-scale,
scientific, acceleration, performance, product, reservation, Stage 0,
Fresh-128, public-benchmark, molecular-execution, or HIP-device authority. It
does not invoke the consumed fixed64 CPU-v7 qualification and does not install
or launch the root supervisor.

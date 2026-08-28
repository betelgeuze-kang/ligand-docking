# Betelgeuze particle-mesh reciprocal reference

This standalone Rust workspace defines the deterministic scalar binary64
particle-mesh **reciprocal-space term** used by the next Engine V2 development
slice. Its schema is
`betelgeuze.reference_particle_mesh_reciprocal/1.0.0`. It is independent of
native compute and the production Rust workspace. `libm` is pinned exactly to
0.2.16; the direct-Ewald crate is a development dependency used only as a test
and observation oracle.

The supported input is a representationally exact-neutral set of point charges
in a fully periodic orthorhombic cell. Canonical units are angstrom, elementary
charge, kcal/mol, and kcal/(mol·angstrom). The only energy output is
`reciprocal_space_kcal_per_mol`; its Cartesian forces are the analytic negative
gradient of that same fixed-mesh energy.

## Frozen numerical definition

For axis `a`, reduce each coordinate to the primary cell, then define
`u_a = N_a r_a/L_a`, `i_a = floor(u_a)`, and `t_a = u_a-i_a`. Charge is
assigned to the four periodic nodes `i_a-1, i_a, i_a+1, i_a+2` with

```text
w(t) = [(1-t)^3,
        4 - 6t^2 + 3t^3,
        1 + 3t + 3t^2 - 3t^3,
        t^3] / 6

dw/dt = [-(1-t)^2/2,
         (3t^2-4t)/2,
         (-3t^2+2t+1)/2,
         t^2/2]
```

The deposited grid value is charge, not charge density:

```text
Q_g = sum_i q_i W_i(g)
```

Storage is z-fast. Separable transforms traverse z, then y, then x. The
forward DFT has a negative sign and no normalization. Each inverse axis applies
`1/N_a`, giving a net `1/M` with `M=Nx Ny Nz`. On an even axis, indices are
mapped to signed modes by `n(h)=h` for `h<N/2`, otherwise `n(h)=h-N`; the
Nyquist representative is therefore negative. Define

```text
k_a = 2 pi n_a/L_a
D_a = (2 + cos(2 pi n_a/N_a))/3
Qhat = FFT(Q)
```

With Coulomb conversion `K = 332.063713299`, dielectric `epsilon`, splitting
parameter `alpha`, and volume `V`, the frozen reciprocal energy is

```text
E = (K/epsilon) (2 pi/V)
    sum(h != 0) exp(-k^2/(4 alpha^2)) |Qhat_h|^2
                  / (k^2 (Dx Dy Dz)^2)
```

The zero mode is exactly omitted and there is no neutralizing-background
convention. The grid potential/energy derivative uses the required mesh-count
factor before the normalized inverse transform:

```text
phihat_h = M (K/epsilon) (4 pi/V)
           exp(-k^2/(4 alpha^2)) Qhat_h / (k^2 (Dx Dy Dz)^2)
phi = IFFT(phihat)
E = 1/2 sum_g Q_g Re(phi_g)
F_i,a = -q_i (N_a/L_a) sum_g (dW_i(g)/dt_a) Re(phi_g)
```

All transforms and grid traversals have fixed scalar orders. The production
evaluation uses an internal iterative radix-2 FFT. Tests compare it with a
separately implemented full triple-sum three-dimensional DFT, exercise
conjugate symmetry and round trips, and verify the half-grid-charge/potential
energy identity.

## Domain and validation

Every mesh dimension must be a power of two in `[4,128]`; the product is
bounded by 1,048,576 points. At most 4,096 particles are accepted. Coordinates
must be finite with absolute value at most `1e12` angstrom. Cell lengths are in
`[1e-6,1e9]` angstrom. Nonzero charge magnitudes are in `[1e-12,16]`
elementary charge. Alpha is in `[1e-12,1e6]` per angstrom and dielectric in
`[1e-12,1e12]`. Neutrality uses a canonical magnitude order and compensated
sum and must equal binary64 zero exactly. Validation occurs before mesh
allocation, and failures return stable typed error codes.

A checked 16,000,000-unit work cap is applied before assignment or grid
allocation. For `M=Nx Ny Nz`, its frozen equation is

```text
work = M (1 + log2(Nx) + log2(Ny) + log2(Nz))
       + particle_count * 4^3 * (1 + 3)
```

The two radix-2 transforms each require `(M/2) sum(log2(Na))` butterflies, so
together they contribute `M sum(log2(Na))`. The additional `M` counts the
influence traversal, and the last term counts the 64-point charge spread plus
three 64-point force gathers per particle. Every product and sum uses checked
integer arithmetic.

Normally represented damping and influence values retain their direct
arithmetic. If damping, influence, an energy term, or an influence-spectrum
component becomes subnormal or zero before later positive factors could rescue
it, pinned `libm` logarithm/exponential reconstruction produces that component
in an exact power-of-two scaled domain. The common scale is `S=2^256`.

Every influence-spectrum component, including normally represented modes, is
stored as `S Qhat exp(-k^2/(4 alpha^2))/(k^2 D^2)` before the single normalized
inverse transform. The analytic force gather applies the combined multiplier
`(-q_i N_a/L_a) (2 M (K/epsilon) (2 pi/V))/S` only after the derivative sum.
Thus normal and reconstructed modes share one spectrum, one inverse transform,
and one final force rounding. When no energy rescue is needed, energy retains
the direct `A sum(influence |Qhat|^2)` path, where
`A=(K/epsilon)(2 pi/V)`. When rescue is needed, reconstructed positive energy
components and `(A S)` times the regular reciprocal sum are compensated in the
same scaled domain and divided by `S` only once. This also prevents separate
regular and rescue lanes from each rounding below half a minimum subnormal.

The accepted mesh has at most `2^19` points and therefore fewer than `2^20`
real/imaginary positive energy contributions. Since `S=2^256`, a scaled term
that still rounds to zero cannot participate in a representable unscaled sum.
The envelope gives `|Qhat| <= 4096*16 = 2^16`, inverse wave-squared below
`2^55`, inverse squared spline modulus below `2^10`, and `A < 2^111`.
Consequently the scaled influence spectrum is below `2^337` (and below
`2^356` even under a deliberately conservative full-mesh intermediate-growth
allowance), while the complete scaled energy sum is below `2^484`; both are far
from binary64 overflow. Also `2 A M < 2^131` and
`|q| N_a/L_a < 2^31`, so the post-inverse force multiplier is below `2^-94`.
Even the derivative stencil's `L1` weight bound of `3/2` cannot revive a value
lost in the common scaled grid through that final multiplier. These bounds
close damping, energy aggregation, potential-spectrum, inverse-grid, and force
underflow gaps throughout the accepted input envelope.

The point-count ceiling alone bounds each complex mesh buffer to 16 MiB, but
the stricter work equation rejects every 1,048,576-point shape. The largest
accepted power-of-two mesh has 524,288 points (subject to particle work), so
the public evaluator holds one 8 MiB complex mesh buffer. Particle assignments
and the returned force vector remain separately bounded by the particle cap.
Unit-test diagnostics may retain one additional charge-grid copy; that copy is
compiled out of the public library.

Order-4 assignment and a finite mesh introduce mesh-phase aliasing. An
integer-periodic image and a simultaneous translation by whole mesh cells are
invariance properties. An arbitrary common translation can change the mesh
energy, and the total analytic force need not be exactly zero. Tests and the
observation example bound those residuals for the one synthetic fixture; they
do not claim continuous translation invariance or exact momentum conservation.

## Fixture and checks

`fixtures/pme_reciprocal_v1.tsv` freezes one reciprocal energy and 12 force
components as lowercase 16-digit IEEE-754 bit patterns for four synthetic
charges in an `[18,20,22]` angstrom cell with alpha `0.31`, dielectric `1`, and
a `16^3` mesh. Tests cover analytic-force finite differences, assignment
identities, grid-charge conservation, deterministic repeatability, periodic
images, mesh-cell translation, atom permutation, charge inversion, zero-mode
behavior, typed validation failures, and `8^3`, `16^3`, `32^3` observations
against the immutable direct-Ewald reciprocal energy at bound 9. Direct-Ewald
reciprocal forces are obtained only by finite-differencing that energy
component; its combined force is not used as a reciprocal oracle.
An anisotropic two-charge regression additionally proves that a raw zero
damping value is reconstructed into normal, nonzero energy and force and that
the rescued force matches the rescued energy's central finite difference. Its
scale-dual regression has energy and unscaled `phihat` below binary64 range but
a representable subnormal analytic force; the common `2^256` spectrum preserves
that force. The same physical family verifies that multiple individually
underflowing positive energy components round once to one minimum subnormal.
Focused aggregation tests cover both rescue-only and mixed regular/rescue
minimum-subnormal sums.

Run the crate-local checks and stable observation with:

```bash
cargo test --manifest-path rust/reference-pme/Cargo.toml --all-targets --locked
cargo run --manifest-path rust/reference-pme/Cargo.toml \
  --example profile_observation --locked
```

## Scope boundary

`full_pme_implemented=false`. This crate implements no real-space term, self
energy, excluded or scaled pair correction, total electrostatic energy,
virial, timing API, native ABI, runtime integration, molecular execution, HIP
execution, performance benchmark, or qualification. The synthetic fixture and
its fixed-mesh observations grant no scientific, acceleration, product, or
operational authority. The crate uses the repository license through
`license-file = "../../LICENSE"`; it intentionally has no duplicated or
symlinked local license file.

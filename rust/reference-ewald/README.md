# Betelgeuze direct-Ewald reference

This standalone crate is the independent scalar binary64 definition of the
first Engine V2 periodic direct-Ewald development slice. It is intentionally
outside the production Rust workspace and the consumed fixed64 CPU-v7 source
closure. It imports no native compute, accelerator, runtime, Python, or
external molecular-dynamics implementation.

The supported domain is a neutral, fully periodic orthorhombic cell. Canonical
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
order. Minimum images use `d - L*floor(d/L + 0.5)`.

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

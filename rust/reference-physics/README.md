# Betelgeuze reference physics

This crate is the independent, scalar `f64` energy oracle for Betelgeuze. It
does not import the native runtime, C++/HIP production evaluators, Python/Torch,
or any external solver. Production implementations are compared against these
equations; this crate is never dispatched as an external-engine adapter.

Canonical units are angstrom, radians, elementary charge, and kcal/mol. The
frozen component and accumulation order is bond, angle, torsion, Lennard-Jones,
then Coulomb. Nonbonded atom pairs are visited lexicographically as `i < j`.

The equations are:

```text
bond      = 0.5 k (r - r0)^2
angle     = 0.5 k (theta - theta0)^2
torsion   = A (1 + cos(n phi - phase))
sigma_ij  = 0.5 (sigma_i + sigma_j)
epsilon_ij= sqrt(epsilon_i epsilon_j)
LJ        = 4 epsilon_ij ((sigma_ij/r)^12 - (sigma_ij/r)^6)
Coulomb   = K q_i q_j exp(-kappa r) / (dielectric r)
```

For angles, the normalized dot product is clamped to
`[-1 + 1e-12, 1 - 1e-12]` before `acos`. For torsions,
`b0=ri-rj`, `b1=rk-rj`, `b2=rl-rk`, the central axis is `b1/|b1|`,
and the projected vectors `v,w` define
`phi=atan2(dot(cross(axis,v),w), dot(v,w))`.

Both nonbonded components use the same quintic switch between switch start and
cutoff: `1 - 10x^3 + 15x^4 - 6x^5`. Exclusions are explicit unordered
pairs and suppress both nonbonded components; topology never implies an
exclusion. An excluded pair is omitted before the minimum-distance singularity
check, while its bonded terms remain.

Orthorhombic PBC uses the half-open minimum-image interval `[-L/2, L/2)`:

```text
d_min = d - L * floor(d / L + 0.5)
```

The cutoff must be strictly smaller than half of every periodic box length.
Fixtures under `fixtures/` freeze expected IEEE-754 binary64 results.

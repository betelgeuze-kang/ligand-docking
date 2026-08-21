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

These are tiny-fixture development observations. They are not equilibrium NVT
statistics, stability validation, throughput measurements, or acceleration
evidence.

## Remaining boundaries

The slice has no SHAKE/RATTLE water constraint validation, neighbor-list
performance evidence, ions, PME/Ewald, NPT/barostat, peptide or protein system,
public benchmark, production-MD, free-energy, scientific-claim, product,
Stage 0, Fresh-128, reservation, or performance-claim authority. Those remain
separate reviewed dependencies.

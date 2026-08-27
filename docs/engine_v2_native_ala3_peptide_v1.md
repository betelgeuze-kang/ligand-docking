# Engine V2 native Ala3 CPU development slice v1

This slice extends the native CPU molecular fixture from water and ions to one
33-atom tri-alanine system. It exercises a real peptide topology with Amber
ff14SB bond, angle, proper/improper periodic-torsion, exclusion, Lennard-Jones,
Coulomb, and scaled 1–4 terms. It is bounded engineering evidence, not general
peptide parameter assignment or production/scientific molecular-dynamics
validation.

## Frozen identity and derivation

The canonical profile is
`config/engine_v2_native_ala3_peptide_profile_v1.json`, SHA-256
`a7a4229cc30bb24393b06d4b19e25b917060213ca432b1263329bda6c0b49adf`.
The Rust runtime embeds an exact copy and freezes the same digest.

The offline generator requires exact source artifacts rather than accepting an
arbitrary peptide:

- `nglview-3.1.2/datafiles/ala3.pdb`, SHA-256
  `5510388d045a8f8938236f0975e4f52b81e1b8b7bf9d0c5effcf856050d6123d`;
- OpenMM `amber14/protein.ff14SB.xml`, SHA-256
  `d9f9779c09d67cd5f8bc657692f174ffab14c469dfd06d560ac1899fa7e976b8`;
- ff14SB reference [DOI 10.1021/acs.jctc.5b00255](https://doi.org/10.1021/acs.jctc.5b00255).

Before projecting either source, generation also requires the repository-pinned
OpenMM distribution `8.4.0.post2` and runtime identity
`8.4.0.dev-4768436`; any other installed version fails closed rather than
rewriting the frozen reference constants.

`benchmarks/oracles/openmm/generate_native_ala3_profile_v1.py` projects the
resulting OpenMM System inside the repository's external-oracle boundary into
the existing native force-field representation and emits
`development_peptide_data.rs`. The generated data SHA-256 is
`7a75f9ccd2d0cee99387ec2ae25c47b145a1a325bf0498b1752340c3a04b88a0`
and is bound inside the profile. Runtime use has no OpenMM or nglview
dependency. The profile records the source-distribution license statements but
does not claim that an external legal-compliance determination has occurred.

## Native and independent-reference checks

The frozen projection contains 33 atoms, 32 bonds, 57 angles, 72 periodic
torsion terms, 89 exclusions, and 74 scaled 1–4 pairs. Its net charge is zero
within floating-point projection precision. A 20 Å nonperiodic native cutoff
and 15 Å switch start exceed every fixture pair distance, so the native switch
is exactly one and matches OpenMM `NoCutoff` for this fixed geometry.

The checked-in OpenMM Reference-platform energy and 99 force components are
independent expected values. Focused Rust tests require both admitted native
CPU implementations to:

1. match those expected values within 2e-5 kcal/mol energy and 5e-5
   kcal/mol/Å component-wise force tolerance;
2. match each other bit-for-bit for energy and force;
3. remain bit-for-bit identical after 32 zero-velocity Velocity Verlet steps;
4. reproduce the same state and report after an exact checkpoint split at step
   13 and continuation for 19 steps.

Only `CppCpuReference` and `RustCpu` contexts are admitted. This slice performs
no HIP-device execution and records no timing or performance threshold.

## Authority boundary

The profile explicitly leaves general peptide parameter assignment,
production MD validation, scientific claims, molecular-execution authority,
performance claims, HIP-device authority, and product authority false. It does
not change the external reservation blockers, the 32 unresolved operational
decisions, or any Stage 0/Fresh-128/public-benchmark gate.

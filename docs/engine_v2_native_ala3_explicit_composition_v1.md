# Engine V2 native Ala3 explicit-composition development slice v1

This bounded fixture composes the existing native Ala3, TIP3P water, Na/Cl,
periodic-neighbor, and SHAKE/RATTLE paths in one canonical molecular state. It
is a structural prerequisite for later explicit-solvent work, not a solvated
ensemble, bulk-solvent validation, or scientific molecular-dynamics result.

## Frozen identity and composition

The canonical profile is
`config/engine_v2_native_ala3_explicit_composition_profile_v1.json`, SHA-256
`a9fad385e3eaf84c673507ee513778ad05842da139c282ce9def1c712eb13079`.
The Rust runtime embeds an exact copy and binds these parent profiles:

- native Ala3 ff14SB fixture `a7a4229c...b49adf`;
- Ala3 X-H constraints `815c9ab4...cb692`;
- native TIP3P water box `2b0be83b...0019e`;
- native water/ion parameters `409902e5...c631f`;
- periodic neighbor cache v2 `c9e671b9...150d`.

The fixed 41-atom ordering is 33 Ala3 atoms, two three-site TIP3P waters, one
sodium ion, and one chloride ion. The projected net charge is zero. All
components share one `System`, `ForceField`, and `Simulation`; the water
geometry and force-field rows are reused from the existing water fixture rather
than copied into a second parameter source.

The profile also freezes placement: Ala3 is translated by `[8, 15, 15]` Å,
the two-water fixture by `[25, 5, 10]` Å, and Na/Cl are placed at
`[32, 10, 25]` Å and `[34.5, 10, 25]` Å. Every initial position is inside the
primary cell.

The orthorhombic cell is 40 Å per axis with all axes periodic. Native
short-range nonbonded evaluation uses a 12 Å cutoff and 10 Å switch start.
PME/Ewald, general solvation, parameter assignment, salt-concentration
construction, and equilibration are not implemented by this slice.

## Constraint, checkpoint, and CPU evidence

The state has 23 mass-weighted constraints: the exact 17 Ala3 X-H rows plus
the two O-H and one H-H rows for each rigid water. Position and radial-velocity
tolerances are both `1e-10` in Å and Å/fs, respectively.

`observe_development_ala3_explicit_composition_v1` evaluates static energy and
all forces, then runs 128 zero-velocity Velocity Verlet steps at 0.02 fs. A
step-53 checkpoint must preserve the loaded state bit-for-bit and both the
continued and uninterrupted terminal states and reports must agree exactly.
The committed optimized observation is:

- static total energy: `-104.92872401231725` kcal/mol;
- post-projection initial total energy: `-107.5118169601866` kcal/mol;
- step-128 total energy: `-107.51188810925693` kcal/mol;
- signed post-projection drift: `-7.11490703366735e-5` kcal/mol;
- maximum position residual: `9.00888252886034e-11` Å;
- maximum radial-velocity residual: `8.599890623379582e-11` Å/fs;
- degrees of freedom: 100.

The C++ reference and Rust CPU backends produce bitwise-identical static
evaluation digests, complete terminal-state digests, reports, and
backend-independent observation receipts. Tests freeze those values and
independently rebuild both the observation receipt and each backend-tagged
receipt byte stream.

## Authority boundary

This is a deterministic development fixture only. Explicit-solvent
validation, bulk-solvent or equilibration validation, PME/Ewald validation,
production MD, scientific claims, molecular-execution authority, performance
claims, HIP-device execution, product authority, reservation, Stage 0,
Fresh-128, and public-benchmark authority all remain false. The external
reservation blockers and unresolved operational decisions are unchanged.

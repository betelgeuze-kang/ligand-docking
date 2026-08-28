# Engine V2 stateless short-range + particle-mesh Ewald CPU composite v1

## Scope

Issue #434 adds a separately versioned, stateless development ABI that
combines the frozen short-range evaluator with the frozen particle-mesh Ewald
parent. One synchronous call borrows an existing context, system, force field,
direct-Ewald model, and particle-mesh reciprocal model. It creates no owner,
retains no caller storage, and changes neither Engine ABI 1.21 nor either
electrostatic parent ABI.

The public profile is
`betelgeuze.native_particle_mesh_ewald_composite/1.0.0`. Its eight public
symbols live in ELF version node
`BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_1.0`, with
`BETELGEUZE_PARTICLE_MESH_EWALD_1.0` as the parent. The 64-bit energy and force
descriptors are respectively 144 and 88 bytes.

## Frozen composition

The 12 energy components are ordered as follows:

1. short-range bond, angle, torsion, Lennard-Jones, Coulomb, and short total;
2. PME real, reciprocal, self, pair correction, and PME total; and
3. grand total, evaluated as short total plus PME total.

The short-range parent receives a private system copy whose charges are all
the exact positive-zero bit pattern. The caller's original exact-neutral
charges are passed to particle-mesh Ewald. Consequently the short Coulomb
component is exact `+0.0` and electrostatics appear only in the PME fields.
The caller's system is never mutated.

The PME parent evaluates direct-local real, self, and pair-correction terms
plus the order-4 mesh reciprocal term. Direct reciprocal bounds remain
irrelevant. The total force is the short-range force plus the PME force in the
same fixed parent order. Energy-only calls request no force output from either
parent.

Compatibility requires identical atom counts and units, a fully periodic
orthorhombic force field, bit-identical force-field/direct-model cell lengths,
exact force-field/direct-model pair-rule provenance, and bit-identical cell,
alpha, and dielectric values across the two Ewald models. Every borrowed
object, descriptor, semantic input span, and writable output span must be
mutually disjoint where required by the ABI.

Both parents finish into local candidates before the caller's energy, force
channels, or force count is committed. Direct-Ewald typed failures are
preserved. Reciprocal failures with an equivalent scientific meaning map to
the corresponding `bg_direct_ewald_error_v1` code; compatibility and ABI
failures remain untyped native failures.

## Deterministic CPU validation

The development fixture has four atoms at positions
`[(1.25,2.5,3.75), (3.1,3.2,4.4), (5.2,5.3,4.7), (7.4,6.1,6.3)]`, charges
`[0.7,-0.4,-0.6,0.30000000000000004]`, cell `[18,20,22]`, Ewald alpha `0.31`,
and a `16^3` reciprocal mesh. Its bonded, Lennard-Jones, exclusion, and scaled
pair inputs match the frozen direct-composite fixture. The Rust CPU composite
total is frozen at binary64 bits `4012dc3129bce12e` (approximately
`4.715031292107865` kcal/mol).

The native and Rust evidence checks:

- exact equality with separate positive-zero short-range and charged PME
  parent components and forces;
- same-lane bitwise repeatability and energy-only bit identity on both CPU
  lanes;
- C++/Rust agreement under the fixed mixed absolute-plus-relative tolerance
  with both tolerances `5e-12`;
- analytic total force against central energy differences on all 12 Cartesian
  fixture axes;
- direct-bound independence and mesh 8/16/32 approach toward the corresponding
  direct-composite total;
- translation, periodic-image, atom-permutation, and charge-inversion
  invariance;
- pair-rule provenance, compatibility rejection, alias rejection, required
  nulls, stale typed errors, failure transactionality, and recovery; and
- C11 and C++ layouts, raw and safe Rust boundaries, exact ELF versioning, and
  the Mach-O export allowlist.

`BG_BACKEND_CPP_CPU_REFERENCE` and `BG_BACKEND_RUST_CPU` are the only accepted
lanes. The requested and resolved lanes must match exactly. `AUTO`, `HIP_SAFE`,
and `HIP_FAST` fail before scientific inputs are inspected, never call a
device, and never fall back to CPU.

## Immutable evidence

The generated evidence is:

- `config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1.json`;
- `config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1_sources.json`.

The canonical ASCII manifest binds the owned ABI, implementation, tests,
build/export policy, Rust packaging/runtime boundary, documentation, verifier,
workflow, predecessor freeze consumers, and their shared parent inputs. The
generated profile and manifest exclude themselves to keep the hash closure
acyclic.

Normal verification is read-only:

```bash
python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py
```

Only an intentional source change may refresh both generated files:

```bash
python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py --refresh
```

The verifier reads both predecessor profiles and manifests from exact frozen
Git objects:

- direct composite PR #437: reviewed head
  `454bb9ee6cdb4202cecbc807f78503ce842bdd13`, squash merge
  `f2731176fb913f600349ec6a1fbf3678d399a7c1`, tree
  `6017cf05e3f437443371966775bb4deb3fc73cab`;
- particle-mesh Ewald PR #441: reviewed head
  `59ad72fe57e82106a71df2c88c63c9fe12d014ad`, squash merge
  `e228f376857ead900bd1ae99cf5b111c8b40cf34`, tree
  `ae0a6eddd44262eeec633c57a0f5566bf7989361`.

The older PME workflow executes its evidence from the exact PR #441 merge
object rather than refreshing it in this descendant.

## Authority boundary

Every authority field is false. The four external reservation and historical
execution blockers and all 32 unresolved operational decisions remain
controlling. This tiny deterministic CPU fixture authorizes no reservation,
molecular A/B, D1/D2, Stage 0, Fresh-128, public benchmark, molecular
execution, qualification rerun, scientific, acceleration, performance,
product, or HIP-device claim or action. It does not install or launch the root
supervisor and does not rerun the consumed native fixed64 CPU-v7
qualification.

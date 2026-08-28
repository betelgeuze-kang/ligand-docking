# Engine V2 native short-range + direct-Ewald composite ABI v1

Issue #434 step 3 adds a separately versioned, stateless development ABI that
combines the frozen short-range evaluator with the direct-Ewald v1 model. It
does not change Engine ABI 1.21 or direct-Ewald ABI 1.0 and creates no new
owner: one call borrows an existing context, system, force field, and immutable
direct-Ewald model.

The public header is `include/betelgeuze/direct_ewald_composite.h`. Composite
ABI 1.0 exports a 144-byte energy descriptor and an 88-byte caller-owned force
SoA descriptor on the supported 64-bit targets. The frozen energy order is:

1. short bond, angle, torsion, Lennard-Jones, Coulomb, and short total;
2. Ewald real, reciprocal, self, pair correction, and Ewald total;
3. grand total, evaluated as short total plus Ewald total.

The evaluator copies the caller system for the short-range parent and replaces
every copied charge with the exact positive-zero bit pattern. The original
charged system is passed to direct Ewald. Therefore the short Coulomb component
must be exact `+0.0`, while direct Ewald supplies the sole electrostatic term.
The caller's system is never mutated; force channels that overlap any borrowed
System SoA channel are rejected before evaluation.

Compatibility checks require identical atom counts and units, a fully periodic
orthorhombic force field, bit-identical force-field/model cell lengths, and an
exact projection of exclusions and scaled Coulomb pairs. Direct-Ewald model
rows retain whether a zero scale originated as an exclusion; an explicit
zero-scaled pair is not interchangeable with an exclusion.

Both parent evaluations finish into local candidates before any caller energy,
force channel, or force count is committed. A short-range failure leaves the
direct-Ewald typed error clear. A late direct-Ewald typed failure is preserved,
while every other output remains unchanged. Energy-only evaluation passes no
force request to either parent and performs no force allocation or
accumulation.

The C++ CPU reference and Rust CPU lanes are development implementations. HIP
contexts fail closed before either evaluator runs and never fall back to CPU.
This boundary is not shared-runtime dynamics, a checkpoint format, PME, or an
operational molecular execution interface.

## Deterministic validation

The executable synthetic fixture has four atoms with charges
`[0.7, -0.4, -0.6, 0.30000000000000004]`, cell lengths `[18, 20, 22]`, Ewald
alpha `0.31`, cutoff `8.9`, reciprocal limits `[5, 5, 5]`, exclusion `0-1`,
and Coulomb scale `0.5` for pair `2-3`. Small bonded and Lennard-Jones terms
exercise both parents. A separate matching explicit-zero Coulomb scale keeps a
nonzero LJ scale and proves that zero-scale provenance remains distinct from an
exclusion. Tests compare the composite with separate
zero-charge-short-range and charged-direct-Ewald calls, preserve frozen
summation order, check same-lane repeatability and energy-only bit identity,
compare CPU lanes within the bounded tolerance, check central finite
differences for all 12 Cartesian force components, and cover mismatch, alias,
failure, and recovery paths.

The existing 41-atom Ala3 input has compensated charge `-2^-54`; it remains a
non-neutral rejection/deferral fact and is not a composite execution fixture.

Raw Rust bindings compile C11 header and C++ layout probes. Native and Rust
tests cover descriptor initialization, size/offsets, output transactionality,
typed-error behavior, and exact ELF/Mach-O public export boundaries. Canonical
and vendored headers and native dependencies must remain byte-identical.

## Immutable evidence

The generated profile and source manifest are:

- `config/engine_v2_native_direct_ewald_composite_profile_v1.json`
- `config/engine_v2_native_direct_ewald_composite_profile_v1_sources.json`

The manifest is canonical ASCII JSON with sorted unique path, byte-count, and
SHA-256 rows. It binds the composite-owned sources and the shared short-range,
direct-Ewald, export, Rust ABI/runtime, and vendor inputs used by this slice.
It includes its verifier. To keep the binding acyclic it excludes the generated
profile and manifest, the profile consumer unit test, this document, and the
workflow.

Normal verification is read-only:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_composite_v1.py
```

Only after an intentional source change is complete may the two generated
files be rewritten explicitly:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_composite_v1.py --refresh
```

The verifier reads predecessor evidence from the frozen Git objects rather
than from the refreshed current direct-Ewald profile:

- PR #436 reviewed head `60a0047af27acacbce3feed7ee1dcedd8a690176`
- squash merge `074d3b71373088c0738de7a14797fe35d66d986e`
- review-reported and merged tree `e2763a42f4605d7435514c49f18259ea44f4dd3c`
- historical direct profile SHA-256
  `5d0a09742e8388938e90988a6a23fd945d5e2613d0fa37e9f2c8c9dd86d89de8`
- historical 55-input manifest SHA-256
  `4f2acac517f56ade77b8712bfd24b4312f208f2a5902862f73a807e2a3f7e3ab`

It requires the merge to be an ancestor of the checked-out revision and reads
both historical blobs directly from the merge commit. The verifier treats the
reviewed-head hash and review-reported tree as frozen review metadata and
cryptographically verifies the reachable squash merge, its exact tree, and its
historical profile/manifest blobs. This avoids depending on a transient PR-head
Git object in a fresh CI clone. This permits the current direct-Ewald evidence
to refresh for shared provenance storage without weakening the exact
predecessor binding.

## Claim and execution boundary

All authority fields are false. The four external reservation/historical
execution blockers and 32 unresolved operational decisions remain controlling.
This repository-local deterministic CPU fixture grants no reservation,
molecular A/B, D1/D2, Stage 0, Fresh-128, public benchmark, molecular execution,
scientific, acceleration, performance, product, or HIP-device authority. It
does not invoke or rerun the consumed native fixed64 CPU-v7 qualification and
does not install or launch the root supervisor.

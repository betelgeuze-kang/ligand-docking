# Engine V2 stateless particle-mesh Ewald CPU v1

## Scope

This development slice composes the frozen direct-Ewald local terms with the
frozen order-4 particle-mesh reciprocal term. It exposes a separately
versioned, stateless native CPU ABI and a safe Rust wrapper. It does not change
Engine ABI 1.21 or either parent ABI.

The boundary borrows an existing `bg_direct_ewald_model_v1` and an existing
`bg_particle_mesh_reciprocal_model_v1` for one synchronous call. It creates no
new model owner and retains no caller storage.

## Frozen electrostatic composition

The output order is:

1. direct-Ewald real-space energy;
2. particle-mesh reciprocal energy;
3. direct-Ewald self energy;
4. direct-Ewald excluded/scaled-pair correction;
5. the binary64 sum in exactly that order.

Forces are the direct local real/pair force plus the particle-mesh reciprocal
force. The self term has no Cartesian force. The direct model is evaluated
through an internal all-zero reciprocal-bound sentinel, so its configured
direct reciprocal bounds cannot affect this ABI. Public direct-Ewald model
creation continues to require positive reciprocal bounds; the sentinel is not
constructible through that public boundary.

The two borrowed models must have exactly matching atom counts, units, cell
length bits, alpha bits, and dielectric bits. The direct model remains the
authority for real-space cutoff, minimum supported pair distance, exclusions,
and explicitly scaled Coulomb pairs. The reciprocal model remains the authority
for mesh dimensions and the order-4 reciprocal calculation.

For the frozen four-charge synthetic fixture, the Rust CPU composed total has
binary64 bits `c0186145396def20` (approximately
`-6.09499063237652194` kcal/mol). The C++ CPU result agrees under the frozen
mixed absolute-plus-relative tolerance.

## CPU lanes and failure behavior

`BG_BACKEND_CPP_CPU_REFERENCE` composes the independent native C++ parent
evaluators. `BG_BACKEND_RUST_CPU` composes the independent Rust parent
evaluators. Both lanes use the same public descriptors and frozen component
order. An explicit CPU request must resolve to that same CPU lane; a mismatched
context fails before any scientific or output argument is accessed.

`AUTO`, `HIP_SAFE`, and `HIP_FAST` requests fail before scientific inputs are
accessed. There is no CPU fallback and no device call. Parent validation,
allocation, and numerical failures preserve stable status and typed error
classification. The outer call validates all borrowed and writable ranges
before evaluation and commits energy, force channels, and force count only
after both parents and the final sum succeed.

The new ABI reuses `bg_direct_ewald_error_v1`. Particle-mesh failures that have
the same scientific meaning map to the corresponding direct-Ewald code;
particle-mesh parameter/mesh failures map to the direct invalid-parameter code.
Compatibility and ABI failures remain untyped native failures.

## Validation evidence

The native and Rust tests cover:

- the exact 8-symbol ABI, C11 header, C++ layouts, ELF version node, and Mach-O
  export allowlist;
- bit-stable repeated evaluation and energy-only identity on both CPU lanes;
- component agreement with frozen parent observations and the frozen Rust CPU
  composed total;
- C++/Rust mixed absolute-plus-relative parity;
- analytic total force against central energy differences on all 12 Cartesian
  fixture axes;
- direct reciprocal-bound independence;
- mesh 8, 16, and 32 observations approaching the frozen direct-Ewald total;
- periodic images, atom permutation, charge inversion, exclusions, and scaled
  pair provenance;
- exact model compatibility rejection;
- output alias, undersized and unaddressable buffers, required-null,
  stale-error, and failure transactionality;
- explicit failure of AUTO and HIP without device execution; and
- raw/sys packaging plus safe Rust ownership and recovery behavior.

The evidence profile and source manifest exclude themselves from the source
hash closure to avoid a hash cycle. The workflow, documentation, verifier, and
unit tests are included in that closure. Earlier reciprocal-only evidence is
executed from the exact PR #440 merge object rather than being refreshed from
this descendant.

## Frozen parents

- Direct scalar reference: PR #435, merge
  `ba008fcaa75891bca45e7b3d33b67449d80fb7d4`, tree
  `0530a50af2cceeff02341ccb6fab141fd8c43726`.
- Native direct-Ewald CPU: PR #436, merge
  `074d3b71373088c0738de7a14797fe35d66d986e`, tree
  `e2763a42f4605d7435514c49f18259ea44f4dd3c`.
- Reciprocal scalar reference: PR #439, merge
  `ebbd7a20538cfd7516d9b53adb2e54c6de14bd97`, tree
  `2ae92801369c7e16147e07cbb16e19c062e52cc9`.
- Native reciprocal CPU: PR #440, merge
  `735883551510cbef91adc3e57dc131a1234b67fb`, tree
  `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.

Every parent profile, manifest, source, FFT, fixture, and lock digest used by
this slice is checked from its historical Git object. Current descendant bytes
cannot silently redefine a parent.

## Explicit exclusions and authority boundary

This is tiny-fixture deterministic development evidence. It does not add
short-range molecular composition, stateful dynamics, checkpointing, virial,
bulk-solvent accuracy, optimization, performance evidence, HIP implementation,
or product/scientific authority.

All authority fields remain false. The controlling blockers remain:

- `external_reservation_provider_not_operational`;
- `external_reservation_endpoint_not_configured`;
- `external_reservation_trust_anchor_not_configured`; and
- `historical_execution_operational_authority_false`.

The 32 unresolved operational decisions remain unresolved. This slice does not
run the consumed native fixed64 CPU-v7 qualification, install or operate a root
supervisor, reserve external capacity, execute molecular A/B, D1/D2, Stage 0,
Fresh-128, a public benchmark, operational molecular work, or a HIP device. It
makes no acceleration, performance, scientific, or product claim.

# Engine V2 native PME Rust reciprocal provider force-source SoA v1

This bounded CPU-only slice lets the force-producing stateful Rust
particle-mesh Ewald composite consume its private reciprocal-provider x, y,
and z scratch directly as the reciprocal force source. The Rust route no
longer populates the reciprocal parent's AoS `Evaluation::forces` storage for
this call shape. Empty reciprocal-parent storage stays empty, and deliberately
seeded stale storage keeps the same allocation, size, and force bits.

The dispatch is exact: only a Rust-lane, stateful, force-producing evaluation
uses the private `evaluate_reusing_provider_force_storage` adapter. The C++
lane continues to reuse reciprocal-parent AoS storage. Stateless and
force-free Rust evaluations continue through the prior evaluator routes. The
existing transactional provider entry point and the hidden direct-provider
force-output entry point are unchanged.

The internal adapter returns only reciprocal energy metadata while retaining
provider force values in owner-private SoA scratch. It scans all three force
channels for finite values before exposing that result to the composite. The
composite uses a local reciprocal-force view, validates every parent,
intermediate, and combined force in a complete first pass, and only then
writes final stateful force SoA in a second pass. This preserves the established
preflight/commit boundary without making universal failure-retention or
allocation-free claims.

Checkpoint bytes, the static fingerprint, public profile identity, and the
13-symbol public ABI remain unchanged. `ProviderForceSourceResult` and
`evaluate_reusing_provider_force_storage` are private native adapter details
and are absent from public headers, exports, and Rust public FFI surfaces.

The native regression covers an initially empty reciprocal parent, a C++-seeded
stale reciprocal parent, checkpoint load/restart, zero-step evaluation,
forceful resynchronization, stateless reciprocal-force bit comparison, and
step/view alias rejection. It verifies the provider SoA is refreshed while the
Rust-lane reciprocal-parent AoS allocation and bits remain untouched. The
inherited direct-provider inverse-FFT second-occurrence failure sentinels and
late scientific-failure transaction boundary remain exact.

## Frozen evidence graph

- Target predecessor: PR #457, reviewed 83ff887e4b9d5e4598023617ca2ed9a4bc87d031, merged f20d7a1480a06c29cee5411d84d1d39305f6b461, tree 1db6841f4884cf0c2774212878b316f5a19d430d.
- Architecture predecessor: PR #453, reviewed 68607f1b4c1311755b565a2ace2e681695d7f764, merged 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a, tree b22c5fd115a5c8e28856872df57127ecdd28d9b5.
- Inherited reciprocal evaluator: PR #440, reviewed 098bce0d726dbed6e4bf7b533e0445f81e244ea2, merged 735883551510cbef91adc3e57dc131a1234b67fb, tree 6c2b6f3960b6df0592b78bb44e429389aa58bcbb.
- Direct-output precedent: PR #380, reviewed c486e767b1452cffb9cfd998bc26d5e4403bbd76, merged 6662f1b53829930a93de0f298b820d5a367cc3dc, tree 5a2d296e891fe89f3d48c3c6d7b1deb61e81a177.

The verifier pins four changed canonical/vendor pairs, eight production paths,
one native regression, six new evidence files, and the two frozen predecessor
wiring edits: 17 delta paths in total. It fixes 96 workflow triggers, four job
bodies, the 278-row canonical source manifest, production/test hashes, exact
public symbols, checkpoint/fingerprint sources, dispatch and two-pass ordering,
and all authority guards. The predecessor workflow fetches the reviewed PR
head and detaches to the exact merged PR #457 object before executing its
frozen verifier and unit test. Its checked-out unit skips only when this
successor profile is present.

The CPU-only workflow inherits focused standalone reciprocal and composite
Release and ASan/UBSan regressions, Rust reciprocal/composite library,
integration, documentation, format, clippy, clean-package, and macOS export
boundaries. Every CMake configuration disables both HIP modes. The inherited
exact-signature macOS locked-Cargo retry remains unchanged and fail-closed.

## Boundary

This is not an allocation-free, universal reciprocal-parent allocation-elision,
universal failure-retention, checkpoint-buffer-aliasing, timing, performance,
acceleration, cross-lane parity, molecular, scientific, HIP-device,
qualification, reservation, or product claim. All operational authorities
remain false; the four external/historical blockers and 32 unresolved
operational decisions remain unchanged.

# Engine V2 native PME Rust reciprocal provider direct force-SoA v1

This bounded CPU-only slice lets the hidden Rust particle-mesh reciprocal
provider write force results directly into the owner-private x, y, and z
scratch established by the target predecessor. The C++ adapter selects the
new route only when force storage reuse and force computation are both
requested. The existing transactional provider entry point remains the path
for public stateless evaluation, force-free evaluation, and every caller that
does not supply reusable storage.

The direct route retains the predecessor's exact reciprocal arithmetic order
while removing its private force-output Vec reservation, gather-to-vector,
and three force-channel copies. It still allocates and owns provider input
copies, neutrality-sort storage, particle assignments, the spectrum,
forward/inverse FFT line scratch, and reciprocal-axis data. Descriptor,
capacity, alias, input-copy, and all such fallible allocation work completes
before the first direct force write. Energy is committed only after success.
A later non-finite-result failure or panic may modify the disposable force
channels, so this slice does not claim universal failure retention or an
allocation-free reciprocal evaluator.

The PR #456 provider-force scratch, reciprocal-parent and final force reuse,
checkpoint bytes, static fingerprint, public profile, and 13-symbol public ABI
remain unchanged. The new provider symbol is internal to the native/Rust
adapter boundary and absent from every public header and export surface.

Tests compare the direct and transactional provider energy and force bits,
including untouched tail capacity. Allocation injection proves the old
force-output allocation fails while the direct route bypasses it, and proves
sentinel retention for all seven remaining allocation sites. Both forward and
inverse FFT line-scratch occurrences are covered explicitly. Capacity,
pairwise force-channel aliasing, and input/output aliasing are rejected before
force writes.

## Frozen evidence graph

- Target predecessor: PR #456, reviewed 8aed1d83a15e23385279c589096a79563a56cd67, merged 51fe906656071e64c5557bcf83014b88aefac136, tree 2cb175d8c17e090d8494469988e7af2a3841b695.
- Architecture predecessor: PR #453, reviewed 68607f1b4c1311755b565a2ace2e681695d7f764, merged 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a, tree b22c5fd115a5c8e28856872df57127ecdd28d9b5.
- Inherited reciprocal evaluator: PR #440, reviewed 098bce0d726dbed6e4bf7b533e0445f81e244ea2, merged 735883551510cbef91adc3e57dc131a1234b67fb, tree 6c2b6f3960b6df0592b78bb44e429389aa58bcbb.
- Direct-output precedent: PR #380, reviewed c486e767b1452cffb9cfd998bc26d5e4403bbd76, merged 6662f1b53829930a93de0f298b820d5a367cc3dc, tree 5a2d296e891fe89f3d48c3c6d7b1deb61e81a177.

The verifier pins the five implementation paths, six predecessor
canonical/vendor mirror pairs plus the changed provider-header pair, the exact
13-path successor delta, 90 static workflow triggers, four immutable job
bodies, and the canonical source manifest. It also freezes checkpoint and
static-fingerprint sources, the hidden-only symbol boundary, the
reuse-and-forces dispatch predicate, direct-output ordering, failure
boundaries, and exact public symbols. The predecessor workflow detaches to the
exact merged PR #456 object before running its frozen evidence.

The CPU-only workflow runs standalone reciprocal and composite-dynamics
Release and ASan/UBSan tests, focused betelgeuze-cpu-kernel reciprocal tests
and clippy, Rust reciprocal/composite library, integration, and documentation
tests, and existing package, format, lint, and export boundaries. The inherited
exact-signature macOS locked-Cargo retry remains unchanged and fail-closed.

## Boundary

This is not an allocation-free, universal failure-retention,
checkpoint-buffer-aliasing, timing, performance, acceleration, cross-lane
parity, molecular, scientific, HIP-device, qualification, or product claim.
Reservation and every operational authority remain false; the four existing
external/historical blockers and 32 unresolved operational decisions remain
unchanged.

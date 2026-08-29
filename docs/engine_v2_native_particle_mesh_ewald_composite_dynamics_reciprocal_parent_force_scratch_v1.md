# Engine V2 native PME reciprocal-parent force scratch v1

This bounded CPU-only slice reuses the particle-mesh Ewald composite's
reciprocal-parent final AoS force storage during successful stateful forceful
integration. Both explicit CPU lanes call internal reciprocal evaluator reuse
entry points. The C++ evaluator gathers into a caller-supplied AoS vector; the
Rust evaluator reuses only its final AoS vector while the provider-facing
force-x, force-y, and force-z vectors remain local to each call.

The stateful force-free and public stateless paths retain ordinary evaluation.
The reciprocal evaluator's internal mesh and SoA work storage are not reused.
The existing short-parent, direct-parent, and final combined-force storage
reuse remains intact. The BGPME001 checkpoint format, static fingerprint, and
13-symbol public ABI remain unchanged.

Tests cover empty creation, reserved zero-step stability, repeated forceful
pointer/capacity retention, same-lane peer and public stateless reciprocal
force-bit identity, checkpoint-load stale scratch retention, zero-step stale
retention, exact forceful resynchronization, and interior owner aliases for
absolute-step and particle-view outputs. Owner overlap is rejected before
particle-view descriptor validation or dereference.

## Frozen evidence graph

- Target predecessor: PR #454, reviewed `f4ab121fc91f3a195df938a9894433b78316408a`, merged `c51112868f1c7e91af7510eb5652407dab46e0df`, tree `288d00bb91b0e5ea11cc093a42d1041ce8bdc648`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.

The verifier pins all 19 production/test implementation paths, eight
canonical/vendor source pairs, the exact 27-path successor delta, 76 static
workflow triggers, four immutable job bodies, and a 260-row source manifest.
The CPU-only workflow runs standalone reciprocal and composite dynamics
Release and ASan/UBSan tests, Rust reciprocal and composite library,
integration, and documentation tests, and existing package/format/lint
boundaries. The inherited exact-signature macOS locked-Cargo retry remains
unchanged and fail-closed.

## Boundary

This is not an allocation-free, failure-retention, checkpoint-buffer-aliasing,
timing, performance, acceleration, cross-lane parity, molecular, scientific,
HIP-device, qualification, or product claim. Reservation and every operational
authority remain false; the four existing external/historical blockers and 32
unresolved operational decisions remain unchanged.

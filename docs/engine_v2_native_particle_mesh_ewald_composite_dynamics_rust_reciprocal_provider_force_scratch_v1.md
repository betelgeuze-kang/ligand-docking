# Engine V2 native PME Rust reciprocal provider-force scratch v1

This bounded CPU-only slice gives each particle-mesh Ewald composite dynamics
owner private force-x, force-y, and force-z storage for the Rust reciprocal
provider. Successful stateful force-producing Rust-lane integration reuses
those three vectors while preserving the reciprocal-parent final AoS storage
reuse added by the target predecessor. The C++ lane does not use or rewrite
the Rust provider scratch, including when that scratch contains stale values.

Stateful force-free and public stateless evaluation retain their ordinary
paths and local provider outputs. Direct-parent, reciprocal-parent,
short-parent, and final combined-force reuse remain intact. Provider-internal
AoS, mesh, and other workspace are not reused by this slice. The derived
provider scratch is neither serialized in BGPME001 checkpoints nor bound into
the static fingerprint; the 13-symbol public ABI remains unchanged.

Tests cover empty C++-lane storage, reserved zero-step stability, C++-lane
empty and stale preservation, repeated Rust forceful pointer/capacity/size
retention, same-lane peer, stateless reciprocal, and reciprocal-parent force
bit identity, checkpoint-load stale retention, zero-step stale retention,
exact forceful resynchronization, and interior owner aliases across all three
provider channels plus the particle-view output. Owner overlap is rejected
before output descriptor validation or dereference.

## Frozen evidence graph

- Target predecessor: PR #455, reviewed `ad2a07735153dd2f65e45d51ac7c299dc1c37b70`, merged `2e35ab48b9668627b5f74641c173c2b33df88966`, tree `d5d9735a52a392a44e9a255fd07f1761bc9e363d`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.

The verifier pins all 15 production/test implementation paths, six
canonical/vendor source pairs, the exact 23-path successor delta, 84 static
workflow triggers, four immutable job bodies, and a 266-row source manifest.
It also freezes the unchanged provider ABI header and Rust kernel sources,
the C++ reciprocal evaluator paths, and the Rust x/y/z
resize-before-capacity-before-data binding order.
The CPU-only workflow runs standalone reciprocal and composite dynamics
Release and ASan/UBSan tests, Rust reciprocal and composite library,
integration, and documentation tests, and existing package/format/lint
boundaries. The inherited exact-signature macOS locked-Cargo retry remains
unchanged and fail-closed.

## Boundary

This is not an allocation-free, universal failure-retention,
checkpoint-buffer-aliasing, timing, performance, acceleration, cross-lane
parity, molecular, scientific, HIP-device, qualification, or product claim.
Reservation and every operational authority remain false; the four existing
external/historical blockers and 32 unresolved operational decisions remain
unchanged.

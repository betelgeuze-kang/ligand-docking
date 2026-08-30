# Engine V2 native PME Rust reciprocal-provider spectrum/FFT-line buffer consolidation v1

This bounded CPU-only slice constructs the call-local reciprocal spectrum and
FFT line scratch in one `Vec<Complex>`. Its length is the checked sum of the
validated mesh-point count and the largest mesh-axis length. One
`split_at_mut(mesh_point_count)` exposes a spectrum slice and a disjoint FFT
line-scratch slice. This consolidates the two corresponding fallible reserves
into one reserve per reciprocal evaluation; it does not eliminate the storage.

The backing owner remains private to `compute_with_transform`. The spectrum
slice is passed through charge spreading, the forward transform, the reciprocal
operator, and, when forces are requested, the inverse transform and force
gather. The FFT scratch slice has exactly the maximum-axis length and is shared
by the forward and inverse transforms within that call. Neither slice nor the
owner is retained in provider inputs, output candidates, simulation state,
checkpoints, or any persistent, owner, or cross-call cache.

Transform order and arithmetic remain fixed. Charge spreading still precedes
the forward transform, the reciprocal operator still follows it, and the
inverse transform remains conditional on force production. The separable FFT
continues in z/y/x order with the same caller-supplied scratch contract. The
existing poison-before-read, reversibility, reciprocal-axis, borrowed-input,
transactional-output, and direct-output regressions remain active.

A non-cubic `[4, 8, 16]` regression fixes the backing length at `512 + 16 =
528`, the split lengths at 512 and 16, and pointer adjacency at the split. In
energy-only, transactional-force, and direct-force provider modes, an injected
occurrence-two failure remains pending while energy bits, force bits, protected
output tails, cleared error descriptors, and borrowed input bits match the
owned baseline exactly.

The allocation-failure boundary is intentionally represented by one combined
site. A first-occurrence failure maps to out-of-memory before energy or force
commit, with the bounded detail `particle-mesh spectrum and FFT line-scratch
allocation failed`. Because the old spectrum reserve and later FFT-scratch
reserve are now one earlier combined reserve, their separate error details and
failure timing are intentionally changed. This evidence therefore does not
claim allocation-detail or allocation-timing invariance. The status ABI,
transactional output behavior, public ABI, checkpoint bytes, and static
fingerprint remain unchanged.

PR #461's one-buffer reciprocal-axis contract is inherited unchanged, including
the checked x+y+z length, immutable x/y/z slices, exact axis arithmetic, and
first/second occurrence regressions. PR #460's call-local FFT scratch behavior,
PR #459's borrowed input SoA contract, and the earlier hidden provider,
force-source, reciprocal-parent, direct-output, transactional, and
late-scientific-failure boundaries are also inherited.

## Frozen evidence graph

- Target predecessor: PR #461, reviewed `d67a9335d5e03fed5d5fbb2f1a15e1ece670e975`, merged `33c7c418babe9f8f4822006cf726daf111459c7d`, tree `e8484675f7d9da011ac43165d907071950f3cf8e`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.
- Direct-output precedent: PR #380, reviewed `c486e767b1452cffb9cfd998bc26d5e4403bbd76`, merged `6662f1b53829930a93de0f298b820d5a367cc3dc`, tree `5a2d296e891fe89f3d48c3c6d7b1deb61e81a177`.

The exact delta is one Rust production file, six successor evidence files, and
the frozen PR #461 workflow/unit wiring: nine paths. The verifier fixes 120
workflow triggers, four exact job bodies, the 302-row canonical source
manifest, the sole production delta, the checked one-reserve/split topology,
transform and reciprocal-axis order, bounded failure behavior, frozen
predecessor bytes, public and hidden symbol surfaces, and authority guards. The
predecessor workflow detaches to the exact PR #461 merge before running its
verifier and unit test; its checked-out unit skips only when this successor
profile exists.

The CPU-only workflow retains standalone reciprocal and composite Release and
ASan/UBSan regressions, Rust reciprocal/composite library, integration,
documentation, format, clippy, clean-package, and macOS export boundaries.
Every CMake configuration disables both HIP modes. The inherited
exact-signature macOS locked-Cargo retry remains unchanged and fail-closed.

## Boundary

This is not a peak-memory, persistent reuse, cross-call reuse, owner reuse,
allocation-free, steady-state-allocation-free, timing, performance,
acceleration, cross-lane parity, molecular, scientific, public-benchmark,
HIP-device, qualification, reservation, supervisor, operational-readiness, or
product claim. No molecular or HIP execution and no consumed fixed64 CPU-v7
qualification rerun occur. All operational authorities remain false; the four
external/historical blockers and 32 unresolved operational decisions remain
unchanged.

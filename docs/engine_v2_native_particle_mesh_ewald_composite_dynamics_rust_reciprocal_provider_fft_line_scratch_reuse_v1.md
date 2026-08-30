# Engine V2 native PME Rust reciprocal-provider FFT line-scratch reuse v1

This bounded CPU-only slice allocates one call-local FFT line buffer for each
particle-mesh reciprocal evaluation and passes that same buffer to the forward
and inverse transforms. The buffer length is `max(mesh_x, mesh_y, mesh_z)`. In
force-producing transactional and direct-provider modes this removes only the
second `FftLineScratch` reserve that previously preceded the inverse transform.
Energy-only evaluation already performed one forward transform and therefore
retains one scratch reserve.

The scratch owner remains a private `Vec<Complex>` inside the shared reciprocal
calculation. Transform functions receive `&mut [Complex]`, so they cannot
reserve, resize, or retain the owner. The buffer is not stored in provider
input, output candidates, simulation state, checkpoints, or a cross-call
owner. This is call-local forward/inverse sharing, not persistent reuse.

The z, y, x separable transform order and every copy, one-dimensional FFT, and
write-back loop remain ordered as before. A non-cubic `[4, 8, 4]` regression
holds pointer and capacity identity across both transforms, poisons the entire
scratch before each transform, and verifies reversibility. A shared-pipeline
adapter poisons scratch after the forward transform and preserves exact energy
and force bits after the inverse transform overwrites it.

OOM boundaries remain explicit. The first `FftLineScratch` reserve still maps
to out-of-memory without committing energy or transactional/direct output. A
second-occurrence injection now remains installed and unconsumed while both
force modes succeed with exact owned-baseline bits, preserved input channels,
and untouched output tails. `ReciprocalAxisData` occurrence three is pinned as
the last fallible direct-provider allocation before the first force write.
Transactional mode still retains its later private `ForceOutput` allocation.

PR #459's borrowed input SoA contract is inherited unchanged. Energy-only,
transactional-force, and direct-force provider modes still borrow call-local
x, y, z, and charge channels only after complete descriptor and alias
preflight. The public/native owners, direct-output contract, transactional and
late-scientific-failure commit boundaries, hidden symbols, C++ force-source
consumption, and reciprocal-parent storage rules are unchanged.

This slice does not claim lower peak memory. The one scratch buffer remains
live across reciprocal-axis construction and force gathering, so only the
number of force-mode scratch allocation requests is reduced. Neutrality-sort
scratch, particle assignments, spectrum storage, one FFT line scratch,
reciprocal-axis data, and the transactional force vector remain fallible.

Checkpoint bytes, the static fingerprint, public profile identity, hidden
provider symbols, and the 13-symbol public ABI remain unchanged. Existing
standalone reciprocal, native composite dynamics, runtime composite dynamics,
restart, checkpoint, alias, exact-bit, and frozen-output regressions are rerun
without widening scientific or operational authority.

## Frozen evidence graph

- Target predecessor: PR #459, reviewed `b9fad46d033ebab33fd458010d2ca1f8e9404970`, merged `e42f710090cad19ed169f3a6081648d1b7606613`, tree `1e00fdbc11b26bb463ef55d23356b5cfda8cca5f`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.
- Direct-output precedent: PR #380, reviewed `c486e767b1452cffb9cfd998bc26d5e4403bbd76`, merged `6662f1b53829930a93de0f298b820d5a367cc3dc`, tree `5a2d296e891fe89f3d48c3c6d7b1deb61e81a177`.

The exact delta is one Rust production file, six successor evidence files, and
the frozen PR #459 workflow/unit wiring: nine paths. The verifier fixes 108
workflow triggers, four exact job bodies, the 290-row canonical source
manifest, the sole production delta, the scratch allocation and transform
source order, exact failure boundaries, frozen predecessor bytes, public and
hidden symbol surfaces, and authority guards. The predecessor workflow detaches
to the exact PR #459 merge before running its verifier and unit test; the
checked-out predecessor unit skips only when this successor profile exists.

The CPU-only workflow retains standalone reciprocal and composite Release and
ASan/UBSan regressions, Rust reciprocal/composite library, integration,
documentation, format, clippy, clean-package, and macOS export boundaries.
Every CMake configuration disables both HIP modes. The inherited exact-signature
macOS locked-Cargo retry remains unchanged and fail-closed.

## Boundary

This is not an all-FFT-allocation-elision, persistent or cross-call reuse,
owner reuse, allocation-free, steady-state-allocation-free, peak-memory,
timing, performance, acceleration, cross-lane parity, molecular, scientific,
HIP-device, qualification, reservation, supervisor, operational-readiness, or
product claim. All operational authorities remain false; the four
external/historical blockers and 32 unresolved operational decisions remain
unchanged.

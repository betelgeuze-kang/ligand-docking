# Engine V2 native PME Rust reciprocal-provider axis-data buffer consolidation v1

This bounded CPU-only slice constructs the reciprocal x, y, and z axis data in
one call-local `Vec<ReciprocalAxisData>`. Its length is the checked sum
`mesh_x + mesh_y + mesh_z`. After the complete backing buffer is filled in
x-then-y-then-z order, two immutable `split_at` operations expose three
contiguous, non-overlapping slices with lengths `mesh_x`, `mesh_y`, and
`mesh_z`. This replaces three per-axis fallible reserves with one fallible
`ReciprocalAxisData` reserve per reciprocal evaluation.

The backing owner remains private to `apply_reciprocal_operator`. Only immutable
slices are used by the operator, and neither those slices nor the owner are
retained in provider inputs, output candidates, simulation state, checkpoints,
or a cross-call owner. The allocation is consolidated, not eliminated.

The reciprocal-axis arithmetic remains ordered as before. For every axis, the
same signed mesh index, wave, angle, squared wave, and assignment-modulus
expressions are evaluated. The operator still forms x+y+z wave-squared terms
and x*y*z assignment-modulus terms in the same order. A non-cubic `[4, 8, 16]`
regression verifies the backing length, both slice boundaries, pointer
adjacency, per-axis lengths, x/y/z order, and every derived value bit.

Failure boundaries remain explicit. The sole `ReciprocalAxisData` reserve still
maps an injected first-occurrence failure to out-of-memory before energy or
transactional output commit. On the direct-provider path it remains the last
fallible allocation before the first caller force write; the existing energy,
force-array, output-tail, and input-bit sentinels remain unchanged on that OOM.
An occurrence-two injection remains pending while energy-only, transactional,
and direct provider modes all succeed with exact owned-baseline energy and force
bits, cleared error descriptors, retained input bits, and untouched output
tails.

PR #460's call-local FFT line-scratch contract is inherited unchanged. The one
FFT buffer is still shared only within a call, the z/y/x transform order is
unchanged, and the existing poison, pointer/capacity identity, reversibility,
first-occurrence OOM, and second-occurrence-pending regressions remain active.
PR #459's borrowed input SoA contract and the earlier hidden provider,
force-source, reciprocal-parent, direct-output, transactional, and
late-scientific-failure boundaries are also inherited unchanged.

This slice does not claim lower peak memory. Neutrality-sort scratch, particle
assignments, spectrum storage, one FFT line scratch, one reciprocal-axis data
backing, and the transactional force vector remain fallible where applicable.
Checkpoint bytes, the static fingerprint, public profile identity, hidden
provider symbols, native/C++ ownership, and the 13-symbol public ABI are
unchanged.

## Frozen evidence graph

- Target predecessor: PR #460, reviewed `312717e57f3e1b2aed9eeb0da52c4544efff057b`, merged `759cbd3abeda74bc385c6a5091cea834f4f06458`, tree `7343cfee07e40a16460e82ff423e2c9ef353342b`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.
- Direct-output precedent: PR #380, reviewed `c486e767b1452cffb9cfd998bc26d5e4403bbd76`, merged `6662f1b53829930a93de0f298b820d5a367cc3dc`, tree `5a2d296e891fe89f3d48c3c6d7b1deb61e81a177`.

The exact delta is one Rust production file, six successor evidence files, and
the frozen PR #460 workflow/unit wiring: nine paths. The verifier fixes 114
workflow triggers, four exact job bodies, the 296-row canonical source
manifest, the sole production delta, the one-reserve and immutable-slice source
topology, x/y/z arithmetic order, exact failure boundaries, frozen predecessor
bytes, public and hidden symbol surfaces, and authority guards. The predecessor
workflow detaches to the exact PR #460 merge before running its verifier and
unit test; the checked-out predecessor unit skips only when this successor
profile exists.

The CPU-only workflow retains standalone reciprocal and composite Release and
ASan/UBSan regressions, Rust reciprocal/composite library, integration,
documentation, format, clippy, clean-package, and macOS export boundaries.
Every CMake configuration disables both HIP modes. The inherited
exact-signature macOS locked-Cargo retry remains unchanged and fail-closed.

## Boundary

This is not a reciprocal-axis-allocation-elision, all-allocation-elision,
persistent or cross-call reuse, owner reuse, allocation-free,
steady-state-allocation-free, peak-memory, timing, performance, acceleration,
cross-lane parity, molecular, scientific, HIP-device, qualification,
reservation, supervisor, operational-readiness, or product claim. All
operational authorities remain false; the four external/historical blockers
and 32 unresolved operational decisions remain unchanged.

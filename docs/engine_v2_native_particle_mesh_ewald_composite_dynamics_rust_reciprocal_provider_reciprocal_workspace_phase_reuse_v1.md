# Engine V2 native PME Rust reciprocal-provider reciprocal workspace phase reuse v1

This bounded CPU-only slice replaces the separate call-local spectrum/FFT-line
and reciprocal-axis buffers with one `ReciprocalWorkspace`. Its sole
`Vec<Complex>` has the checked length `M + A`, where `M` is the validated mesh
point count and `A = x + y + z`. One split at `M` exposes the spectrum and a
disjoint tail. This consolidates two call-local reserves and allocation sites
into one reserve and site per reciprocal evaluation; it does not eliminate the
workspace allocation.

The tail is reused in three ordered phases. Its prefix of length
`L = max(x, y, z)` is first caller-supplied forward-FFT scratch. The complete
tail is then overwritten in x/y/z order with reciprocal-axis data: `real`
stores exact `wave_squared` bits and `imaginary` stores exact
`assignment_modulus` bits. The reciprocal operator borrows those values
immutably. When forces are requested, the same prefix is reborrowed as inverse
FFT scratch; the suffix `tail[L..A]` remains unchanged. The short, disjoint
reborrows preserve forward-transform, operator, optional inverse-transform,
and z/y/x FFT order without unsafe slice conversion.

The final nonfinite grid scan remains restricted to the spectrum slice. It
does not inspect the phase-reused tail, whose prefix contains FFT scratch after
the inverse phase. Force and energy arithmetic, public and status ABI,
checkpoint bytes, static fingerprint, transactionality, and the existing late
scientific-failure boundary remain frozen.

A non-cubic `[4, 8, 16]` regression fixes `M = 512`, `A = 28`, `L = 16`, and
the backing length at 540. It fixes the spectrum/tail split and axis offsets at
0, 4, and 12, pointer adjacency, and exact real/imaginary axis bits. A phase
regression poisons the forward prefix, proves FFT overwrite before read, proves
the axis phase overwrites the whole tail, proves the operator leaves all axis
bits unchanged, then poisons and reuses the inverse prefix while proving the
12-element suffix remains bit-identical. No assertion equates `Vec` capacity
with the requested length because `try_reserve_exact` does not promise that.

Energy-only, transactional-force, and direct-force provider regressions inject
occurrence two at `ReciprocalWorkspace`; it remains pending while energy and
force bits, protected output tails, cleared errors, and borrowed input bits
match the owned baseline. Occurrence one fails all three modes before output
commit with out-of-memory and the exact bounded detail `particle-mesh spectrum,
FFT line-scratch, and reciprocal axis-data allocation failed`. Transactional
force retains four fallible sites; energy-only and direct force retain three.

The allocation detail and failure timing intentionally change. The former
late reciprocal-axis allocation no longer exists, and the larger combined
reserve occurs at the earlier workspace boundary. Therefore this slice does
not claim allocation-detail or allocation-timing invariance or preservation of
the old direct last-prewrite axis-allocation boundary.

This is also not a peak-memory claim. For `[4, 4, 4]` with `P = 4096`, the old
axis owner could be dropped before force gathering, leaving `M + L` Complex
entries live in that cluster. The new workspace retains `M + A`; because
`A - L = 8`, the new live payload during gather can be 128 bytes larger when a
`Complex` is 16 bytes. The bounded claim is only two call-local cluster
reserves/sites to one and removal of the separate axis `Vec`.

## Frozen evidence graph

- Target predecessor: PR #462, reviewed `e12c9fd82a0376bc7d83d6e83a28b9c950f321b5`, merged `761e979e36b048cc19f3ef3ff4a90d373e1e8315`, tree `222129db34948751bcadd391bde11943898b8f91`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.
- Direct-output precedent: PR #380, reviewed `c486e767b1452cffb9cfd998bc26d5e4403bbd76`, merged `6662f1b53829930a93de0f298b820d5a367cc3dc`, tree `5a2d296e891fe89f3d48c3c6d7b1deb61e81a177`.

The exact delta is one Rust production file, six successor evidence files, and
the frozen PR #462 workflow/unit wiring: nine paths. The verifier fixes 126
unique pull/push triggers, four exact job bodies, the 308-row canonical source
manifest, the sole production delta, phase order and borrow topology, exact
failure behavior, frozen predecessor bytes, public and hidden symbol surfaces,
and authority guards. The predecessor workflow detaches to the exact PR #462
merge before running its verifier and unit test; its checked-out unit skips
only when this successor profile exists.

## Boundary

The workspace is call-local and not retained. This is not a persistent,
cross-call, owner, capacity-equality, peak-memory-reduction, allocation-free,
steady-state-allocation-free, timing, performance, acceleration, cross-lane
parity, molecular, scientific, public-benchmark, HIP-device, qualification,
reservation, supervisor, operational-readiness, or product claim. No molecular
or HIP execution and no consumed fixed64 CPU-v7 qualification rerun occur. All
operational authorities remain false; the four external/historical blockers
and 32 unresolved operational decisions remain unchanged.

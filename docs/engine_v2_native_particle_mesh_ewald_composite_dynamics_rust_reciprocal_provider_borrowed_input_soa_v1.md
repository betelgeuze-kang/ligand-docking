# Engine V2 native PME Rust reciprocal-provider borrowed-input SoA v1

This bounded CPU-only slice makes every hidden Rust particle-mesh reciprocal
provider mode consume the caller's x, y, z, and charge channels through
call-local borrowed slices. Energy-only evaluation, transactional force
evaluation, and the hidden direct-force-output route now share the same
borrowed input. The four provider channel-copy allocations and the separate
`Vec<Position>` AoS rematerialization are removed from all three modes.

An internal `ReciprocalInput` accessor keeps the owned test input and borrowed
provider input on one validation and calculation pipeline. Particle order,
coordinate order, charge order, neutrality summation, mesh assignment, FFT,
reciprocal operator, force gathering, error mapping, and result rounding remain
the established sequence. Exact-bit tests compare the owned evaluator with
borrowed energy-only, transactional-force, and direct-force results.

The provider finishes descriptor, range, header, capacity, mutable-output
disjointness, and every input/output alias check before it constructs a slice.
Zero-count null channels become `&[]` without calling `from_raw_parts`. Nonzero
input channels must remain initialized and immutable for the call. The borrowed
view is local to `evaluate_provider_impl`; it is not placed in the returned
candidate, retained across calls, serialized, or exposed through public ABI.

Output ownership and commit boundaries are unchanged. Energy-only evaluation
does not allocate force storage. Transactional force evaluation retains its
private force `Vec` and commits energy and forces only on success. Direct force
evaluation writes caller-owned scratch after all remaining fallible work and
commits energy only on success; a deliberately late scientific failure may
leave direct force scratch disposable. Input bits remain unchanged on success,
allocation failure, alias rejection, and late failure.

This is not an allocation-free path. Neutrality-sort scratch, particle
assignments, the spectrum, FFT line scratch, reciprocal-axis data, and the
transactional force vector remain fallible allocations. Their OOM details and
pre-write sentinels, including the inverse-FFT second-occurrence boundary, stay
covered.

The native C++ adapter already builds a private descriptor from `bg_system`-
owned vectors and makes no additional C++ input copy. Those public/native
owners remain deep-owned storage; this change does not create a public zero-copy
API, persistent input view, or cross-call borrow. PR #458's provider force-source
SoA consumption, finite scan, reciprocal-parent empty/stale preservation,
two-pass composite force validation, and final SoA commit remain byte-frozen.

Checkpoint bytes, the static fingerprint, public profile identity, the hidden
provider symbols, and the 13-symbol public ABI remain unchanged. Stateless and
stateful composite callers that select the Rust provider receive the same
call-local borrowing internally, while C++-lane evaluation is unchanged.

## Frozen evidence graph

- Target predecessor: PR #458, reviewed `9d5e33bb9131bf029a21141883949c5543de2eb5`, merged `4dafdf5dee9e7a6357ff50006c9ae6dd9d757a3e`, tree `fee1fa12d62a6ef65555a93736454168c3b552a1`.
- Architecture predecessor: PR #453, reviewed `68607f1b4c1311755b565a2ace2e681695d7f764`, merged `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged `735883551510cbef91adc3e57dc131a1234b67fb`, tree `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.
- Direct-output precedent: PR #380, reviewed `c486e767b1452cffb9cfd998bc26d5e4403bbd76`, merged `6662f1b53829930a93de0f298b820d5a367cc3dc`, tree `5a2d296e891fe89f3d48c3c6d7b1deb61e81a177`.

The exact delta is one Rust production file, six successor evidence files, and
the frozen PR #458 workflow/unit wiring: nine paths. The verifier fixes 102
workflow triggers, four job bodies, the 284-row canonical source manifest, the
single production delta, frozen predecessor production/test bytes, public and
hidden symbol boundaries, borrowed-slice construction order, all three output
modes, remaining OOM boundaries, and authority guards. The predecessor workflow
detaches to the exact PR #458 merge before running its verifier and unit test;
the checked-out predecessor unit skips only when this successor profile exists.

The CPU-only workflow retains standalone reciprocal and composite Release and
ASan/UBSan regressions, Rust reciprocal/composite library, integration,
documentation, format, clippy, clean-package, and macOS export boundaries.
Every CMake configuration disables both HIP modes. The inherited exact-signature
macOS locked-Cargo retry remains unchanged and fail-closed.

## Boundary

This is not an allocation-free, public zero-copy, persistent-borrow,
universal-input-elision, timing, performance, acceleration, cross-lane parity,
molecular, scientific, HIP-device, qualification, reservation, supervisor,
operational-readiness, or product claim. All operational authorities remain
false; the four external/historical blockers and 32 unresolved operational
decisions remain unchanged.

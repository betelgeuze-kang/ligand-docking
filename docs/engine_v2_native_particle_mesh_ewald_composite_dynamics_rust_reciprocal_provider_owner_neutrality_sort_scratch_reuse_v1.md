# Engine V2 native PME Rust reciprocal-provider owner neutrality-sort scratch reuse v1

This bounded CPU-only slice retains the existing neutrality-sort `Vec<f64>`
inside each composite simulation owner's private `ProviderForceScratch`. It is
used only together with the already-retained reciprocal workspace on the
stateful Rust force-producing route. The C++ reference lane remains outside
this Rust scratch. The stateful Rust force-free route, stateless and
transactional Rust routes, and the predecessor workspace-only hidden entry
keep their established call-local neutrality-sort allocation behavior.

The private provider ABI gains a distinct 72-byte, zero-initializable
neutrality-sort descriptor with EMPTY, READY, and LEASED states. Its type tag
cannot be substituted for the reciprocal-workspace tag. The descriptor is
embedded inline beside the existing owner-private workspace and force channels;
it is not a public header type, exported symbol, checkpoint field, or
static-fingerprint input. `ProviderForceScratch` remains neither copyable nor
movable and its `noexcept` destructor releases both canonical READY Rust
allocations. Null, all-zero EMPTY, detectably malformed, already LEASED, and
repeated neutrality destroy calls fail closed. Release is authorized only for
private Rust-origin canonical READY raw parts.

Rust preflights both descriptors and both complete backing capacities against
each other, the error and energy descriptors, every input channel, the force
descriptor, and every force channel before either ownership lease or any input
borrow. Each lease reconstructs the exact Rust `Vec`, publishes LEASED while
Rust owns it, and externalizes EMPTY or canonical READY raw parts on every
success, error, or panic unwind. The owner-private contract does not authorize
concurrent access.

Composite report/error, particle-view, and absolute-step overlap preflights now
also cover the complete neutrality-sort capacity. Malformed length/capacity,
noncanonical zero-capacity raw parts, null storage, byte-count overflow,
descriptor alias, workspace/scratch backing cross-alias, logical-payload alias,
and spare-capacity tail alias fail closed before any backing `Vec`
reconstruction, slice formation,
or channel borrow. The raw tail-alias regression forms an address only; it
neither reads nor writes uninitialized spare capacity.

`NeutralitySortScratch::prepare` uses the validated charge slice, so its logical
length is exactly the particle count. It reserves only when that length exceeds
capacity, and reserve completes before the old logical payload is cleared. A
successful prepare then overwrites the complete logical range from the charge
slice before sorting or summing. The frozen comparator remains ascending
absolute magnitude with total-value tie breaking, followed by the same
`CompensatedSum` arithmetic and iteration order.

Cold first use preserves the allocation order `NeutralitySort`,
`ParticleAssignments`, `ReciprocalWorkspace` and the exact first-site detail
`neutrality summation scratch allocation failed`. Warm same-shape, shrink, and
other capacity-sufficient calls do not request a neutrality reserve; growth
beyond capacity uses one neutrality reserve. A failed growth reserve preserves
the prior pointer, length, capacity, and logical payload. Poison regressions
show that the next successful prepare overwrites the retained logical payload
before it is read, and panic and late-error regressions restore both owner
leases before recovery.

Failure retention is intentionally conditional. A failure at the neutrality
reserve leaves a cold descriptor EMPTY or preserves its prior READY allocation;
after neutrality prepare succeeds, a later particle-assignment or reciprocal-
workspace allocation failure may leave the newly provisioned neutrality
scratch READY. This slice makes no unconditional failure-storage-retention
claim.

Native regressions prove new owners and force-only reserve operations leave the
neutrality scratch EMPTY; the eligible stateful Rust force-producing route
provisions it; capacity-sufficient calls retain its storage; and independent
owners do not share it. C++ interleave, zero-step force-free evaluation, and
checkpoint load/reload preserve the established derived-scratch behavior.
Checkpoint bytes and static fingerprints exclude both private allocations.
Checkpoint write still stages complete temporary bytes before `memmove`, and
load still copies input bytes before validation and commit, so the frozen
checkpoint buffer/scalar semantic alias policy is unchanged.

## Frozen evidence graph

- Target predecessor: PR #464, reviewed
  `c3a212bff356675ae7a27bb3c54020b6436db6dd`, merged
  `5a629c5fffbfc0e2526de953dcdaaa4d946a5ee9`, tree
  `fc9c801052e3a87129696d51aa00068eb0bdc383`.
- Target profile SHA-256:
  `34caf3981b79a40ff496b76ff6d6fe5e6aefdb69a34d7238c2e93f708d41bbb3`.
- Target 314-row source manifest SHA-256:
  `8b140b96f482911fc5afe019645da5a8089b62d98fe9112af592c9b576f89a1a`.
- Architecture predecessor: PR #453, reviewed
  `68607f1b4c1311755b565a2ace2e681695d7f764`, merged
  `35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a`, tree
  `b22c5fd115a5c8e28856872df57127ecdd28d9b5`.
- Inherited reciprocal evaluator: PR #440, reviewed
  `098bce0d726dbed6e4bf7b533e0445f81e244ea2`, merged
  `735883551510cbef91adc3e57dc131a1234b67fb`, tree
  `6c2b6f3960b6df0592b78bb44e429389aa58bcbb`.
- Direct-output precedent: PR #380, reviewed
  `c486e767b1452cffb9cfd998bc26d5e4403bbd76`, merged
  `6662f1b53829930a93de0f298b820d5a367cc3dc`, tree
  `5a2d296e891fe89f3d48c3c6d7b1deb61e81a177`.

The exact delta is nine production paths, three native regression paths, six
successor evidence files, and the frozen PR #464 workflow/unit wiring: twenty
paths. The verifier freezes 138 unique pull/push triggers, four exact job
bodies, the 320-row canonical source manifest, all twelve predecessor and
successor source hashes, four canonical/vendor mirror pairs, both private
descriptor/lease contracts, 13 unchanged public symbols, hidden-symbol
boundaries, checkpoint/static-fingerprint sources, allocation behavior, and
authority guards. The predecessor workflow detaches to the exact PR #464 merge
before running its verifier and unit; its checked-out unit skips only when this
successor profile exists.

## Boundary

The bounded claim is only that an eligible owner's stateful Rust force-producing
route avoids a neutrality-sort reserve after successful provisioning while
capacity is sufficient. Particle-assignment allocation remains. This is not an
allocation-elision, allocation-free, steady-state-allocation-free,
provider-wide, force-free, stateless, transactional, concurrent, capacity-
equality, peak-memory, timing, performance, acceleration, cross-lane parity,
molecular, scientific, public-benchmark, HIP-device, qualification,
reservation, supervisor, operational-readiness, or product claim. No molecular
or HIP execution and no consumed fixed64 CPU-v7 qualification rerun occur. All
operational authorities remain false; the four external/historical blockers
and 32 unresolved operational decisions remain unchanged.

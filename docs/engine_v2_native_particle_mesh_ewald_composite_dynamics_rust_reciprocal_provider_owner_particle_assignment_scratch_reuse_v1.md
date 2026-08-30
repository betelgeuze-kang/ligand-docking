# Engine V2 native PME Rust reciprocal-provider owner particle-assignment scratch reuse v1

This bounded CPU-only slice retains the Rust particle-assignment vector inside
each composite simulation owner's private `ProviderForceScratch`. Reuse occurs
only on the eligible stateful Rust force-producing route, together with the
already retained neutrality-sort scratch and reciprocal workspace. The C++
reference lane, stateful Rust force-free route, stateless and transactional
Rust routes, and both legacy hidden reusable-storage entries retain their
established call-local particle-assignment allocation behavior.

The private provider ABI gains a third distinct 72-byte, zero-initializable
descriptor. Its logical length and allocation capacity are opaque byte counts;
the provider contract does not expose or freeze the internal
`ParticleAssignment` C layout or element size. Rust defines EMPTY, canonical
READY `PAS1`, and LEASED `PAL1` states whose tags cannot be substituted for
the workspace or neutrality-sort tags. The descriptor is embedded inline
beside the existing private descriptors and force channels. It is absent from
public headers, exports, checkpoints, and the static fingerprint.
`ProviderForceScratch` remains noncopyable and nonmovable, and its
`noexcept` destructor releases all three canonical READY Rust allocations.

Only a private Rust-origin canonical READY descriptor may be converted back to
raw vector parts. Preflight validates whole-element byte counts, alignment,
ordering, addressability, and canonical zero-capacity raw parts before that
conversion. The internal assignment element has no drop glue, which is required
for the bounded test-only logical-byte shrink contract. Null, all-zero EMPTY,
detectably malformed, already LEASED, type-swapped, self-aliased, and repeated
destroy calls fail closed; a valid READY allocation is destroyed exactly once.

Rust first proves writable error storage disjoint from all three descriptors,
their complete backing capacities, every input channel, the force descriptor,
and every force channel before a diagnostic write. It then completes the full
pairwise output and input disjointness preflight before any ownership lease,
byte-to-element conversion, or input borrow. Three RAII leases publish LEASED
while Rust owns the vectors and restore EMPTY or canonical READY on success,
error, and panic unwind. Concurrent use is outside the contract.

Composite report/error, particle-view, and absolute-step overlap checks cover
the complete particle-assignment byte capacity, including spare capacity.
Logical-prefix and capacity-tail aliases fail before descriptor access or owner
mutation. Checkpoint bytes and static fingerprints still exclude all private
scratch. Checkpoint write/load staging and the established checkpoint semantic
alias policy are unchanged.

`ParticleAssignmentScratch::prepare` reserves only when particle count exceeds
capacity. Reserve completes before `clear`, so a failed growth preserves prior
raw parts and payload. A successful prepare clears the logical vector and
recomputes every assignment from the current positions, cell, and validated
mesh dimensions. Poison and changed-position regressions prove that the full
logical range is overwritten and that changed coordinates produce the exact
fresh assignment bits.

Cold first use preserves the order `NeutralitySort`,
`ParticleAssignments`, `ReciprocalWorkspace` and the exact assignment OOM
detail `particle assignment allocation failed`. Warm same-shape and other
capacity-sufficient calls leave an injected assignment reserve pending. Growth
beyond capacity issues one assignment reserve. Failure retention remains
conditional: assignment-reserve failure preserves a cold EMPTY descriptor or
the prior READY allocation, while a later reciprocal-workspace failure may
leave newly provisioned neutrality and assignment allocations READY.

Native and Rust regressions prove only the eligible stateful Rust
force-producing owner route provisions this scratch, independent owners retain
disjoint allocations, legacy routes do not consume it, C++ interleave and
checkpoint reload preserve it as derived private state, full-capacity output
aliases fail closed, and all three leases recover after late errors and panic.

## Frozen evidence graph

- Target predecessor: PR #465, reviewed
  `0c6a50e85a4613baea889f6ded810a53955d6326`, merged
  `dacb1fb5cb466a7ecb43b32b2a1039734bcfdfdb`, tree
  `09ae686da88e9875bd0646aa9be6774063f1079a`.
- Target profile SHA-256:
  `4ee3d32e690401d06c18390d247e0ca492339b926ba55fab6e6f946ea12f7919`.
- Target 320-row source manifest SHA-256:
  `a19e69257a2b9c102bd37fc925969f042799fdbad92ff8fb82739b5eca6b97fe`.
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
successor evidence files, and frozen PR #465 workflow/unit wiring: twenty
paths. The verifier derives 144 unique, symmetric pull/push triggers and a
326-row canonical source manifest; freezes all twelve predecessor and successor
source hashes plus four canonical/vendor mirror pairs; and checks the three
private descriptor/lease contracts, 13 unchanged public symbols, hidden
entries, checkpoint/static-fingerprint exclusion, allocation boundaries, and
authority guards. The predecessor workflow detaches to the exact PR #465 merge
before running its verifier and unit, whose suite skips only when this successor
profile exists.

## Boundary

The bounded positive claim is only capacity-sufficient owner-private
particle-assignment reserve elision after successful provisioning on the
eligible route. Global particle-assignment allocation elision remains false,
as do allocation-free, provider-wide, force-free, stateless, transactional,
concurrent, capacity-equality, peak-memory, timing, performance, acceleration,
cross-lane parity, molecular, scientific, public-benchmark, HIP-device,
qualification, reservation, supervisor, operational-readiness, and product
claims. No molecular or HIP execution and no consumed fixed64 CPU-v7
qualification rerun occur. All operational authorities remain false; the four
external/historical blockers and 32 unresolved operational decisions are
unchanged.

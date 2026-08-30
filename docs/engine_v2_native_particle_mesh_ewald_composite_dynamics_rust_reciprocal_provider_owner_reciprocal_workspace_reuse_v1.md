# Engine V2 native PME Rust reciprocal-provider owner reciprocal-workspace reuse v1

This bounded CPU-only slice retains the existing `ReciprocalWorkspace` backing
inside each composite simulation owner's private `ProviderForceScratch`. Only
the stateful Rust force-producing provider route leases that storage across
calls. The C++ reference lane, stateful Rust force-free route, stateless Rust
provider routes, and the established transactional and direct hidden entries
remain call-local.

The private provider ABI gains a 72-byte, zero-initializable workspace
descriptor with EMPTY, READY, and LEASED states. It is embedded inline beside
the three provider force channels; it is not a public header type, exported
symbol, checkpoint field, or static-fingerprint input. `ProviderForceScratch`
is neither copyable nor movable and releases a canonical READY Rust allocation
from its `noexcept` destructor. Null, all-zero EMPTY, detectably malformed,
already LEASED, and repeated destroy calls fail closed without reconstructing
an untrusted allocation. The destroy safety contract authorizes release only
for private, Rust-origin canonical READY raw parts.

Rust preflights the workspace descriptor and its complete backing capacity
against the error descriptor, all input channels, energy, force descriptors,
and force channels before acquiring ownership or borrowing input. A lease
reconstructs the exact Rust `Vec`, writes LEASED while the allocation is owned
by Rust, and externalizes canonical READY raw parts on every success, error,
or panic unwind. The owner-private contract does not authorize concurrent use.

The composite dynamics report/error, particle-view, and absolute-step output
overlap preflights also cover the workspace's full backing capacity. Malformed
length/capacity, zero-capacity raw parts, null storage, and byte-count overflow
fail closed. Integration validates alignment and representable error/report
ranges, rejects context, owner, workspace, and output/output overlap, and only
then reads the initialized output descriptors. Particle-view and absolute-step
outputs likewise reject owner/workspace overlap before descriptor access or
output writes. These checks do not add the private workspace to checkpoint or
static-fingerprint inputs. They do not change checkpoint buffer/scalar alias
semantics: the frozen checkpoint guard continues to exclude derived scratch,
including workspace payload, while write commits from complete temporary bytes
and load copies input bytes before validation and state commit.

`ReciprocalWorkspace::prepare` keeps the checked logical length `M + A`, where
`M` is the mesh-point count and `A = x + y + z`. It calls the established
`ReciprocalWorkspace` reserve site only when the requested length exceeds
capacity. Cold first use therefore preserves the allocation order
`NeutralitySort`, `ParticleAssignments`, `ReciprocalWorkspace` and the exact
out-of-memory detail `particle-mesh spectrum, FFT line-scratch, and reciprocal
axis-data allocation failed`. A warm same-shape call leaves occurrence one at
that site pending. Same-shape, smaller-shape, and capacity-sufficient growth
do not reserve; growth beyond capacity performs one workspace reserve.

Every successful prepare clears the retained spectrum before charge spreading,
which remains additive. The FFT/axis tail is overwritten by the already-frozen
forward-FFT, axis-data, and optional inverse-FFT phases. Regressions poison the
retained backing before warm reuse, cover shrink and capacity growth, and prove
that failed growth retains the previous pointer, length, capacity, and payload.
An injected panic after prepare restores READY and the next call succeeds.
Capacity equality and pointer identity across an actual growth operation are
not asserted.

Native regressions prove new owners and force-only reserve operations leave the
workspace EMPTY; the first stateful Rust force-producing evaluation provisions
it; repeated evaluations retain same-capacity storage; and independent owners
never share storage. Checkpoint load does not populate another owner, while a
C++-lane interleave, checkpoint reload, and zero-step force-free restart leave
an already-derived owner workspace untouched. Test-only introspection remains
outside public exports.

## Frozen evidence graph

- Target predecessor: PR #463, reviewed
  `375e29d8fe43ca588366139fdb5ea0c1a4016b0f`, merged
  `a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c`, tree
  `84cdf4c64f8b41f99380700f0cdb090a852a3c03`.
- Target profile SHA-256:
  `ddf1aaf25370464dab2717f83ad4f746ce94cf0d4914adb198a1b57487f365e5`.
- Target 308-row source manifest SHA-256:
  `f659b995b298aa5a79977a99a50ad9853f7e0c2786ea9331f8471a0673e72ba5`.
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
successor evidence files, and the frozen PR #463 workflow/unit wiring: twenty
paths. The verifier fixes 132 unique pull/push triggers, four exact job bodies,
the 314-row canonical source manifest, all twelve source hashes, four
canonical/vendor mirror pairs, the private descriptor and lease contracts,
public and hidden symbol boundaries, checkpoint bytes and the unchanged
static-fingerprint computation,
allocation failure behavior, and authority guards. The predecessor workflow
detaches to the exact PR #463 merge before running its verifier and unit test;
its checked-out unit skips only when this successor profile exists.

## Boundary

The bounded claim is one owner's stateful Rust force-producing reciprocal
workspace reserve avoided after successful provisioning while capacity is
sufficient. Neutrality-sort and particle-assignment allocations remain, and
cold use or growth can allocate. This is not an allocation-free,
steady-state-allocation-free, universal-provider, force-free, stateless,
transactional, concurrent, capacity-equality, growth-pointer-identity,
peak-memory, timing, performance, acceleration, cross-lane parity, molecular,
scientific, public-benchmark, HIP-device, qualification, reservation,
supervisor, operational-readiness, or product claim. No molecular or HIP
execution and no consumed fixed64 CPU-v7 qualification rerun occur. All
operational authorities remain false; the four external/historical blockers
and 32 unresolved operational decisions remain unchanged.

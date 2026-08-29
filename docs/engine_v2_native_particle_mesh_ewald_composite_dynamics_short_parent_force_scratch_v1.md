# Engine V2 particle-mesh Ewald composite-dynamics short-parent force scratch v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGPME001` 104-byte checkpoint header. Each particle-mesh Ewald
composite-dynamics owner now retains a private short-parent `Evaluation`.
Successful force-producing stateful calls in both explicit CPU lanes reuse the
three short-parent force-vector storages. The existing private short-system
scratch and final SoA force-output storage contracts remain in place.

Stateful calls supply the short-system scratch, short-parent evaluation, and
Rust forcefield-validation cache as one all-nonnull group; stateless calls
supply an all-null group and retain ordinary local evaluation. Create-time,
zero-step, and other force-free stateful evaluation uses a local `Evaluation`,
so it does not change retained short-parent force storage or the Rust cache.
The dynamics output-alias guard includes all three active short-parent force
channels.

The short-parent force scratch and validation cache are derived,
non-authoritative state. Neither is serialized in checkpoints or included in
the static fingerprint. Regression coverage exercises empty and reserved
state, pointer/capacity retention, non-aliasing against authoritative owner,
short-system, and final-output storage, repeated same-lane identity, checkpoint
A to state B followed by loading A, stale zero-step preservation, forceful
resynchronization, and rejection of an output that aliases active scratch.
It covers both the C++ CPU-reference lane (cache byte remains zero) and Rust
CPU lane (cache byte becomes one after forceful validation).

Repeated late direct-local failures preserve authoritative rollback and the
short-parent force-vector storage identity. Such failures may mutate derived
scratch contents or cache state. This evidence does not claim retention for
upstream failures, reciprocal failures generally, or every failure path.

The immediate architecture predecessor is PR #449: reviewed head
`0268e1731eb5f8b472cb527ac277a66c7ce4317f`, squash merge
`11ee408d89c44e70188af5133544ecebd604b182`, tree
`01d37e1adf097384c1e895fa637af0cfff45f4e8`, profile SHA-256
`745a4413cc875f143be460f372ad4ddc809af0588df65e736d68361fce418485`,
and 220-entry manifest SHA-256
`38d48a481963dc5a4a6202f6b6f794e9984e64ea43bb2ebd11a3aeb7e7815a1f`.
The target predecessor is PR #448: reviewed head
`4ace5d02dd90618140baecfeba28fdf93f3b342f`, squash merge
`5d4a55c85a80b62d38e79ea608e4850a6966ceeb`, tree
`1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73`, profile SHA-256
`72982489ea675272607013d9495f36ea5f649eb94f57d35e6a37a9e8ebfef476`,
and 214-entry manifest SHA-256
`691792ba1f59fb314bd7c4dc8b6ae746f25629a840b9e64da6b3f54eba561028`.
Its inherited force-scratch predecessor is PR #445: reviewed head
`801a85d56846c464b3a618ecacca867cd12a8c9f`, squash merge
`c53f7993ec06c4ac04a4907b40f179d12fbe309a`, tree
`2bb25b756b802671bcfc5f3ac95b26df3b284956`, profile SHA-256
`32129a32d0b351ac265fda21906e707cc708c664241715b4d0d92fa3cc013b62`,
and 194-entry manifest SHA-256
`d428b3f18d26382fbb7e5e8a48f3a114eb953b8708bec77c4f00ec6c0d1bcc3f`.

This slice makes no allocation-free, timing, performance, acceleration,
cross-lane bit-parity, product, or scientific claim. All authority remains
false. The four operational blockers and 32 unresolved decisions remain
controlling. CI is synthetic CPU-only and performs no qualification,
HIP-device, molecular, benchmark, supervisor, or reservation execution.

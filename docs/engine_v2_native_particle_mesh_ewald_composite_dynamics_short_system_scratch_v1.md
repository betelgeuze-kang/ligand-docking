# Engine V2 particle-mesh Ewald composite-dynamics short-system scratch v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGPME001` 104-byte checkpoint header. It gives each
particle-mesh Ewald composite-dynamics owner private short-system scratch
storage while preserving the existing persistent final SoA force-output
storage. The explicit C++ CPU-reference and Rust CPU lanes refresh the three
position channels in place before short-range evaluation while retaining the
stateless API's local-copy path.

The scratch is initialized only after static compatibility succeeds and
deep-owns all eight channel storages captured from the owner. Its unit, shape,
mass, and exact positive-zero charge data originate at initialization. Only
the three position channels are refreshed and current; the unused velocity
contents are derived and non-authoritative. Shape, unit, or bitwise nonzero
charge drift is rejected before force evaluation. Checkpoint bytes and the
static fingerprint omit the scratch, loading a checkpoint does not publish it,
and the next evaluation resynchronizes positions without replacing storage.
Stateful dynamics report/error output-alias validation includes the private
scratch storage.

Regression coverage exercises both explicit CPU lanes, initial and zero-step
state, repeated integration, A-to-B state followed by loading checkpoint A,
post-load resynchronization, negative-zero and shape/unit tampering, and
repeated late typed PME failure. A late failure may refresh non-authoritative
scratch contents, but authoritative particles, reports, checkpoints, final
force-output storage, and short-system scratch storage identity remain
transactional.

The target PME predecessor is PR #445: reviewed head
`801a85d56846c464b3a618ecacca867cd12a8c9f`, squash merge
`c53f7993ec06c4ac04a4907b40f179d12fbe309a`, tree
`2bb25b756b802671bcfc5f3ac95b26df3b284956`, profile SHA-256
`32129a32d0b351ac265fda21906e707cc708c664241715b4d0d92fa3cc013b62`,
and 194-entry manifest SHA-256
`d428b3f18d26382fbb7e5e8a48f3a114eb953b8708bec77c4f00ec6c0d1bcc3f`.
The immediate architecture and optimization predecessor is PR #447: reviewed
head `5d4d238a2eea2765b6ac5d5d3f596487bd5b8cd6`, squash merge
`3f68361985e57f4c5ee547ba690f4a6859bd8b34`, tree
`1fc25fdc53ae1d2303a6fe6abe279e520fc13f12`, profile SHA-256
`8be1f7d28f936f78486bfabaf9fdfc2e1e334285864138639c796d36a454d3cb`,
and 208-entry manifest SHA-256
`85c17310e995b8eb22028083694f710414e523884a0ae9834b5258dfcb6c48fd`.
The frozen target lineage continues through stateful PME dynamics PR #444,
stateless PME composite PR #442, and backend-preflight PR #443.

This slice makes no allocation-free, timing, performance, acceleration,
cross-lane bit-parity, product, or scientific claim. All authority remains
false. The four operational blockers and 32 unresolved decisions remain
controlling. CI is synthetic CPU-only and performs no qualification,
HIP-device, molecular, benchmark, supervisor, or reservation execution.

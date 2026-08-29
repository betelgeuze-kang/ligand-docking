# Engine V2 particle-mesh Ewald composite-dynamics combined-force SoA v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGPME001` 104-byte checkpoint header. On a successful
force-producing stateful call, the particle-mesh Ewald composite evaluator records
the fully combined force directly into the dynamics provider's existing final
SoA `Evaluation`. That path no longer materializes a combined
`Evaluation::forces` AoS vector and no longer performs the dynamics-layer
AoS-to-SoA copy.

The direct-write pointer is required exactly when evaluation is both stateful
and force-producing. It must not alias the retained short-parent
`Evaluation`. Stateless force-producing calls still return the public
composite AoS representation, while stateful force-free calls pass no final
SoA output and retain their prior behavior. Existing short-system,
short-parent force-scratch, Rust validation-cache, and final force-output
scratch contracts remain in place.

Before any final SoA channel is resized or written, the evaluator checks all
parent force shapes and performs a complete finite-value scan over each short,
direct, reciprocal, particle-mesh Ewald, and combined component. The proven
late typed direct-local failure returns before final SoA recording; this slice
does not claim reciprocal-failure storage retention. Runtime regression covers both
explicit CPU lanes, reserved pointer/capacity/size retention across successful
forceful calls, same-lane peer and stateless AoS bit identity, create and
zero-step stability, checkpoint A to state B followed by loading A, stale
zero-step preservation, forceful resynchronization, final-scratch output-alias
rejection, and repeated late typed direct-local rollback while preserving the
last successful final SoA bits and storage identity.

The final force scratch is derived, non-authoritative state. It is neither
serialized in the checkpoint nor included in the static fingerprint. The
three channel resizes occur after parent pre-scan but before the force
calculation is committed to authoritative dynamics state. This evidence does
not claim address, size, content, or storage-identity retention if a resize or
allocation throws. It also makes no unconditional, upstream, universal, or
all-failure-path scratch-retention claim.

The immediate architecture predecessor is PR #451: reviewed head
`b09f1dd125e1bb6aaf255cc2f3fb737ca4d9f475`, squash merge
`0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a`, tree
`124539c1d14f5cbc0f3d91d231d6a40736f58f5a`, profile SHA-256
`50c50ba44f9d3ff32358454d0d9f81f2619265fdaa5a3e9fe9194f22848685b7`,
and 232-entry manifest SHA-256
`348ab691558af31b398c653d0c6399bc30c651bc7cc911edb35aedcda2ec9032`.
The particle-mesh target predecessor is PR #450: reviewed head
`b0e26a8b2eea995a6038a484894808387486ff9e`, squash merge
`75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330`, tree
`03ccd07339b71eafa435a9b2012d2ab6a863d4d9`, profile SHA-256
`cc7c92719b832c847f213ea02b9a46e75bfd7e79b291c28af59b24f5b0478d3f`,
and 226-entry manifest SHA-256
`c19ec3eb610bc07978b7cb96b0368043f9084a91d344c8515fa75140bb27c7f6`.
The inherited final-SoA predecessor is PR #445: reviewed head
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

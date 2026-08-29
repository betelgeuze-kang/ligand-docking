# Engine V2 direct-Ewald composite-dynamics combined-force SoA v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGDEC001` 104-byte checkpoint header. On a successful
force-producing stateful call, the direct-Ewald composite evaluator records
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
direct-Ewald, and combined component. A late typed direct-Ewald failure
therefore returns before final SoA recording. Runtime regression covers both
explicit CPU lanes, reserved pointer/capacity/size retention across successful
forceful calls, same-lane peer and stateless AoS bit identity, create and
zero-step stability, checkpoint A to state B followed by loading A, stale
zero-step preservation, forceful resynchronization, final-scratch output-alias
rejection, and repeated late typed direct-Ewald rollback while preserving the
last successful final SoA bits and storage identity.

The final force scratch is derived, non-authoritative state. It is neither
serialized in the checkpoint nor included in the static fingerprint. The
three channel resizes occur after parent pre-scan but before the force
calculation is committed to authoritative dynamics state. This evidence does
not claim address, size, content, or storage-identity retention if a resize or
allocation throws. It also makes no unconditional, upstream, universal, or
all-failure-path scratch-retention claim.

The immediate architecture predecessor is PR #450: reviewed head
`b0e26a8b2eea995a6038a484894808387486ff9e`, squash merge
`75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330`, tree
`03ccd07339b71eafa435a9b2012d2ab6a863d4d9`, profile SHA-256
`cc7c92719b832c847f213ea02b9a46e75bfd7e79b291c28af59b24f5b0478d3f`,
and 226-entry manifest SHA-256
`c19ec3eb610bc07978b7cb96b0368043f9084a91d344c8515fa75140bb27c7f6`.
The direct target predecessor is PR #449: reviewed head
`0268e1731eb5f8b472cb527ac277a66c7ce4317f`, squash merge
`11ee408d89c44e70188af5133544ecebd604b182`, tree
`01d37e1adf097384c1e895fa637af0cfff45f4e8`, profile SHA-256
`745a4413cc875f143be460f372ad4ddc809af0588df65e736d68361fce418485`,
and 220-entry manifest SHA-256
`38d48a481963dc5a4a6202f6b6f794e9984e64ea43bb2ebd11a3aeb7e7815a1f`.
The inherited final-SoA predecessor is PR #446: reviewed head
`5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7`, squash merge
`29edcd1ea18e9fb64b9d416a0d05d87e0485be4b`, tree
`77f5298c291130f7ea86b96bd13b6bd9596f6850`, profile SHA-256
`2c1a5c015cd4db903e359e6d18fb52ee70c583e1c2744409754b44352d201985`,
and 202-entry manifest SHA-256
`f1c41ad4ad774bd2d7ab1672df61792ad539f0c2c199b37511ed0f5783412467`.

This slice makes no allocation-free, timing, performance, acceleration,
cross-lane bit-parity, product, or scientific claim. All authority remains
false. The four operational blockers and 32 unresolved decisions remain
controlling. CI is synthetic CPU-only and performs no qualification,
HIP-device, molecular, benchmark, supervisor, or reservation execution.

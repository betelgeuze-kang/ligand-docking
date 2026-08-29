# Engine V2 direct-Ewald composite-dynamics short-system scratch v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGDEC001` 104-byte checkpoint header. It gives each
direct-Ewald composite-dynamics owner private short-system scratch storage.
The explicit C++ CPU-reference and Rust CPU lanes refresh the three position
channels in place before short-range evaluation while retaining the stateless
API's local-copy path.

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
repeated late direct-Ewald failure. A late failure may refresh non-authoritative
scratch contents, but authoritative particles, reports, checkpoints, and
scratch storage identity remain transactional.

The immutable predecessor is PR #446: reviewed head
`5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7`, squash merge
`29edcd1ea18e9fb64b9d416a0d05d87e0485be4b`, tree
`77f5298c291130f7ea86b96bd13b6bd9596f6850`, profile SHA-256
`2c1a5c015cd4db903e359e6d18fb52ee70c583e1c2744409754b44352d201985`,
and 202-entry manifest SHA-256
`f1c41ad4ad774bd2d7ab1672df61792ad539f0c2c199b37511ed0f5783412467`.
The direct-Ewald backend-preflight architecture remains frozen at PR #443:
reviewed head `b785fd793c421c27730516453559a27b9cee6427`, squash
merge `5c532668f9ed95b1159b899acf726eef8824b288`, tree
`515d0ea740426d6267a5b521acc451ea1492f282`, profile SHA-256
`8ae38af90175e1e62eb54abb6727963a4439ece0fc4b622a4b0f4c9593c1a97f`,
and 120-entry manifest SHA-256
`1aed00454380e70338428b11e347b7d47f28b2b5f46e5e843612dca0ac361432`.

This slice makes no allocation-free, timing, performance, acceleration,
cross-lane bit-parity, product, or scientific claim. All authority remains
false. The four operational blockers and 32 unresolved decisions remain
controlling. CI is synthetic CPU-only and performs no qualification,
HIP-device, molecular, benchmark, supervisor, or reservation execution.

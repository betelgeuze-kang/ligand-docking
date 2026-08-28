# Engine V2 direct-Ewald composite-dynamics force scratch v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGDEC001` 104-byte checkpoint header. It changes only the
explicit C++ CPU-reference and Rust CPU integration lanes so their final SoA
force output uses owner-persistent scratch storage instead of creating a fresh
force-output allocation for every provider evaluation.

The simulation owner retains exclusive ownership of the storage. Failed force
evaluation and integration remain whole-call transactional, checkpoint bytes
do not include scratch capacity or contents, and checkpoint load cannot publish
scratch state. This slice claims neither allocation-free execution nor timing,
performance, acceleration, cross-lane bit parity, or scientific improvement.

The immutable slice predecessor is PR #445: reviewed head
`801a85d56846c464b3a618ecacca867cd12a8c9f`, squash merge
`c53f7993ec06c4ac04a4907b40f179d12fbe309a`, tree
`2bb25b756b802671bcfc5f3ac95b26df3b284956`, profile SHA-256
`32129a32d0b351ac265fda21906e707cc708c664241715b4d0d92fa3cc013b62`,
and 194-entry manifest SHA-256
`d428b3f18d26382fbb7e5e8a48f3a114eb953b8708bec77c4f00ec6c0d1bcc3f`.
The direct-Ewald backend-preflight architecture remains frozen at PR #443:
reviewed head `b785fd793c421c27730516453559a27b9cee6427`, squash
merge `5c532668f9ed95b1159b899acf726eef8824b288`, tree
`515d0ea740426d6267a5b521acc451ea1492f282`, profile SHA-256
`8ae38af90175e1e62eb54abb6727963a4439ece0fc4b622a4b0f4c9593c1a97f`,
and 120-entry manifest SHA-256
`1aed00454380e70338428b11e347b7d47f28b2b5f46e5e843612dca0ac361432`.

All authority remains false. The four operational blockers and 32 unresolved
decisions remain controlling. CI is synthetic CPU-only and performs no
qualification, HIP-device, molecular, benchmark, supervisor, or reservation
execution.

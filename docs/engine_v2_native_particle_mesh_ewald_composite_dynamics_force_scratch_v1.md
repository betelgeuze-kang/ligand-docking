# Engine V2 PME composite-dynamics force scratch v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGPME001` 104-byte checkpoint header. It changes only the
explicit C++ CPU-reference and Rust CPU integration lanes so their final SoA
force output uses owner-persistent scratch storage instead of creating a fresh
force-output allocation for every provider evaluation.

The simulation owner retains exclusive ownership of the storage. Failed force
evaluation and integration remain whole-call transactional, checkpoint bytes
do not include scratch capacity or contents, and checkpoint load cannot publish
scratch state. This slice claims neither allocation-free execution nor timing,
performance, acceleration, cross-lane bit parity, or scientific improvement.

The immutable predecessor is PR #444: reviewed head
`84dcdf4759e1d182d52502f157a2d551bfad68a4`, squash merge
`6499ef99ed5b7b3a374b9f4ab15bc43057f44cf3`, tree
`531399ae05897624439f561402b7d51d76a21cad`, profile SHA-256
`acca244232d196701044fd9ecbf6a2abce91cd03be966ead875c61cf42f75bab`,
and 186-entry manifest SHA-256
`030264269b2c438c11013c1e5a62e8c9745abcdf8567771ce990cf2f33e14f78`.

All authority remains false. The four operational blockers and 32 unresolved
decisions remain controlling. CI is synthetic CPU-only and performs no
qualification, HIP-device, molecular, benchmark, supervisor, or reservation
execution.

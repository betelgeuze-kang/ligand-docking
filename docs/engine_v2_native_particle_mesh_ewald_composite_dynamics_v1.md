# Engine V2 particle-mesh-Ewald composite dynamics v1

This bounded successor adds a separate 13-symbol stateful ABI for synthetic
particle-mesh-Ewald composite dynamics. It deep-owns the model and reuses the
shared integrator and whole-call transactional rollback path. Only explicit
C++ CPU reference and Rust CPU lanes are accepted; AUTO and HIP requests are
rejected without fallback.

The canonical checkpoint has magic `BGPME001` and a 104-byte header. Its
fingerprint normalizes direct reciprocal bounds that are ignored by the
particle-mesh evaluator. Checkpoints are exact within the same lane only; this
evidence makes no cross-lane bit-parity claim. Failed integration or checkpoint
load leaves all state and caller reports unchanged.

The immediate immutable parents are PR #442 (merge `5f6f4e2642dbe5c1272b2a9710288db25db5164f`,
tree `95f3d64a553f6c261d59a7ef8bd202561d51c45a`, reviewed head
`8ce40276b58098186edc0dbde426c9b3be12f010`) and PR #443 (merge
`5c532668f9ed95b1159b899acf726eef8824b288`, tree
`515d0ea740426d6267a5b521acc451ea1492f282`, reviewed head
`b785fd793c421c27730516453559a27b9cee6427`). Standalone verification requires
the merge objects and exact trees. Reviewed heads are optional locally and are
checked only when present, with lazy fetching disabled; CI explicitly fetches
and checks both.

Run `python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py`.
Only intentional evidence regeneration uses `--refresh`.

All authority remains false. The four reservation/operational blockers and 32
unresolved decisions remain controlling. This synthetic CPU evidence performs
no qualification, HIP device, molecular, reservation, supervisor, or public
benchmark execution and grants no scientific, performance, acceleration, or
product claim.

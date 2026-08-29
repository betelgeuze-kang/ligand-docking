# Engine V2 direct-Ewald composite-dynamics short-parent force scratch v1

This bounded successor preserves the frozen 1.0 stateful ABI, its exact 13
symbols, and the `BGDEC001` 104-byte checkpoint header. Each direct-Ewald
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

Repeated late downstream direct-Ewald failures preserve authoritative
rollback and the short-parent force-vector storage identity. Such failures may
mutate derived scratch contents or cache state; this evidence does not claim
unconditional retention for upstream failures or for every failure path.

The immediate architecture predecessor is PR #448: reviewed head
`4ace5d02dd90618140baecfeba28fdf93f3b342f`, squash merge
`5d4a55c85a80b62d38e79ea608e4850a6966ceeb`, tree
`1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73`, profile SHA-256
`72982489ea675272607013d9495f36ea5f649eb94f57d35e6a37a9e8ebfef476`,
and 214-entry manifest SHA-256
`691792ba1f59fb314bd7c4dc8b6ae746f25629a840b9e64da6b3f54eba561028`.
The direct target predecessor is PR #447: reviewed head
`5d4d238a2eea2765b6ac5d5d3f596487bd5b8cd6`, squash merge
`3f68361985e57f4c5ee547ba690f4a6859bd8b34`, tree
`1fc25fdc53ae1d2303a6fe6abe279e520fc13f12`, profile SHA-256
`8be1f7d28f936f78486bfabaf9fdfc2e1e334285864138639c796d36a454d3cb`,
and 208-entry manifest SHA-256
`85c17310e995b8eb22028083694f710414e523884a0ae9834b5258dfcb6c48fd`.
Its inherited force-scratch predecessor is PR #446: reviewed head
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

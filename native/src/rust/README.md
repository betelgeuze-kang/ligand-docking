# Rust CPU provider

`rust_cpu` is a native, deterministic scalar execution backend. The kernel is
implemented in `rust/cpu-kernel` and linked behind the private versioned
provider ABI in `provider.h`; public callers continue to use the same opaque C
ABI as the C++ reference lane.

The provider is not an alias for `cpp_cpu_reference`. Both implementations run
the same synthetic fixtures independently, are bit-stable on repeated runs,
and must remain within the frozen cross-backend energy/force tolerance. This
backend is the host parity authority for the future `hip_safe` implementation,
but does not itself grant molecular execution or product-claim authority.

The same provider now owns the persistent Engine V2 ScorerV1 context behind
the public ABI 1.5 fixed64 boundary. Receptor/ligand parameters and reference
geometry are deep-copied once; every score call retains exactly 64 rows and
returns all eight weighted terms, total score, pair/contact counts, and typed
candidate-local failures transactionally. The implementation calls the same
Rust ScorerV1 kernel used by the higher-level native receipt core rather than a
second scoring formula.

ABI 1.6 also routes fixed64 pose validity through a persistent Rust context.
The private provider calls the reusable canonical Rust validity kernel and
returns the complete check mask, blocker mask, 22 measurements, and typed
failure evidence without dropping any slot or relabeling another backend.

ABI 1.7 routes stable Top-K through the reusable fixed-width Rust ranking
kernel as well. The private provider revalidates scorer/validity binding and
coordinate identities, returns both complete ordering arrays transactionally,
and keeps all product authority flags false.

ABI 1.8 routes direct-coordinate fixed64 RMSD clustering through the reusable
Rust clustering kernel. The provider accepts only the complete stable-valid
ordering, retains every failed slot, uses deterministic first-representative
assignment with an inclusive threshold, and returns the same immutable rows
as the independent C++ and HIP implementations.

ABI 1.11 composes the existing Rust scorer, validity, and ranking providers
behind the shared persistent fixed64 downstream handle. The C++ orchestration
layer derives failure and coordinate-identity channels once and commits the
three Rust outputs transactionally; it does not reimplement any Rust
scientific kernel or allow a Python/product fallback.

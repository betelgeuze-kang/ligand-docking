# Native docking kernel boundary

ABI 1.5 introduces a persistent Engine V2 ScorerV1 handle shared by the
qualification C++ lane and the product Rust CPU lane. Its frozen batch contract
is candidate-major float64 SoA with exactly 64 slots. Inactive upstream rows are
not deleted; they return `UPSTREAM_NOT_ADMITTED`, so denominator and failure
accounting remain intact.

ABI 1.6 adds the matching persistent pose-validity handle. Its fixed64 input
binds each evaluated coordinate row to explicit `(x,y,z,w)` rotation evidence
and retains exact upstream ScorerV1 failure codes for inactive rows. The
output preserves all eight frozen checks and all 22 measurements; capacity or
non-finite failures stay candidate-local and transactional. The qualification
C++ implementation and product Rust CPU implementation are independent but
share the public numerical contract. HIP lanes remain fail-closed until their
dedicated device providers are compiled; both now contain deterministic
fixed64 validity kernels and expose parity tests when a qualified device is
available.

ABI 1.7 adds the persistent stable Top-K handle. It consumes the complete
ScorerV1 and pose-validity rows plus 64 coordinate SHA-256 identities, derives
the primary score order and the validity-filtered order with a bounded
allocation-free insertion sort, and returns explicit rank-zero sentinels for
ineligible rows. C++, Rust, `hip_safe`, and `hip_fast` share the frozen
score-then-slot ordering and never authorize automatic product-rank changes,
customer pose emission, or production claims.

ABI 1.8 extends that same backend-bound handle with fixed64 direct-coordinate
RMSD clustering. Valid candidates are traversed in stable-valid-rank order;
the first representative within the inclusive threshold wins, and the first
five representatives form the cluster Top-K. The v1 contract performs no
alignment or symmetry permutation. C++, Rust, `hip_safe`, and `hip_fast`
preserve all 64 rows, coordinate identities, typed upstream ineligibility, and
false product-authority flags transactionally.

ABI 1.11 adds one persistent downstream handle that owns ScorerV1,
pose-validity, and stable Top-K providers on a single explicit backend/device.
Creation rejects receptor, ligand, pocket, exclusion, or receipt-identity
cross-wiring before the handle is returned. A run derives scorer-to-validity
failure bindings and the canonical Rust-compatible coordinate SHA-256 values
internally, keeps all 64 rows, and commits score, validity, and ranking outputs
as one transaction. `cpp_cpu_reference`, `rust_cpu`, `hip_safe`, and
`hip_fast` execute the same composition without fallback; the pipeline still
grants no molecular-execution or product authority.

Scorer capacity, degenerate-rotor, and non-finite failures retain the pair
counts observed before failure. Downstream validity binds those rows as typed
upstream failures, and Top-K accepts the pair-count receipt while requiring
zero score/contact evidence and keeping the slot rank-ineligible.

ABI 1.12 adds the persistent fixed64 refinement pipeline. It owns the existing
V2/V3/V6 rigid, V7 torsion, and ABI 1.11 downstream handles on one exact
backend/device. V7 baselines and accepted-step evidence are derived from the
rigid result, final quaternions include the accepted rigid rotation, and V2/V3
rows bypass V7 without bypassing the fixed denominator. All component outputs
and the final coordinate-selection rows commit together after complete
validation. Cross-wired receptor, ligand-radius, or pocket contexts fail at
creation; overlapping buffers fail before work. The 64 rows retain the exact
failure stage and coordinate origin, while execution, reservation, benchmark,
rank-mutation, pose-emission, and claim authority remain false.

The term order is:

1. typed van der Waals
2. electrostatics
3. directional hydrogen bond
4. hydrophobic contact
5. desolvation proxy
6. torsion energy
7. ligand strain
8. weak pocket prior

Context creation deep-copies the receptor, ligand reference geometry, typed
atom parameters, donors, exclusions, rotors, configuration, and four evidence
identity digests. A batch writes no scientific output until all descriptor and
backend checks succeed. Candidate-local geometry/capacity failures are rows,
not batch aborts.

`cpp_cpu_reference` independently reimplements the frozen formula for
qualification only. `rust_cpu` calls the canonical Rust ScorerV1 core through a
private versioned provider. Synthetic parity requires equal status, failure,
pair/contact counts, and tight binary64 term/total agreement; repeated runs
require bit-identical rows.

`hip_safe` and `hip_fast` instantiate the frozen device formula as separately
compiled providers with separate symbols and persistent receptor/ligand device
state; neither lane calls or relabels the other. Each fixed64 kernel uses one
serial thread per candidate. `hip_safe` is available only in an exact ROCm
6.0.2 build with an explicitly qualified architecture and a compatible runtime
device. `hip_fast` uses the explicit native HIP build and remains on strict
math flags until safe parity is qualified; performance math must be enabled by
a later, separately reviewed profile.

The device suite compares every typed failure/count exactly, uses a frozen
binary64 tolerance for score terms, and requires bit-identical same-device
repeats. No backend fallback, performance claim, execution authority, or
product authority is created here.

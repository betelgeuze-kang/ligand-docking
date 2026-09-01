# Engine V2 native PME Rust reciprocal rollback output force-storage binding v1

## Scope

This bounded successor changes only the private C++ output binding held by
`EvaluationForceStorageRollback` in the native particle-mesh reciprocal Rust
adapter. In the exact PR 482 predecessor, the guard already retained the local
candidate as `EvaluationForceStorage &candidate_forces_`, but it still retained
the caller's whole evaluation through `Evaluation *output_` even though rollback
reads and writes only `output_->forces`.

The inherited `using EvaluationForceStorage = decltype(Evaluation::forces)`
alias and no-throw swap assertion remain exact. The successor replaces the whole
output pointer with nullable `EvaluationForceStorage *output_forces_`; constructor
and destructor swaps directly dereference that pointer. The unchanged candidate
binding remains `EvaluationForceStorage &candidate_forces_`.

The construction site passes `&out_evaluation->forces` only under
`compute_forces && reuse_force_storage && out_evaluation != nullptr`. C++
conditional evaluation therefore short-circuits before the address is formed
when the provider-force-source route supplies a null evaluation output. The
output force-storage pointer is the sole activation and commit sentinel, and
`commit()` disarms it by setting only `output_forces_` to null. The guard's retained state is force-storage-only.

This lexical pointer/reference narrowing does not provide runtime lifetime enforcement
or establish an object-layout or performance result.

No public header, Rust provider, provider ABI, linked symbol, checkpoint,
production caller, or native fake-provider test changes in this slice.

## Exact transform and route truth table

The verifier reconstructs each complete successor adapter from the exact PR
482 adapter with exactly two replacements: the rollback class and the guard
construction call site. Both
canonical and vendored adapters must equal that reconstruction byte for byte
and remain byte-identical.

The construction-site predicate activates rollback only for force-producing
reusable non-null evaluation output. Its five inherited semantic routes remain:

| Route | Forces | Reuse | Evaluation output | Rollback active |
|---|---:|---:|---:|---:|
| Stateless energy | no | no | yes | no |
| Stateless force | yes | no | yes | no |
| Reusable energy | no | yes | yes | no |
| Reusable force | yes | yes | yes | yes |
| Provider-force source | yes | yes | no | no |

When active, construction swaps the caller force storage into the local
candidate and destruction restores it on every failure return. `commit()` runs
only after provider status, typed-error, energy, and force validation succeed;
it still disarms rollback only by setting `output_forces_` to `nullptr`. The dispatch
normalization, two provider symbols, force-descriptor branch locality, scratch
ownership, validation, and success-only external commit remain exact PR 482
behavior. Thus, initial swap, failure rollback, and success-only commit behavior are preserved.

The unchanged fake-provider transactionality test still covers all five route classes,
reusable-force typed failure, non-finite success, exact energy bits, and force
address/capacity/size/bit preservation. It is an adapter test double with
neither production nor scientific authority.

## Evidence graph

The predecessor is frozen to PR 482:

- reviewed head: `3f8e3f2acfdd3cbc3514feffa17e2e74e300598c`;
- merge commit: `8decdf9ca7129bb5669d5217e611f52860ac779c`;
- merge tree: `44e57663a0243d16b4805fe97c5655ee028f8c84`;
- predecessor workflow SHA-256: `59ad45c19d6c812832d91d23e42761c53fe2eafe86c674875edcb792a06f9ab2`;
- predecessor profile SHA-256: `c130a1fb649972ff9d762a7d23c9c0e9599380b626681295b1cd691cc7f595a3`;
- predecessor source-manifest SHA-256: `42ac3a4ac8c9f9cc726ad58be2ef65f6d0e288273750f1d67d22ac4d938bf125`;
- predecessor documentation SHA-256: `ff0f0457bb490c6a5ede86d6edd7571b5e7d0bcb7e6f0065de4101b5f529d08f`;
- predecessor unit SHA-256: `9ed7fceba4fc61c2b63e6a39e0ae1b07f9ec301d80cbdeb58c0733cea9ea8d6b`;
- predecessor verifier SHA-256: `c8536d6cb9b33c265ad450436b68757de0093f5cf7e9acef645ef68d66017847`;
- predecessor adapter SHA-256: `70ad84edb0a4458a5971e4e23aff6625908faa6f7eda21133fa7a47f6722aa2a`;
- predecessor fake-provider transactionality test SHA-256: `4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03`;
- predecessor source manifest: 423 sorted unique paths.

The successor delta has ten paths: two mirrored adapter files, six successor
evidence files, and the predecessor workflow/unit freeze wiring. The successor
source manifest has 429 sorted unique paths. Both predecessor and successor
workflows carry 246 unique symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 482 merge object and runs its
frozen profile, manifest, verifier, and seven-test unit before restoring the
current checkout. Its frozen unit skips locally only when this successor
profile exists. Release and sanitizer jobs exercise the inherited native
reciprocal, PME, composite, composite-dynamics, and fake-provider
transactionality tests. Rust-boundary and export jobs remain unchanged.

## Authority boundary

This is private C++ type-state and ownership hardening only. It makes no performance, allocation, object-size, stack-size, acceleration, scientific,
molecular, HIP, product, or operational claim.

Operational authority remains false. The four blockers remain:

- `external_reservation_endpoint_not_configured`;
- `external_reservation_provider_not_operational`;
- `external_reservation_trust_anchor_not_configured`;
- `historical_execution_operational_authority_false`.

There are 32 unresolved operational decisions. Reservation, molecular A/B,
Fresh-128, public benchmark, D1/D2, Stage0, qualification rerun, real molecular
execution, HIP-device execution, root-supervisor installation, and product
authorization remain closed.

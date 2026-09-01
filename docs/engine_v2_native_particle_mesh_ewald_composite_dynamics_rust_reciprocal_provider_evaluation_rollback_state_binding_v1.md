# Engine V2 native PME Rust reciprocal evaluation rollback-state binding v1

## Scope

This bounded successor changes only the private C++
`EvaluationForceStorageRollback` state binding in the native particle-mesh
reciprocal Rust adapter. In the exact PR 480 predecessor, the always-live local
`Evaluation candidate` was passed and retained through nullable pointers while
a separate `bool enabled` controlled whether `output_` became active.

The successor binds the candidate as `Evaluation &candidate_` and
removes the redundant `enabled` constructor parameter. The construction site passes either
`out_evaluation` or `nullptr`. The nullable `Evaluation *output_` is
therefore the sole inactive, active, and committed sentinel. The local
`candidate` is declared before the guard and outlives it. A C++ reference strengthens
nullability at this lexical boundary; it does not provide runtime lifetime enforcement
or prove a different object layout.

No public header, Rust provider, provider ABI, linked symbol, checkpoint,
production caller, or native fake-provider test changes in this slice.

## Exact transform and route truth table

The verifier reconstructs each complete successor adapter from the exact PR
480 adapter by replacing only the rollback class and its construction block.
Both canonical and vendored adapters must equal that reconstruction byte for
byte and remain byte-identical.

The construction-site conditional activates rollback only for force-producing
reusable evaluation output. Its five inherited semantic routes remain:

| Route | Forces | Reuse | Evaluation output | Rollback active |
|---|---:|---:|---:|---:|
| Stateless energy | no | no | yes | no |
| Stateless force | yes | no | yes | no |
| Reusable energy | no | yes | yes | no |
| Reusable force | yes | yes | yes | yes |
| Provider-force source | yes | yes | no | no |

When active, construction still swaps the caller force storage into the local
candidate and destruction restores it on every failure return. `commit()`
still runs only after provider status, typed-error, energy, and force
validation succeed; it now disarms rollback only by setting `output_` to
`nullptr`. The no-throw move/swap/copy assertions, dispatch normalization,
two provider symbols, force-descriptor branch locality, scratch ownership,
validation, and success-only external commit remain exact PR 480 behavior.
Thus, initial swap, failure rollback, and success-only commit behavior are preserved.

The unchanged fake-provider transactionality test still covers all five route classes,
reusable-force typed failure, non-finite success, exact energy bits,
and force address/capacity/size/bit preservation. It is an adapter test double
with neither production nor scientific authority.

## Evidence graph

The predecessor is frozen to PR 480:

- reviewed head: `9b5277aae0ba1335de04b37ad76b9b9e66db26df`;
- merge commit: `3b301c25c019e132c8dabba10894d09d5ef25e98`;
- merge tree: `eacae3fe0453ccb1c8769d8e1753e3f22cd5ccca`;
- predecessor profile SHA-256: `2615595c125f47b6704fbdabc2e11002a9a11d8cf25d3aacdb327ecc9f103a8c`;
- predecessor source-manifest SHA-256: `b8bf14bfc7b81cceae99e984cab8e140d201f14666a49401d27b348c55c7e10b`;
- predecessor source manifest: 411 sorted unique paths.

The successor delta has ten paths: two mirrored adapter files, six successor
evidence files, and the predecessor workflow/unit freeze wiring. The successor
source manifest has 417 sorted unique paths. Both predecessor and successor
workflows carry 234 unique symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 480 merge object and runs its
frozen verifier and unit before restoring the current checkout. Its frozen
unit skips locally only when this successor profile exists. Release and
sanitizer jobs exercise the inherited native reciprocal, PME, composite,
composite-dynamics, and fake-provider transactionality tests. Rust-boundary
and export jobs remain unchanged.

## Authority boundary

This is private C++ type-state and ownership hardening only. It makes
no performance, allocation, object-size, stack-size, acceleration, scientific,
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

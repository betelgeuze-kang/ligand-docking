# Engine V2 native PME Rust reciprocal rollback force-storage binding v1

## Scope

This bounded successor changes only the private C++ force-storage reference held
by `EvaluationForceStorageRollback` in the native particle-mesh reciprocal Rust
adapter. In the exact PR 481 predecessor, the guard retained the whole local
candidate through `Evaluation &candidate_`, even though rollback reads and
writes only its `forces` member.

The successor introduces
`using EvaluationForceStorage = decltype(Evaluation::forces)` and binds the
existing no-throw swap assertion to that alias. The guard now retains
`EvaluationForceStorage &candidate_forces_`, and its construction site passes `candidate.forces`.
The whole-candidate reference parameter, member, member
accesses, and call-site argument are absent.

The local `candidate` is declared before the guard and outlives the force-storage reference.
This lexical reference binding does not provide runtime lifetime enforcement or
prove a different object layout. `Evaluation *output_` remains the sole activation and commit sentinel,
so this evidence does not claim that the entire guard is force-storage-only.

No public header, Rust provider, provider ABI, linked symbol, checkpoint,
production caller, or native fake-provider test changes in this slice.

## Exact transform and route truth table

The verifier reconstructs each complete successor adapter from the exact PR
481 adapter with exactly three replacements: the force-storage type binding and
assertion, the rollback class, and the guard construction call site. Both
canonical and vendored adapters must equal that reconstruction byte for byte
and remain byte-identical.

The existing construction-site predicate activates rollback only for
force-producing reusable evaluation output. Its five inherited semantic routes remain:

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
it still disarms rollback only by setting `output_` to `nullptr`. The dispatch
normalization, two provider symbols, force-descriptor branch locality, scratch
ownership, validation, and success-only external commit remain exact PR 481
behavior. Thus, initial swap, failure rollback, and success-only commit behavior are preserved.

The unchanged fake-provider transactionality test still covers all five route classes,
reusable-force typed failure, non-finite success, exact energy bits, and force
address/capacity/size/bit preservation. It is an adapter test double with
neither production nor scientific authority.

## Evidence graph

The predecessor is frozen to PR 481:

- reviewed head: `bae72aefcf609029c45211ecaa28de7d86d8bd4d`;
- merge commit: `214f11daf45997826f142544bb02dc6c7831b8ee`;
- merge tree: `d8360b665efa6c6292ea7a690a3839f6200e2396`;
- predecessor workflow SHA-256: `00fa7314666d4c242de0e604b0ce22e17a1ad5466a107a49a128bcc0beedd87f`;
- predecessor profile SHA-256: `6ca14b72687d4ddb6b80cf70f7ff012e4384ba9cb708a77c1b6673156ad71460`;
- predecessor source-manifest SHA-256: `2e22e52cf8745fe2ab48de47bb4e5073a4fe80c05d311543fbec29b75a5fbbb8`;
- predecessor documentation SHA-256: `3504369ca0dbcad135d9c2b1cc1a00feaab81ceb7f0fc5f379f0e7d30068ce0d`;
- predecessor unit SHA-256: `852f52a2a8e2323805587be24c91a88827897488738e4995dc8bb6bfc12ebda8`;
- predecessor verifier SHA-256: `e4c9b688e596f84694a44b76037380a93a179855aeaa7f4cad3673d91d2b2b5c`;
- predecessor adapter SHA-256: `3ac73fad9bc7c4852d640d6ef6c690fdf6490f961c16fcb4ff50e2e90b3d5941`;
- predecessor fake-provider transactionality test SHA-256: `4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03`;
- predecessor source manifest: 417 sorted unique paths.

The successor delta has ten paths: two mirrored adapter files, six successor
evidence files, and the predecessor workflow/unit freeze wiring. The successor
source manifest has 423 sorted unique paths. Both predecessor and successor
workflows carry 240 unique symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 481 merge object and runs its
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

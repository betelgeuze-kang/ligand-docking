# Engine V2 native PME Rust-provider dispatch-status single assignment v1

## Scope

This is a bounded C++ type-state refactor in the private native particle-mesh reciprocal Rust adapter. The exact PR 478 predecessor declared `raw_status` without an initializer, assigned it in the force and energy branches, and consumed the common result after dispatch.

The successor initializes `const std::int32_t raw_status` exactly once from a capture-by-reference lambda with an explicit `std::int32_t` return type. The lambda is immediately invoked. Its force path returns the force-provider status and its fallthrough energy path returns the energy-provider status. There are zero uninitialized `raw_status` declarations and zero branch assignments to `raw_status`.

No public header, Rust provider, private provider ABI, linked symbol, checkpoint format, caller, or native fake-provider test changes in this slice.

## Exact transform and preserved boundaries

The verifier reconstructs each complete successor adapter from the frozen PR 478 adapter by replacing exactly one dispatch region with the exact IIFE region. Both canonical and vendored adapters must equal that reconstruction byte for byte and must remain byte-identical to one another.

Inside the new dispatch region:

- one explicit-return-type IIFE initializes the one const status;
- one `if (compute_forces)` selects the force return;
- the energy-provider call is the fallthrough return, with no `else` and no status assignment;
- the force descriptor remains local to the force branch, and the energy branch has no `provider_forces` reference;
- the common `provider_error` descriptor remains outside and before dispatch;
- the two existing private provider symbols and their arguments remain the only provider calls.

The common `provider_error` descriptor setup is exact predecessor material before the transformed region. The post-dispatch status normalization, validation, rollback, and commit remain exact PR 478 bytes after it. This is source and control-flow evidence only; it does not claim compiler optimization, generated-code identity, stack reduction, allocation reduction, or runtime improvement.

## Evidence graph

The predecessor is frozen to PR 478:

- reviewed head: `c61fd0637c25cbb09c762f6ed5dea70814bf7145`;
- merge commit: `e02cb7721e50d35f0a8680cec12ac24801450bba`;
- merge tree: `6369559489af14a8bfe604ab6af2cdc9b298e722`;
- predecessor source manifest: 399 sorted unique paths.

The successor delta has ten paths: two mirrored adapter files, six successor evidence files, and the predecessor workflow/unit freeze wiring. The successor source manifest has 405 sorted unique paths. Both predecessor and successor workflows carry 222 unique symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 478 merge object and runs its frozen verifier and unit before restoring the current checkout. Its frozen unit skips locally only when this successor profile exists. The successor workflow checks the PR 478 merge/head/tree pins and verifies current evidence without detaching from the successor checkout.

Release and sanitizer jobs exercise the existing native reciprocal, PME, composite, composite-dynamics, and fake-provider transactionality tests. The Rust-boundary job runs the inherited Rust tests. Sanitizer evidence remains limited to native and fake-provider boundaries; the fake provider has neither production nor scientific authority.

## Authority boundary

Operational authority remains false. The four blockers remain:

- `external_reservation_endpoint_not_configured`;
- `external_reservation_provider_not_operational`;
- `external_reservation_trust_anchor_not_configured`;
- `historical_execution_operational_authority_false`.

There are 32 unresolved operational decisions. Reservation, molecular A/B, Fresh-128, public benchmark, D1/D2, Stage0, qualification rerun, real molecular execution, HIP device execution, root-supervisor installation, and product authorization remain closed. No performance, acceleration, scientific, molecular, HIP, product, or operational claim is made.

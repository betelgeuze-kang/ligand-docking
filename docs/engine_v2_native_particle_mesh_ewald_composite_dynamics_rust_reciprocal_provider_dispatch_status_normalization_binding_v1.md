# Engine V2 native PME Rust-provider dispatch-status normalization binding v1

## Scope

This is a bounded C++ type-state refactor in the private native particle-mesh reciprocal Rust adapter. The exact PR 479 predecessor initialized `const std::int32_t raw_status` from an explicit-return-type dispatch IIFE and then normalized that standalone binding in the next statement.

The successor initializes `const bg_status status` by passing the immediately invoked dispatch lambda as the direct argument to `normalize_provider_status`. The lambda keeps its explicit `std::int32_t` return type. There are zero standalone `raw_status` bindings, so unchecked provider status exists only inside the dispatch expression and the sole post-dispatch status binding is the normalized `bg_status`.

No public header, Rust provider, private provider ABI, linked symbol, checkpoint format, caller, or native fake-provider test changes in this slice.

## Exact transform and preserved boundaries

The verifier reconstructs each complete successor adapter from the frozen PR 479 adapter by replacing exactly the dispatch-status declaration plus its immediately following normalization statement with the direct normalization-boundary binding. Both canonical and vendored adapters must equal that reconstruction byte for byte and must remain byte-identical to one another.

Inside the transformed region:

- one `const bg_status status` directly binds the result of `normalize_provider_status`;
- the explicit `std::int32_t` return type remains on the capture-by-reference IIFE;
- one `if (compute_forces)` selects the force return and the fallthrough return selects energy;
- the force descriptor remains local to the force branch, while the energy branch has no `provider_forces` reference;
- the common `provider_error` descriptor remains outside and before dispatch;
- the two existing private provider symbols and their arguments remain the only provider calls.

The post-dispatch validation, rollback, and commit remain exact PR 479 bytes. This is source and control-flow evidence only; it does not claim compiler optimization, generated-code identity, lifetime-based runtime improvement, stack reduction, allocation reduction, or any performance change.

## Evidence graph

The predecessor is frozen to PR 479:

- reviewed head: `f62a5f68a59a94ffe0d2b20900e1f8c4d82b6eb8`;
- merge commit: `0f723b265c6366c0037d83d9ed9e934817fd9626`;
- merge tree: `619ad7bf2e6b74b80e6e7594b5b3c91f5e72b514`;
- predecessor profile SHA-256: `7d968b533127c959c8e76daf8641fef6e831a31804ed747b547890a85ab935cb`;
- predecessor source manifest SHA-256: `58f21f9c120dbc5b6062eaec7478d34ca5f59ddea6d2aea64b07cf9e93392820`;
- predecessor source manifest: 405 sorted unique paths.

The successor delta has ten paths: two mirrored adapter files, six successor evidence files, and the predecessor workflow/unit freeze wiring. The successor source manifest has 411 sorted unique paths. Both predecessor and successor workflows carry 228 unique symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 479 merge object and runs its frozen verifier and unit before restoring the current checkout. Its frozen unit skips locally only when this successor profile exists. The successor workflow checks the PR 479 merge/head/tree pins and verifies current evidence without detaching from the successor checkout.

Release and sanitizer jobs exercise the existing native reciprocal, PME, composite, composite-dynamics, and fake-provider transactionality tests. The Rust-boundary job runs the inherited Rust tests. Sanitizer evidence remains limited to native and fake-provider boundaries; the fake provider has neither production nor scientific authority.

## Authority boundary

Operational authority remains false. The four blockers remain:

- `external_reservation_endpoint_not_configured`;
- `external_reservation_provider_not_operational`;
- `external_reservation_trust_anchor_not_configured`;
- `historical_execution_operational_authority_false`.

There are 32 unresolved operational decisions. Reservation, molecular A/B, Fresh-128, public benchmark, D1/D2, Stage0, qualification rerun, real molecular execution, HIP device execution, root-supervisor installation, and product authorization remain closed. No performance, acceleration, scientific, molecular, HIP, product, or operational claim is made.

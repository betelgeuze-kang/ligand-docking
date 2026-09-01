# Engine V2 native PME Rust reciprocal error-output reference binding v1

## Scope

This bounded successor changes only error-output access inside the private C++
`evaluate_impl` function in the native particle-mesh reciprocal Rust adapter.
The exact PR 483 predecessor validates `Error *out_error` before initializing
and updating that object. The successor keeps the pointer parameter and null
check, then binds `Error &output_error = *out_error` immediately after the
validation and performs the existing initialization and eight member writes
through that non-null local reference.

The null/XOR output check remains before reference creation. The three public
wrappers retain their `Error *` signatures and pointer forwarding exactly. The
empty-system, capacity, count-mismatch, and provider typed-error mappings still
update the same caller-owned object. Unknown-provider diagnostics, status
normalization, and return values are unchanged.

This lexical binding does not provide runtime lifetime enforcement, remove the
public pointer boundary, or establish an object-layout or performance result.
No public header, Rust provider, provider ABI, linked symbol, checkpoint,
production caller, or native fake-provider test changes in this slice.

## Exact transform and inherited behavior

The verifier reconstructs both complete successor adapters from the exact PR
483 adapter. It replaces the single `*out_error = Error{};` statement with the
reference binding plus `output_error = Error{};`, then rewrites exactly eight
`out_error->` accesses as `output_error.` accesses. The canonical and vendored
adapters must equal that reconstruction byte for byte and remain byte-identical.

Everything outside those accesses remains exact predecessor bytes, including:

- all five semantic dispatch routes;
- provider-force scratch selection and ownership;
- `EvaluationForceStorageRollback` activation, restore, and commit behavior;
- status normalization and typed-error ordering;
- provider energy/force validation and success-only external commit;
- the three public wrapper bodies and pointer signatures.

The unchanged fake-provider transactionality test still covers all five route
classes, reusable-force typed failure, non-finite success, exact energy bits,
and force address/capacity/size/bit preservation. It remains a test double with
neither production nor scientific authority.

## Evidence graph

The predecessor is frozen to PR 483:

- reviewed head: `9138a05e9730b1892ee56a3133ffc48f8439ee92`;
- merge commit: `e51f10d6034bc9abf86017b879a5b777834cb3db`;
- merge tree: `9e9fc3099422870ddb03d5ff01874480ba9c71be`;
- predecessor workflow SHA-256: `7b3a6cce99090bef5276a825d431c476fa7f470b994950f41d15dc6ebcef2bbb`;
- predecessor profile SHA-256: `f9a3f0df78afe1207adef12c7b788b51cdf84e31aa378a7adbb54de4cc5b7ec9`;
- predecessor source-manifest SHA-256: `c0382ccb2d09fad33427bbe2d52cc7452a3bdea4aaddba1b17bae66eb0249479`;
- predecessor documentation SHA-256: `d61b954676e51822d9a6a9236725f90caa4e1a8c239e495a6589c117ed12cb93`;
- predecessor unit SHA-256: `326410fec9e978913a075e3ab35a4e5226138b4285f556e9198c9cd51dfaf8d2`;
- predecessor verifier SHA-256: `52261cae71e3bc9a193620c87682f3038ac4b2ed7ea8791554d3fe32719df69c`;
- predecessor adapter SHA-256: `4219d43bb2f74fc86d2dc10981966c74eb999f9a423cbd8dc696f78d36a89e17`;
- predecessor fake-provider transactionality test SHA-256: `4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03`;
- predecessor source manifest: 429 sorted unique paths.

The successor delta has ten paths: two mirrored adapters, six successor
evidence files, and predecessor workflow/unit freeze wiring. The successor
source manifest has 435 sorted unique paths. Both workflows carry 252 unique
symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 483 merge object and runs its
frozen profile, manifest, verifier, and seven-test unit before restoring the
current checkout. Its unit skips locally only when this successor profile is
present. Release, sanitizer, Rust-boundary, Linux-export, and macOS-export
checks retain their predecessor scope.

## Authority boundary

This is private C++ ownership-expression hardening only. It makes no
performance, allocation, object-size, stack-size, acceleration, scientific,
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

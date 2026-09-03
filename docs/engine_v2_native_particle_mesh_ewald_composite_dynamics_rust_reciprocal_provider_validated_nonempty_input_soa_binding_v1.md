# Engine V2 native PME Rust reciprocal validated non-empty input SoA binding v1

## Scope

This bounded successor changes only the four private C++ input-SoA pointer
bindings in the native particle-mesh reciprocal Rust adapter. The exact PR 484
predecessor first rejects `atom_count == 0U` and then rejects any
`position_y`, `position_z`, `charge`, or model count mismatch before creating
`provider_system`. At descriptor creation, `position_x` is therefore non-empty
and all four input channels have the same positive length.

The successor binds `provider_system.position_x`, `position_y`, `position_z`,
and `charge` directly to their respective `std::vector::data()` pointers. It
removes the now-unreachable `data_or_null` empty-vector branch and the unused
`<vector>` include. The four bindings preserve field order, channel identity,
and the addresses of the same caller-owned vector storage. The const input
system remains alive across descriptor construction, both provider-symbol
routes, validation, rollback, and success-only commit.

This adapter-local fact does not change the raw provider ABI: an independent
raw provider caller can still supply its existing zero-count descriptor
representation. It does not add runtime lifetime enforcement, change public or
private nullability contracts, establish object-layout equivalence, or claim a
performance result.

## Exact transform and inherited behavior

The verifier reconstructs both complete successor adapters from the exact PR
484 adapter. It removes exactly one `#include <vector>` line, removes the one
five-line `data_or_null` helper, and replaces exactly four helper calls with
direct `.data()` bindings. The canonical and vendored adapters must equal that
reconstruction byte for byte and remain byte-identical.

Everything outside those three lexical edits remains exact predecessor bytes,
including:

- null/XOR output validation and the inherited error-output reference binding;
- empty-system, capacity, and count-mismatch status/error mapping;
- provider descriptor metadata, ABI checks, and model conversion;
- both provider symbols and all five semantic dispatch routes;
- scratch selection, ownership, destruction, and output-force rollback;
- typed-error and finiteness validation plus success-only external commit;
- the three public wrapper bodies and pointer signatures.

The unchanged fake-provider transactionality test still covers all five route
classes, reusable-force typed failure, non-finite success, exact energy bits,
and force address/capacity/size/bit preservation. It remains a test double with
neither production nor scientific authority.

## Evidence graph

The predecessor is frozen to PR 484:

- reviewed head: `3b3a64c29c419c2e9c49a8f3f740c307201a684d`;
- merge commit: `57110c81ef1b65de034bb0a4d0fff70cb9a1445b`;
- merge tree: `30155bc6d8f13421157f926e8721dc1bdbc0f39c`;
- predecessor workflow SHA-256: `462de6202eaee8ffa5d3c31954d097ce0403d251612fd093063a8b2fa6159d08`;
- predecessor profile SHA-256: `1d8f56829c150e90ef4659b5bd3b4762829fb0a744d98c3dde841dc82f5e5fb0`;
- predecessor source-manifest SHA-256: `58c82873431f1bfb0cc0421a5d9d448f517442c7818622e64ef1a4c2c0135c5b`;
- predecessor documentation SHA-256: `f4013816d6d00f4098d3106f5527bb1b8cfc62d37e89a69a81485918656229c8`;
- predecessor unit SHA-256: `94d7061c106a9cd2be4cc06fe981a3a8bd00ed1ca6607632b245299dbdf647c6`;
- predecessor verifier SHA-256: `f00053cd0da2d8debd32d034f5c0d558dae645e105ae59624799d902b5364473`;
- predecessor adapter SHA-256: `41e772e5015a29c89fc99d34f13eb3c9352678c28f207a087949ef09ab9bbbfd`;
- successor adapter SHA-256: `5cd857c48bb7c3138f50d622772ae35bb0e79ccfd963bb8d12e2fac23761a201`;
- predecessor fake-provider transactionality test SHA-256: `4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03`;
- predecessor source manifest: 435 sorted unique paths.

The successor delta has ten paths: two mirrored adapters, six successor
evidence files, and predecessor workflow/unit freeze wiring. The successor
source manifest has 441 sorted unique paths. Both workflows carry 258 unique
symmetric pull-request and push trigger paths.

The predecessor workflow detaches the exact PR 484 merge object and runs its
frozen profile, manifest, verifier, and seven-test unit before restoring the
current checkout. Its unit skips locally only when this successor profile is
present. Release, sanitizer, Rust-boundary, Linux-export, and macOS-export
checks retain their predecessor scope.

## Descendant-stable source manifest

The 441-row manifest now distinguishes the frozen source snapshot from live
successor evidence. Non-evidence source rows are read from the exact post-PR
485 verifier-fix merge `234edea066fcba2b51fd4df8338b696d2febc66e`
and tree `ccd3792e60df668072e60ba454a4c9345616193a`. The current workflow, documentation, unit, and verifier remain live checkout inputs and continue to
be hashed from the current source tree.

This prevents unrelated descendant source changes from contaminating the
historical PR 485 source contract while retaining semantic checks against the
current canonical and vendored adapters. The manifest is a frozen source
snapshot with current evidence, not a claim that later descendants are byte
identical to PR 485.

## Authority boundary

This is private C++ descriptor-expression hardening only. It makes no
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

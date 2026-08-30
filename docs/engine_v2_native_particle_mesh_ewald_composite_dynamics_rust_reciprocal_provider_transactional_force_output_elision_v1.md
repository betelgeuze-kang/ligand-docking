# Engine V2 native PME Rust-adapter transactional force-output elision v1

## Scope

This bounded development slice changes only the non-reuse force-producing native Rust adapter path. That path now calls the existing hidden direct-force-output provider entry with call-local C++ SoA channels instead of asking the raw transactional provider to allocate an internal `ForceOutput` vector and then copy it into those channels.

The adapter still builds its final AoS `Evaluation` candidate and commits it only after provider status, typed-error, energy-finiteness, and force-finiteness checks succeed. A late direct-provider error may have written the disposable call-local C++ SoA, but it does not commit those writes to the caller's `Evaluation`.

## Dispatch boundary

The four native adapter routes remain distinct:

- the provider-force-source owner route uses the existing workspace, neutrality-sort, and particle-assignment triple-scratch entry;
- the reusable force-producing route uses the existing workspace entry;
- the non-reuse force-producing native Rust adapter uses the existing hidden direct-output entry;
- the energy-only route uses the public raw entry with force computation disabled.

The C++ evaluator lane remains provider-independent. The reusable owner routes, force-free route, input borrowing, status mapping, typed diagnostics, finite scans, checkpoint state, and final public commit boundary are not broadened by this slice.

## Unchanged Rust and ABI contract

The raw Rust transactional entry remains unchanged. Its transactional `ForceOutput` vector, allocation-failure diagnostic, and success-only raw energy/force commit behavior remain anchored by the exact PR #466 Rust source hash and the existing focused Rust kernel tests. The raw direct FFI force channels are not claimed to be transactional after a late scientific failure.

No Rust source, provider header, public header, status ABI, public symbol, private provider ABI version, checkpoint format, or static fingerprint changes. The public composite-dynamics surface remains the same 13 symbols, the private provider ABI remains version 1, and the checkpoint identity remains `BGPME001` with a 104-byte header. The existing direct-output symbol remains hidden.

## Test-double boundary

The standalone fake provider is only a route-selection and commit-separation test double. It checks the four adapter call branches, caller-local SoA late-error isolation, preservation of `Evaluation` pointer/capacity/size/bits, and C++ lane separation.

It does not execute the real Rust allocator, the production public C API, a Rust panic boundary, or molecular/scientific evaluation. It does not prove production or scientific transactionality. Its modeled raw transactional peer is not evidence that replaces the unchanged Rust source and focused Rust tests.

For the changed adapter contract, ASan/UBSan evidence is limited to the fake-provider adapter target. Inherited reciprocal and composite native sanitizer regressions also run, but the Rust provider itself is not sanitizer-instrumented and those runs do not establish real-Rust sanitizer coverage. The workflow configures a macOS engine/export boundary, but macOS and MSVC execution is not claimed by local evidence; only the CMake/MSVC source portability branch was reviewed.

## Allocation and claim boundary

The only allocation removed from this native route is the Rust provider's internal transactional force-vector allocation and its subsequent provider Vec-to-SoA copy. Call-local C++ x/y/z vectors, the final candidate AoS allocation, and the final SoA-to-AoS/public copy remain. Other reciprocal workspaces and owner scratch behavior remain inherited.

This is not a provider-wide, global, steady-state, or allocation-free claim. Allocation failure timing and detail invariance are not claimed. No performance, acceleration, scientific-equivalence, or product claim is authorized; peak-memory and cross-lane parity claims are also excluded.

## Evidence graph

The exact predecessor is PR #466: reviewed head `88f4ac017d33d188409486dacd8deda1c0f298c4`, merge `0da08391d0487300e1df00ace32bb2954b380f88`, and tree `6233b7c1ef87a108b49bc358ad5ed9f574d5832f`. The existing direct-output entry is anchored to PR #457.

The exact successor delta contains 12 paths: four implementation/test/CMake paths, six successor evidence paths, and two PR #466 workflow/unit freeze-wiring paths. The source manifest contains 333 entries and excludes its own profile and manifest. Pull-request and push triggers each contain the same 150 unique paths.

## Operational boundary

All operational and scientific authority remains false. The blockers remain:

- `external_reservation_endpoint_not_configured`
- `external_reservation_provider_not_operational`
- `external_reservation_trust_anchor_not_configured`
- `historical_execution_operational_authority_false`

The unresolved operational decisions remain 32. This evidence does not authorize reservation, molecular execution or A/B work, D1/D2, Stage0, Fresh-128, public benchmarking, HIP-device execution, qualification reruns, supervisor operations, or test-double production authority.

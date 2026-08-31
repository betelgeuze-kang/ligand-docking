# Engine V2 native PME Rust reciprocal-provider active scratch reference v1

This bounded successor changes only the native C++ adapter active
`ProviderForceScratch` binding and its member-access syntax. The external
`ProviderForceScratch *provider_force_scratch` parameter remains nullable at
the function boundary, and the existing reusable-owner null guard remains
before the new reference binding. After that guard, the adapter binds exactly
one non-null `ProviderForceScratch &active_provider_force_scratch` with the
predicate `reuse_force_storage`: reusable calls select
`*provider_force_scratch`, while stateless calls select
`local_provider_force_scratch.emplace()`.

The predecessor mutable nullable active pointer, its post-declaration reseat
branch, and all active-pointer `->` member accesses are removed. The successor
has one active reference declaration and 18 active-reference `.` member
accesses. The function-scope `std::optional<ProviderForceScratch>` remains
disengaged for reusable calls and is emplaced exactly once for stateless calls.
Its lifetime still spans force preparation, provider dispatch, status and
finiteness validation, output commit, and destruction on every return path.

The canonical and vendored adapters are the exact same transformation of the
exact PR 475 predecessor and remain byte-identical. The verifier reconstructs
the complete successor adapter from exact PR 475 by replacing one pointer
selection block and exactly 18 `active_provider_force_scratch->` tokens. No
other adapter byte may change. This exact transform also proves that the
nullable input parameter and guard, two `compute_forces` branches, two provider
symbols, five semantic route classes, ABI conversion, descriptor routing,
status normalization, typed-error handling, rollback, finiteness checks, force
copying, and success-only external commit are preserved.

Dispatch and validation regions are not claimed byte-identical because their
member syntax changes from `->` to `.`. They are required to equal the PR 475
regions exactly after normalizing only that member syntax. The force private
symbol and energy private symbol still have one native-adapter callsite each;
the dispatch predicate remains only `compute_forces` and does not inspect
`reuse_force_storage`, output metadata, or evaluation metadata.

The native fake-provider adapter test is unchanged from exact PR 475 bytes.
Its provider-force-source, reusable forceful, reusable energy-only, stateless
forceful, and stateless energy-only routes remain frozen, together with six
reusable zero-destroy checks, three external-owner scope destroy checks, and six
stateless call-local lifecycle checks, typed-error and non-finite rollback, and
success commit assertions. The fake provider proves only adapter dispatch,
ownership, rollback, and callback boundaries; it does not execute the real
Rust allocator or Rust panic boundary and has no production or scientific
authority.

No Rust function, private header declaration, provider symbol, public symbol,
provider ABI, status ABI, checkpoint format, production caller, composite
source, or composite test changes. The private provider ABI remains version 1.
The raw-public transactional peer, checkpoint sources, export lists, and public
Rust/C headers remain frozen from exact PR 475.

Release and ASan/UBSan workflow lanes build the reciprocal, PME, composite,
adapter-transactionality, and composite-dynamics targets and select their
matching tests. Linux requires the inherited private all-scratch energy symbol
in the linked image and absent from dynamic exports; macOS remains
engine/export-only. The predecessor workflow detaches the exact PR 475 merge
object and runs its verifier and unit test before successor evidence is used.

This is type-state and ownership hardening only. No allocation-free,
allocation-count, allocation-behavior, heap-allocation-elision,
provider-allocation-elision, null-check-elision performance, reference-binding
performance, stack-storage reduction, scratch-footprint reduction, object-size
reduction, peak-memory reduction, performance, acceleration,
scientific-equivalence, molecular, HIP, product, or operational claim is made.
Using a non-null reference after the guard is not a runtime performance claim.

This evidence does not authorize reservation, molecular execution, Fresh-128,
D1/D2, Stage0, public benchmark, HIP-device execution, qualification reruns,
supervisor installation, or any operational, production, or scientific
conclusion. The blockers `external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

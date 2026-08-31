# Engine V2 native PME Rust reciprocal-provider force descriptor branch localization v1

This bounded successor changes only the lexical scope of the native C++
adapter's already directly bound `provider_forces` descriptor. The exact PR
477 predecessor declared the descriptor in common scope, populated it in a
standalone `if (compute_forces)` preparation branch, and later passed its
address to the force-specific provider symbol. The successor removes the
common-scope declaration and standalone preparation branch, then moves the
same declaration and preparation body to the beginning of the existing force
dispatch branch.

The canonical and vendored adapters are the same exact whole-file transform
of the exact PR 477 predecessor and remain byte-identical. The verifier
reconstructs each complete successor adapter by removing the unique outer
descriptor declaration, removing the unique standalone preparation branch,
and inserting the descriptor declaration plus that exact preparation body at
the start of the force dispatch branch. No other adapter byte may change.

Inside the single `if (compute_forces)` dispatch branch, the descriptor is
zero-initialized exactly once, the x/y/z backing vectors are resized, and
struct size, ABI version, capacity, and x/y/z pointers are populated in the
inherited order before the force-specific symbol receives
`&provider_forces`. Every `provider_forces` variable reference is confined to
that branch. The descriptor lives through the synchronous force-provider call
and is not needed by post-dispatch validation, which reads the backing scratch
vectors.

The energy branch is exact PR 477 bytes and has zero `provider_forces`
references, force-descriptor arguments, or x/y/z resize operations. It still
calls only the energy-specific all-three-scratch symbol with the shared energy
and error descriptors. The common `provider_error` descriptor and
`raw_status` remain available to both branches.

The dispatch region is not claimed byte-identical because it now contains the
branch-local descriptor preparation. Removing only that preparation from the
successor dispatch must reproduce the exact PR 477 dispatch. The relocated
preparation must reproduce the exact predecessor preparation bytes, preceded
only by the moved descriptor declaration. The post-dispatch status
normalization, typed-error handling, energy and force finiteness validation,
rollback, force copying, and success-only external commit remain exact PR 477
bytes.

The provider-force-source guard and reusable-owner null guard still precede
the non-null active scratch reference binding and dispatch. The active
`ProviderForceScratch` remains one reference with 18 member accesses. The
function-scope optional owner is still emplaced only for stateless calls;
reusable calls still select the external owner. Its lifetime continues through
dispatch, validation, commit, and destruction. The rollback guard and
`ProviderForceScratch` destructor are exact PR 477 bytes.

The two private provider symbols and five semantic route classes remain
unchanged: provider-force-source, reusable forceful, reusable energy-only,
stateless forceful, and stateless energy-only. The native fake-provider adapter
test is unchanged from exact PR 477 bytes, including six reusable zero-destroy
checks, three external-owner scope destroy checks, and six stateless call-local
lifecycle checks. The fake provider proves only adapter dispatch, ownership,
rollback, and callback boundaries; it does not execute the real Rust allocator
or Rust panic boundary and has no production or scientific authority.

No Rust function, private header declaration, provider symbol, public symbol,
provider ABI, status ABI, checkpoint format, production caller, composite
source, or composite test changes. The private provider ABI remains version 1.
The raw-public transactional peer, checkpoint sources, export lists, and
public Rust/C headers remain frozen from exact PR 477.

Release and ASan/UBSan workflow lanes build the reciprocal, PME, composite,
adapter-transactionality, and composite-dynamics targets and select their
matching tests. Linux requires the inherited private all-scratch energy symbol
in the linked image and absent from dynamic exports; macOS remains
engine/export-only. The predecessor workflow detaches the exact PR 477 merge
object and runs its verifier and unit test before successor evidence is used.

This is source-scope/type-state hardening only. No allocation-free,
allocation-count, allocation-behavior, heap-allocation-elision,
provider-allocation-elision, stack-storage reduction, scratch-footprint
reduction, object-size reduction, peak-memory reduction, branch-localization
performance improvement, force-descriptor scope-reduction performance
improvement, performance, acceleration, scientific-equivalence, molecular,
HIP, product, or operational claim is made. Shortening a descriptor's lexical
scope is not a runtime performance claim.

This evidence does not authorize reservation, molecular execution, Fresh-128,
D1/D2, Stage0, public benchmark, HIP-device execution, qualification reruns,
supervisor installation, or any operational, production, or scientific
conclusion. The blockers `external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

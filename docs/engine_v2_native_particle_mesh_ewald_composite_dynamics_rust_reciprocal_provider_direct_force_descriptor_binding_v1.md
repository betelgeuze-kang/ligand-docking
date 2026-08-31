# Engine V2 native PME Rust reciprocal-provider direct force descriptor binding v1

This bounded successor changes only how the native C++ adapter supplies its
already prepared `provider_forces` descriptor to the force-producing private
provider symbol. The exact PR 476 predecessor declared a nullable local
`force_pointer`, assigned `&provider_forces` inside the existing
`if (compute_forces)` preparation branch, and later passed `force_pointer` to
the force symbol. The successor removes that one declaration and one
assignment and passes `&provider_forces` directly at the force-symbol call.

The canonical and vendored adapters are the same exact three-point transform
of the exact PR 476 predecessor and remain byte-identical. The verifier
reconstructs each complete successor adapter by deleting exactly the
`force_pointer` declaration, deleting exactly its `&provider_forces`
assignment, and replacing exactly the force-symbol `force_pointer` argument
with `&provider_forces`. No other adapter byte may change.

The `provider_forces{}` descriptor declaration remains unique. Its struct
size, ABI version, capacity, and x/y/z pointers are still populated only in the
existing `if (compute_forces)` preparation branch before dispatch. The force
symbol has exactly one adapter callsite and receives exactly one direct
`&provider_forces` argument. The energy symbol has exactly one adapter
callsite, its branch contains no force-descriptor argument, and it still
receives only the energy and error descriptors.

The two-branch dispatch is not claimed byte-identical because its force
argument changes. It must equal the exact PR 476 dispatch after normalizing
only `&provider_forces` back to `force_pointer`. The post-dispatch status
normalization, typed-error handling, energy and force finiteness validation,
rollback, force copying, and success-only external commit are required to be
exact PR 476 bytes. The provider-force-source guard, reusable-owner null guard,
active scratch reference binding, descriptor preparation, two provider
symbols, five semantic route classes, reusable scratch ownership, and ABI
conversion remain preserved by the whole-file exact transform.

The active `ProviderForceScratch` remains one non-null reference with 18 member
accesses. The function-scope optional owner is still emplaced only for
stateless calls; reusable calls still select the external owner after the
existing null guard. Its lifetime continues through descriptor preparation,
dispatch, validation, commit, and destruction. The rollback guard and
`ProviderForceScratch` destructor are exact PR 476 bytes.

The native fake-provider adapter test is unchanged from exact PR 476 bytes.
Its provider-force-source, reusable forceful, reusable energy-only, stateless
forceful, and stateless energy-only route classes remain frozen, together with
six reusable zero-destroy checks, three external-owner scope destroy checks,
and six stateless call-local lifecycle checks. The fake provider proves only
adapter dispatch, ownership, rollback, and callback boundaries; it does not
execute the real Rust allocator or Rust panic boundary and has no production
or scientific authority.

No Rust function, private header declaration, provider symbol, public symbol,
provider ABI, status ABI, checkpoint format, production caller, composite
source, or composite test changes. The private provider ABI remains version 1.
The raw-public transactional peer, checkpoint sources, export lists, and
public Rust/C headers remain frozen from exact PR 476.

Release and ASan/UBSan workflow lanes build the reciprocal, PME, composite,
adapter-transactionality, and composite-dynamics targets and select their
matching tests. Linux requires the inherited private all-scratch energy symbol
in the linked image and absent from dynamic exports; macOS remains
engine/export-only. The predecessor workflow detaches the exact PR 476 merge
object and runs its verifier and unit test before successor evidence is used.

This is local binding simplification only. No allocation-free,
allocation-count, allocation-behavior, heap-allocation-elision,
provider-allocation-elision, pointer-temporary-removal performance,
direct-descriptor-binding performance, stack-storage reduction,
scratch-footprint reduction, object-size reduction, peak-memory reduction,
performance, acceleration, scientific-equivalence, molecular, HIP, product,
or operational claim is made. Removing the local pointer temporary is not a
runtime performance claim.

This evidence does not authorize reservation, molecular execution, Fresh-128,
D1/D2, Stage0, public benchmark, HIP-device execution, qualification reruns,
supervisor installation, or any operational, production, or scientific
conclusion. The blockers `external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

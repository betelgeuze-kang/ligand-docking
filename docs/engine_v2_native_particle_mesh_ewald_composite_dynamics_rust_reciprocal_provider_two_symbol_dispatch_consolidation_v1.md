# Engine V2 native PME Rust reciprocal-provider two-symbol dispatch consolidation v1

This bounded successor changes only the native C++ adapter provider-dispatch
branch and callsite structure. It replaces five route-specific arms with one
`if (compute_forces)` force arm and one energy-only `else` arm. The all-scratch
force private symbol now has exactly one native-adapter callsite, and the
all-scratch energy private symbol also has exactly one. The dispatch predicate
is only `compute_forces`; it does not inspect `reuse_force_storage`,
`out_provider_force_source_result`, or `out_evaluation`.

The provider-force-source validity guard and reusable-owner null guard remain
before dispatch. Force vectors, the force descriptor, and `force_pointer` are
still prepared before the consolidated force call. The provider-force-source,
reusable forceful, reusable energy-only, stateless forceful, and stateless
energy-only semantic classes therefore retain the same symbol, descriptor, and
output routing selected by their inherited `compute_forces` contract.

The canonical and vendored adapters are the exact same transformation of the
exact PR 474 predecessor and remain byte-identical. Everything outside the
five-arm dispatch block is frozen from exact PR 474 bytes. This includes the
function-scope `std::optional<ProviderForceScratch>` selection and lifetime,
status normalization, typed-error handling, energy and force finiteness checks,
`Evaluation` rollback, force copying, external result commit, and the
`ProviderForceScratch` destructor.

The native fake-provider adapter test is unchanged from exact PR 474 bytes. Its
five semantic route classes and all lifecycle and transactionality assertions
remain frozen: six reusable zero-destroy checks, three external-owner scope
destroy checks, and six stateless call-local lifecycle checks. The fake
provider proves only dispatch, rollback, and callback boundaries; it does not
execute the real Rust allocator or Rust panic boundary and has no production or
scientific authority.

No Rust function, private header declaration, provider symbol, public symbol,
provider ABI, status ABI, checkpoint format, production caller, or composite
test changes. The private provider ABI remains version 1. The public
transactional, direct-force, and workspace-only force entries retain zero
native-adapter callsites. The raw-public ForceOutput transactional peer,
checkpoint sources, export lists, and public Rust/C headers remain frozen.

Release and ASan/UBSan workflow lanes build the reciprocal, PME, composite,
adapter-transactionality, and composite-dynamics targets and select their
matching tests. Linux requires the inherited private all-scratch energy symbol
in the linked image and absent from dynamic exports; macOS remains
engine/export-only. The predecessor workflow detaches the exact PR 474 merge
object and runs its verifier and unit test before successor evidence is used.

This is branch and callsite consolidation only. No allocation-free,
allocation-count, allocation-behavior, heap-allocation-elision,
provider-allocation-elision, stack-storage reduction, scratch-footprint
reduction, object-size reduction, peak-memory reduction, performance,
acceleration, scientific-equivalence, molecular, HIP, product, or operational
claim is made. Reducing source branches and repeated call expressions is not a
runtime performance claim.

This evidence does not authorize reservation, molecular execution, Fresh-128,
D1/D2, Stage0, public benchmark, HIP-device execution, qualification reruns,
supervisor installation, or any operational, production, or scientific
conclusion. The blockers `external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

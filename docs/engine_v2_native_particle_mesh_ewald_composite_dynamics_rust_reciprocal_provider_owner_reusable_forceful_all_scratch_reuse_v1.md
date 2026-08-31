# Engine V2 native PME Rust reciprocal-provider reusable forceful all-scratch reuse v1

This bounded successor changes only the native C++ adapter's internal reusable
force-producing branch. It now calls the existing private hidden
`bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1`
entry and supplies the owner's reciprocal workspace, neutrality-sort scratch,
particle-assignment scratch, and force x/y/z channels. No Rust function,
private provider declaration, public symbol, provider ABI, or checkpoint format
is added or changed; the private provider ABI remains version 1.

The five adapter branches remain distinct while using four unique provider
symbols. Provider-force-source and reusable forceful evaluation both use the
all-three-scratch force entry. Reusable energy-only evaluation keeps the
all-three-scratch energy entry, non-reusable forceful evaluation keeps the
direct-force entry, and non-reusable energy-only evaluation keeps the public
transactional entry with forces disabled. The workspace-only force ABI remains
available in Rust and the private header but has zero native-adapter call sites.

The production composite forceful path was already routed through the
provider-force-source all-scratch branch and is frozen byte-for-byte here. No
production caller of the newly changed reusable-forceful adapter branch exists
in this scope. This is adapter ownership completeness and future-safe routing
evidence, not a production allocation or performance improvement claim.

Caller `Evaluation` now has success-only commit semantics. An
`EvaluationForceStorageRollback` guard swaps caller force storage into a local
candidate and restores the exact address, capacity, size, and force bits on
every failure. The caller energy bits also remain unchanged until final commit.
All provider force channels are scanned for finiteness before candidate resize
or copy. Static assertions freeze no-throw force-vector swap, force-element
assignment, and final `Evaluation` move assignment after the last fallible
operation. Tests cover a late typed provider error and a provider-success
response containing a late NaN force.

Only caller `Evaluation` is transactional. `Error` is reset or updated by the
adapter, and owner force x/y/z, reciprocal workspace, neutrality-sort scratch,
and particle-assignment scratch are derived and nontransactional. They may
change on a late error, panic boundary, or rejected non-finite success.

The inherited Rust implementation still preflights all three descriptors,
their whole backing capacities, force outputs, inputs, and every mutable range
before leases or borrows. Its cold preparation order remains neutrality
sorting, particle assignment, then reciprocal workspace. A cold neutrality
failure retains all descriptors EMPTY; an assignment failure may retain
neutrality READY; and a later workspace failure may retain neutrality and
assignment READY. These are frozen predecessor semantics, not new execution
claims.

The native fake provider is only route-selection and commit-separation
evidence. Release and ASan/UBSan exercise the changed native adapter boundary;
the fake does not establish real-Rust scientific transactionality, allocator
behavior, or panic behavior. Linux linked-image checks require the existing
private force symbol in the normal symbol table and absent from dynamic
exports. macOS remains engine/export-only.

No allocation-free, performance, acceleration, scientific-equivalence,
molecular, HIP, or product claim is made. This evidence does not authorize
reservation, molecular execution, Fresh-128, D1/D2, Stage0, public benchmark,
HIP-device execution, qualification reruns, supervisor installation, or any
production/scientific conclusion. The blockers
`external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

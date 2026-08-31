# Engine V2 native PME Rust reciprocal-provider stateless forceful all-scratch v1

This bounded successor changes only the native C++ adapter's stateless
force-producing branch. It replaces the direct-force call with the existing
private hidden
`bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1`
entry. The adapter supplies call-local force x/y/z channels plus call-local
reciprocal-workspace, neutrality-sort, and particle-assignment descriptors. No
Rust function, private provider declaration, public symbol, provider ABI, or
checkpoint format is added or changed; the private provider ABI remains
version 1.

The five adapter branches remain distinct while using three unique provider
symbols. Provider-force-source, reusable forceful, and stateless forceful
evaluation share the existing all-three-scratch force entry. Reusable
energy-only evaluation retains the all-three-scratch energy entry, and
stateless energy-only evaluation retains the public transactional entry with
forces disabled. The direct-force and workspace-only force ABIs remain
available in frozen Rust and private headers but now have zero native-adapter
call sites.

Each stateless call constructs one automatic `ProviderForceScratch`. Its three
descriptor fields are exact all-zero EMPTY values before provider dispatch and
are pairwise distinct. The provider may prepare or mutate their derived
payloads during the call. C++ automatic lifetime then invokes the matching
particle-assignment, neutrality-sort, and reciprocal-workspace destroy
callbacks exactly once each before the adapter returns, on success, typed
failure, and rejected non-finite success. The descriptors and force channels
are not persisted or reused across calls. This is explicitly not persistent
scratch reuse or cross-call reuse.

Caller `Evaluation` remains success-only. The stateless branch does not move
caller force storage into its candidate, so a late typed provider error or a
provider-success response containing a late NaN force preserves the exact
caller energy bits and force address, capacity, size, and bits. All provider
force channels are scanned for finiteness before candidate resize or copy. The
existing `EvaluationForceStorageRollback` guard for reusable evaluation is
frozen byte-for-byte from PR 471.

Only caller `Evaluation` has the asserted rollback boundary. `Error` may be
reset or updated, while call-local force x/y/z, reciprocal workspace,
neutrality-sort scratch, and particle-assignment scratch are derived and
nontransactional. They may change before their call-local destruction on a
late error, panic boundary, or rejected non-finite success.

The inherited Rust implementation still preflights all three descriptors,
their whole backing capacities, force outputs, inputs, and every mutable range
before leases or borrows. Its cold preparation order remains neutrality
sorting, particle assignment, then reciprocal workspace. Those are frozen
Rust contracts, not a claim that the fake provider executes Rust allocation or
panic behavior.

Public headers, private provider headers, Rust sources, composite callers, and
composite tests are frozen to the exact PR 471 predecessor. The unchanged
production stateless forceful caller reaches the changed adapter branch, but
this synthetic boundary evidence makes no production allocation, performance,
or scientific claim. The native fake provider checks dispatch, initially EMPTY
descriptors, exact destruction, force writes, and Evaluation rollback only.
Release and ASan/UBSan exercise that native fake-provider boundary plus the
stateless reciprocal, particle-mesh Ewald, and short-plus-PME composite caller
tests. Linux
linked-image checks require the existing private all-scratch force symbol in
the normal symbol table and absent from dynamic exports; macOS remains
engine/export-only.

No allocation-free, persistent-reuse, cross-call-reuse, performance,
acceleration, scientific-equivalence, molecular, HIP, or product claim is
made. This evidence does not authorize reservation, molecular execution,
Fresh-128, D1/D2, Stage0, public benchmark, HIP-device execution,
qualification reruns, supervisor installation, or any production/scientific
conclusion. The blockers `external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

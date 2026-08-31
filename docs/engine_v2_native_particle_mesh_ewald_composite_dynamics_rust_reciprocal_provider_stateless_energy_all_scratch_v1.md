# Engine V2 native PME Rust reciprocal-provider stateless energy all-scratch v1

This bounded successor changes only the native C++ adapter's stateless
energy-only branch. It replaces that branch's public transactional provider
call with the existing private hidden
`bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1`
entry. The call supplies one automatic `ProviderForceScratch` owner's
reciprocal-workspace, neutrality-sort, and particle-assignment descriptors.
Its force x/y/z vectors remain empty and are never passed to this energy-only
entry. No Rust function, private header declaration, public symbol, provider
ABI, status ABI, or checkpoint format is added or changed; the private
provider ABI remains version 1.

The five adapter branches remain distinct while using two unique provider
symbols. Provider-force-source, reusable forceful, and stateless forceful
evaluation retain the existing all-three-scratch force entry. Reusable and
stateless energy-only evaluation use the existing all-three-scratch energy
entry. The public transactional, direct-force, workspace-only force,
workspace-only energy, and workspace-plus-neutrality energy ABIs remain
available in frozen Rust and private headers. The public transactional entry,
direct-force entry, and workspace-only force entry have zero native-adapter
call sites. The raw-public ForceOutput transactional peer test remains frozen
byte-for-byte from exact PR 472.

Each stateless energy-only call constructs one automatic
`ProviderForceScratch`. Its three descriptor fields have exact all-zero EMPTY
values before provider dispatch and are pairwise distinct. The matching
particle-assignment, neutrality-sort, and reciprocal-workspace destroy
callbacks run exactly once each before the adapter returns on success, typed
failure, and rejected non-finite energy success. The fake provider also proves
that the force-output allocation-failure injection remains pending and no
force channels are supplied. This is a call-local, single-call lifetime, not
persistent scratch reuse or cross-call reuse. It makes no allocation-count or
allocation-elision assertion.

Caller `Evaluation` remains success-only. A late typed energy error and a
provider-success response containing non-finite energy preserve the exact
caller energy bits and force address, capacity, size, and bits. Provider
energy is scanned for finiteness before the candidate is externally committed.
The existing `EvaluationForceStorageRollback` guard for reusable force storage
is frozen byte-for-byte from PR 472. Only caller `Evaluation` has the asserted
rollback boundary. `Error` and the call-local derived scratch payloads are not
claimed transactional, and the evidence makes no claim about their bytes
after a real provider has begun preparation.

The inherited Rust implementation and private headers are frozen from exact
PR 472. Rust still preflights all three descriptors, their complete backing
capacities, inputs, and mutable-range disjointness before leases or borrows;
its cold preparation order remains neutrality sorting, particle assignment,
then reciprocal workspace. Those are frozen implementation contracts. The
native fake provider does not execute the real Rust allocator or panic
boundary, and it has neither production nor scientific authority.

Public headers and symbol surfaces, reciprocal API and particle-mesh Ewald
callers, composite callers, and composite tests are exact PR 472 bytes. The
production stateless energy caller reaches the changed adapter branch through
the reciprocal API, PME parent, and short-plus-PME composite call chains.
Release and ASan/UBSan workflow lanes build exact reciprocal, PME, composite,
adapter-transactionality, and composite-dynamics native targets and select the
matching tests. This validates dispatch and commit separation at the native
fake-provider boundary; it does not claim real-Rust sanitizer instrumentation
or cross-lane bit parity. Linux linked-image checks require the existing
private all-scratch energy symbol in the normal symbol table and absent from
dynamic exports; macOS remains engine/export-only.

No allocation-free, allocation-count, persistent-reuse, cross-call-reuse,
performance, peak-memory, acceleration, scientific-equivalence, molecular,
HIP, or product claim is made. This evidence does not authorize reservation,
molecular execution, Fresh-128, D1/D2, Stage0, public benchmark, HIP-device
execution, qualification reruns, supervisor installation, or any operational,
production, or scientific conclusion. The blockers
`external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

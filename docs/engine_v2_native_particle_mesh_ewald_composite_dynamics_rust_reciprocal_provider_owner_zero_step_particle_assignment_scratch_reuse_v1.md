# Engine V2 native PME Rust reciprocal-provider owner zero-step particle-assignment scratch reuse v1

This bounded successor extends only the stateful Rust force-free
(`compute_forces == false`) composite route. The adapter selects the private
hidden
`bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1`
entry and supplies the owner's reciprocal workspace, neutrality-sort scratch,
and particle-assignment scratch. The entry uses the explicit
`EnergyWithWorkspaceAndNeutralitySortScratchAndParticleAssignmentScratch` mode
with `ForceStorageMode::Disabled` and accepts no force descriptor. The
workspace-only and workspace-plus-neutrality predecessor energy entries remain
available, and the private provider ABI version remains 1.

The five adapter branches stay distinct: provider-force-source uses the
triple-scratch forceful entry, reusable forceful evaluation uses the
force-output workspace entry, reusable energy-only evaluation uses the new
all-three-scratch entry, non-reusable forceful evaluation uses the direct-force
entry, and non-reusable energy-only evaluation uses the public transactional
entry with forces disabled. Production composite control flow is unchanged; it
already passes the complete owner scratch to the reusable zero-step route.

Rust preflights all three descriptors and each whole backing capacity against
every descriptor, input, and mutable output before acquiring any of the three
leases and before borrowing input channels. EMPTY and READY are accepted.
Malformed or LEASED descriptors, same-descriptor aliases, cross-backing
aliases, and aliases into capacity-only tails fail closed. All Drop paths
restore ownership after success, error, or panic. Energy has success-only
commit semantics, while report, checkpoint, and static-fingerprint state remain
transactional.

The valid-path allocation order remains neutrality sorting, particle
assignment, then reciprocal workspace preparation. A cold neutrality failure
leaves all three descriptors EMPTY. A cold assignment failure may retain
neutrality READY while assignment and workspace remain EMPTY. A cold workspace
failure may retain both neutrality and assignment READY while workspace remains
EMPTY. Growth OOM preserves the affected descriptor's prior raw parts and
payload. Workspace, neutrality-sort, and particle-assignment payloads are
derived scratch and are not transactional.

Capacity-sufficient warm calls elide the tracked neutrality, assignment, and
workspace reserve requests, and repeated zero-step and forceful calls retain
the same owner-private allocation addresses and capacities. Force x/y/z remain
untouched by the force-free entry. Two live owners retain six pairwise-disjoint
scratch allocations. These observations are limited to the explicitly tracked
reserve sites and do not establish a generally allocation-free provider or
steady state.

The native fake provider is only a route-selection and commit-separation test
double. It is not allocator, panic-boundary, scientific, performance, or
product authority. Linux Release tests exercise the real Rust provider and
require the new hidden symbol in the linked image while keeping it absent from
dynamic exports. Native sanitizer tests cover native and fake-provider
boundaries; the Rust provider itself is not sanitizer-instrumented. macOS
remains engine/export-only.

No allocation-free, performance, acceleration, scientific-equivalence,
molecular, HIP, or product claim is made. This evidence does not authorize
reservation, molecular execution, Fresh-128, D1/D2, Stage0, public benchmark,
HIP-device execution, or any production/scientific conclusion. The blocker
`external_reservation_provider_not_operational` and all inherited blockers
remain active, and unresolved operational decisions remain 32.

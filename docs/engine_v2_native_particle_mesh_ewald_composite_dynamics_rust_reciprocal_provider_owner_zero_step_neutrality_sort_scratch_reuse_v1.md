# Engine V2 native PME Rust reciprocal-provider owner zero-step neutrality-sort scratch reuse v1

This bounded successor extends only the stateful Rust force-free
(`compute_forces == false`) composite route. The adapter selects the private
hidden
`bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_v1`
entry and supplies the owner's reciprocal workspace and neutrality-sort
scratch. The entry uses an explicit
`EnergyWithWorkspaceAndNeutralitySortScratch` mode with
`ForceStorageMode::Disabled`; it accepts no force or particle-assignment
descriptor. The predecessor workspace-only hidden entry remains available and
the private provider ABI version remains 1.

The five adapter branches stay distinct: provider-force-source uses the
triple-scratch entry, reusable forceful evaluation uses the force-output
workspace entry, reusable energy-only evaluation uses the new workspace plus
neutrality entry, non-reusable forceful evaluation uses the direct-force
entry, and non-reusable energy-only evaluation uses the public transactional
entry with forces disabled. Production composite control flow is unchanged;
it already passes the complete owner scratch to the reusable zero-step route.

Rust preflights both descriptors and each whole backing capacity against every
descriptor, input, and mutable output before acquiring the workspace and
neutrality leases and before borrowing input channels. EMPTY and READY are
accepted. Malformed or LEASED descriptors, same-descriptor aliases,
cross-backing aliases, and aliases into capacity-only tails fail closed. Both
Drop paths restore ownership after success, error, or panic. Energy has
success-only commit semantics, and native Evaluation, report, checkpoint, and
static-fingerprint state remain transactional.

The valid-path allocation order remains neutrality sorting, call-local
particle assignment, then reciprocal workspace preparation. A cold neutrality
allocation failure leaves both owner descriptors EMPTY. A later assignment or
workspace failure may leave neutrality READY with a changed sorted payload
while a cold workspace remains EMPTY. Warm neutrality growth failure preserves
its prior raw parts and payload; warm workspace growth failure preserves the
workspace raw parts and payload after neutrality may already have been
rewritten. Workspace and neutrality payloads are derived scratch and are not
transactional.

Capacity-sufficient warm calls elide neutrality and workspace reserve requests,
but the call-local particle-assignment allocation remains and its injected OOM
is still consumed. Force x/y/z and the owner particle-assignment descriptor are
untouched by this force-free entry. Two live owners retain disjoint workspace
and neutrality allocations. The old workspace-only energy entry, forceful
workspace-plus-neutrality entry, triple-scratch force source, stateless path,
and C++ lane remain independently covered.

The native fake provider is only a route-selection and commit-separation test
double. It is not allocator, panic-boundary, scientific, performance, or
product authority. Linux Release tests exercise the real Rust provider and
require the new hidden symbol in the linked image while keeping it absent from
dynamic exports. Native sanitizer tests cover native and fake-provider
boundaries; the Rust provider itself is not sanitizer-instrumented. macOS
remains engine/export-only.

This evidence is not allocation-free because particle assignment remains
call-local. No performance, acceleration, scientific-equivalence, molecular,
HIP, or product claim is made. It does not authorize reservation, molecular
execution, Fresh-128, D1/D2, Stage0, public benchmark, HIP-device execution,
or any production/scientific conclusion. The blocker
`external_reservation_provider_not_operational` and all inherited blockers
remain active, and unresolved operational decisions remain 32.

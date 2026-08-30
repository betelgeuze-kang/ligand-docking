# Engine V2 native PME Rust reciprocal-provider owner zero-step workspace reuse v1

This bounded successor routes stateful Rust force-free (`compute_forces ==
false`) composite evaluation through the owner reciprocal workspace. The
adapter selects the private hidden
`bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1` entry
without constructing or exposing force channels. That Rust entry uses
`ForceStorageMode::Disabled`; it accepts the system, model, reciprocal
workspace, energy output, and typed-error output, but no force, neutrality-sort,
or particle-assignment descriptor.

The five dispatch branches remain distinct: provider-force-source uses the
existing triple-scratch entry, reusable forceful evaluation uses the existing
force-output workspace entry, reusable energy-only evaluation uses the new
hidden workspace entry, non-reusable forceful evaluation uses the existing
direct-force entry, and non-reusable energy-only evaluation uses the public
transactional entry with forces disabled.

The reusable path requires a non-null scratch owner before the provider ABI is
queried. Rust preflights the workspace descriptor and its whole backing
capacity against every input and mutable output before acquiring the lease.
EMPTY and READY are accepted; malformed and LEASED descriptors fail closed.
The lease Drop path restores EMPTY after a cold, still-unallocated failure and
READY after success, error, or panic. Energy has success-only commit semantics:
provider status, typed-error, and finite-result validation all precede the
caller-visible write. A failed provider call therefore preserves the caller's
complete evaluation sentinel.

The force x/y/z vectors remain untouched, and the owner neutrality-sort and
particle-assignment scratch remain call-local to their existing provider
phases. The workspace payload is derived scratch and is not transactional;
growth OOM instead preserves the prior READY raw parts and payload. The native
fake provider is only a route-selection and commit-separation test double. It
is not allocator, scientific, performance, or product authority.

The Rust provider tests freeze cold allocation, warm reuse, growth failure,
panic recovery, descriptor and backing-range alias rejection, and
interoperation with the forceful workspace entry. Linux Release tests exercise
the real Rust provider plus native reciprocal evaluator, focused adapter
transactionality, and composite dynamics. Native sanitizer tests exercise the
adapter through a fake provider; the Rust provider itself is not
sanitizer-instrumented. The exact public export allowlist is checked on Linux
and macOS. Linux `nm` additionally requires the hidden energy-workspace symbol
to exist in the linked image while remaining absent from its dynamic exports;
the symbol therefore remains outside the dynamic product ABI.

This evidence is not allocation-free: call-local neutrality sorting and
particle assignment may still allocate, and cold or growth paths may allocate.
No performance, acceleration, scientific-equivalence, molecular, HIP, or
product claim is made. Cross-lane parity and operational readiness are also
unclaimed. It does not authorize reservation, molecular execution, Fresh-128,
public benchmark, HIP-device execution, or any production/scientific
conclusion. In particular, `external_reservation_provider_not_operational` and
the other inherited blockers remain active, and unresolved operational
decisions remain 32.

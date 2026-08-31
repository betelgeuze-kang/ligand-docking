# Engine V2 native PME Rust reciprocal-provider conditional call-local scratch lifecycle v1

This bounded successor changes only native C++ adapter ownership selection for
`ProviderForceScratch`. The adapter replaces one unconditional automatic owner
with a function-scope `std::optional<ProviderForceScratch>`. The optional is
emplaced exactly once only for stateless calls. Reusable calls leave it
disengaged and keep `active_provider_force_scratch` pointed at the caller's
external owner. The inherited C++17 build contract supplies `std::optional`;
no build setting changes.

The function-scope optional remains alive through force-channel preparation,
provider dispatch, status normalization, energy and force finiteness checks,
force copying, and external result commit. It is not reset early or placed in
a narrower block. Stateless energy and force calls therefore retain their
single-call owner lifetime: the matching particle-assignment,
neutrality-sort, and reciprocal-workspace destroy callbacks still run exactly
once each before return for the covered success, typed-failure, and rejected
non-finite-success paths.

Reusable calls no longer create an unused call-local owner whose destructor
would invoke three empty-descriptor destroy callbacks. The native fake-provider
test asserts zero destroy callbacks before external owner scope exit after six
reusable calls: forceful success, typed failure, and rejected non-finite force
success; energy-only success and typed failure; and provider-force-source
success. After each of the three explicit external-owner scopes exits, the
matching workspace, neutrality-sort, and particle-assignment callbacks have
each run exactly once. This establishes only owner lifetime and unused
call-local destroy-callback elision.

The five adapter branches remain distinct and use the same two private provider
symbols. Provider-force-source, reusable forceful, and stateless forceful calls
retain the all-three-scratch force entry. Reusable and stateless energy-only
calls retain the all-three-scratch energy entry. Descriptor routing, provider
dispatch, status handling, finiteness validation, `Evaluation` rollback, result
commit, the raw-public ForceOutput transactional peer, and all stateless
lifecycle test regions are frozen from exact PR 473.

No Rust function, private header declaration, public symbol, provider ABI,
status ABI, checkpoint format, production caller, or composite test changes.
The private provider ABI remains version 1. Public transactional, direct-force,
workspace-only, workspace-plus-neutrality, and all-three-scratch entries remain
available as before. The public transactional, direct-force, and workspace-only
force entries retain zero native-adapter call sites. Canonical and vendored
adapter sources remain byte-identical.

Release and ASan/UBSan workflow lanes build the reciprocal, PME, composite,
adapter-transactionality, and composite-dynamics targets and select their
matching tests. The native fake provider proves dispatch and lifecycle callback
boundaries; it does not execute the real Rust allocator or Rust panic boundary
and has no production or scientific authority. Linux requires the inherited
private all-scratch energy symbol in the linked image and absent from dynamic
exports; macOS remains engine/export-only.

The optional still reserves inline object storage. No allocation-free,
allocation-count, heap-allocation-elision, provider-allocation-elision,
stack-storage reduction, object-size reduction, persistent-reuse,
cross-call-reuse, performance, peak-memory, acceleration,
scientific-equivalence, molecular, HIP, or product claim is made. Destroy
callback elision is not a performance claim.

This evidence does not authorize reservation, molecular execution, Fresh-128,
D1/D2, Stage0, public benchmark, HIP-device execution, qualification reruns,
supervisor installation, or any operational, production, or scientific
conclusion. The blockers `external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false` remain active; unresolved
operational decisions remain 32.

# Engine V2 direct-Ewald composite-dynamics backend preflight v1

## Scope

This bounded successor hardens only the backend preflight of the frozen
direct-Ewald composite-dynamics v1 boundary. The requested backend is authoritative.
A call is accepted only when the request is exactly
`BG_BACKEND_CPP_CPU_REFERENCE` or `BG_BACKEND_RUST_CPU` and the resolved lane
is the same CPU lane.

`BG_BACKEND_AUTO`, `BG_BACKEND_HIP_SAFE`, `BG_BACKEND_HIP_FAST`, and unknown
values return `BG_STATUS_UNSUPPORTED_BACKEND`. In particular, a real `AUTO`
context remains rejected when context creation resolves it to Rust CPU. An
explicit CPU request whose resolved lane differs returns
`BG_STATUS_ABI_MISMATCH`. The checks run before owner-invariant validation,
force evaluation, integration, or dynamic-state publication.

The safe Rust wrapper rejects an unsupported requested lane before querying
the resolved backend. For an explicit CPU request it resolves the lane,
returns an ABI error for any mismatch, and only then validates resolved-lane
support. This complete preflight precedes composite ABI compatibility and the
native composite integration call. It cannot use a resolved CPU lane to
authorize an `AUTO` or HIP request.

## Transactional rejection

Native regression coverage constructs a real `AUTO` context and verifies its
preserved `AUTO` request and resolved Rust CPU lane before exercising the
integration boundary. It also constructs a mismatched explicit-CPU context
and covers HIP and unknown requests. These paths verify report, typed-error, and dynamic-state transactionality: the caller report and every simulation
state byte remain unchanged, while a valid stale direct-Ewald typed error is
cleared before the untyped preflight rejection is returned.

Safe Rust coverage snapshots the absolute step, particle channels, and exact
`BGDEC001` checkpoint image around the real-`AUTO` rejection. Explicit C++ CPU
and Rust CPU integration remain covered by the frozen dynamics regressions.

## Frozen compatibility boundary

No ABI, public-symbol, owner, or checkpoint-format change is introduced.
Engine ABI 1.21, direct-Ewald ABI 1.0, stateless direct-composite ABI 1.0, and
direct-composite-dynamics ABI 1.0 remain unchanged. The stateful boundary
still exports exactly its 13 existing symbols in
`BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0`. `BGDEC001` retains its
104-byte header and existing fingerprint, checksum, and transactionality
rules. The C11 and C++ probes are byte-identical to the frozen predecessor.

The predecessor is PR #438:

- reviewed head `581a17a135d75ddf085c4edd29f3763c2f691fcf`;
- squash merge `e434295b1711f612e0f7e9fac2d95de92abf19a8`;
- common exact tree `3546ef29ae708c16c7af1e3be4925d2d7ad1f6b5`;
- profile SHA-256
  `42aad2692719d3d0233d9b71e24e6b49fe50a27fbc150d31fb4d9688ae84215f`;
- 113-entry source-manifest SHA-256
  `1a7a284467958e7c153edb0afd86cc5ea4ad07b659266ecf59d9da7549a19d15`.

Standalone verification always requires the exact merge object and tree,
reads the immutable profile and manifest from that merge, and requires the
checked-out #438 evidence to remain byte-identical. The reviewed-head SHA
remains frozen metadata. A shallow standalone checkout may omit that reviewed
commit; if the object is locally present, its tree must equal the recorded
merge tree. All required and optional object probes set `GIT_NO_LAZY_FETCH=1`,
so standalone verification cannot fetch missing objects or mutate a partial
clone. The verifier also compares the public ABI headers, checkpoint
implementation, and ABI probes directly with their #438 blobs.

The successor branch base is exact PR #442 merge
`5f6f4e2642dbe5c1272b2a9710288db25db5164f`, tree
`95f3d64a553f6c261d59a7ef8bd202561d51c45a`. The original successor slice has
11 paths: five modified implementation/test files and six new profile,
manifest, documentation, verifier, unit, and workflow files. For each of the
five modified files, the verifier freezes the exact base and current byte
counts and SHA-256 digests. This repository-config-independent binding permits
unrelated paths in later descendant work while rejecting any drift in the
intended backend preflight implementation delta.

## Evidence and CI

The generated successor evidence is:

- `config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1.json`;
- `config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1_sources.json`.

Its acyclic source closure includes all 113 current paths bound by #438, the
exact immutable #438 profile and manifest, the root build entry point, and the
new documentation, verifier, unit suite, and workflow. The generated profile
and source manifest exclude themselves from hashed file rows. Non-hash
manifest metadata records all six successor evidence paths, including those
two generated files.

Normal verification is read-only:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py
```

Only an intentional update of the bound inputs may regenerate both successor
files:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py --refresh
```

The pinned-actions workflow explicitly fetches `refs/pull/438/head`, requires
its exact reviewed-head SHA and tree, and verifies the frozen merge, profile,
and manifest before running the verifier and unit suite, focused native
release and sanitizer tests, Rust raw/safe tests and docs, and Linux/macOS
export checks. It invokes no HIP device, molecular execution, reservation,
root supervisor, benchmark, or fixed64 qualification workflow.

All four workflow `uses:` entries are the exact same 40-hex checkout pin. One
global permission block grants only `contents: read`, with no job override or
write scope. Global CUDA, HIP, and ROCR visibility is empty, every CMake
configuration disables both HIP options, and both pull-request and push path
filters cover the bound `tools/__init__.py`. Reservation, supervisor, and
public-benchmark tokens are forbidden throughout this focused workflow.

## Authority boundary

Every authority field remains false. The exact blockers remain:

1. `external_reservation_endpoint_not_configured`;
2. `external_reservation_provider_not_operational`;
3. `external_reservation_trust_anchor_not_configured`;
4. `historical_execution_operational_authority_false`.

Those blockers and all 32 unresolved operational decisions remain
controlling. This deterministic CPU preflight evidence grants no reservation,
historical molecular A/B, D1/D2, Stage 0, Fresh-128, public benchmark,
scientific, acceleration, performance, product, qualification-rerun, HIP
device, molecular-execution, or test-double production authority.

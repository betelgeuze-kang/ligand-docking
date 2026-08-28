# Engine V2 native direct-Ewald composite dynamics ABI v1

Issue #434 adds a separately versioned, stateful development owner after the
stateless short-range + direct-Ewald composite boundary. It does not change
Engine ABI 1.21, direct-Ewald ABI 1.0, or stateless composite ABI 1.0.

The public header is
`include/betelgeuze/direct_ewald_composite_dynamics.h`. Composite-dynamics
ABI 1.0 exports exactly 13 symbols under
`BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0`. It deliberately reuses the
frozen `bg_distance_constraints_v1`, `bg_simulation_options_v1`, particle
view, and `bg_dynamics_report_v1` descriptors. No second options or report
layout is introduced.

Creation borrows the system, force field, immutable direct-Ewald model,
optional constraints, and Velocity-Verlet options only for the call. The
returned owner deep-copies all semantic inputs. Caller arrays may be changed or
destroyed after successful creation, while the owner's borrowed particle-view
addresses remain stable until owner destruction.

## Shared integration seam

The owner uses the existing canonical dynamics implementation through the
internal `dynamics::ForceProvider` seam. The provider evaluates the exact
short-range + direct-Ewald composite and translates its total and force vector
into the shared dynamics evaluation. Velocity-Verlet, SHAKE/RATTLE,
thermodynamic reporting, and the SHA-256 implementation stay shared with the
legacy owner rather than being copied.

Only Velocity-Verlet NVE is accepted. Langevin BAOAB is rejected at creation.
Explicit C++ CPU and Rust CPU contexts are supported. HIP-safe and HIP-fast
contexts fail closed before evaluation and never fall back to CPU.

Zero steps evaluates the current potential without changing state. Every
failed integration restores positions, velocities, absolute step, neighbor-list
publication state, and the caller report. A late direct-Ewald failure still
commits its typed direct-Ewald error after all ordinary output validation has
succeeded.

## Independent checkpoint format

The canonical checkpoint has magic `BGDEC001`, a 104-byte little-endian
header, and six float64 SoA particle channels. It uses the shared SHA-256 codec,
but its static fingerprint additionally binds the composite evaluator family,
all direct-Ewald model fields, exclusion versus explicit-zero provenance, and
the reused simulation options including timestep.

Legacy `BGDYN001` and composite `BGDEC001` checkpoints reject each other.
Corrupt, truncated, appended, size-mismatched, and fingerprint-mismatched input
is rejected transactionally. Size and write outputs also remain unchanged on
failure.

## Bounded deterministic validation

The executable native fixture has exactly four atoms with charges
`[0.7, -0.4, -0.6, 0.30000000000000004]` and a fully periodic
`[18, 20, 22]` Angstrom cell. It is synthetic and exact-neutral. It is not a
molecular or qualification input.

Focused validation covers:

- ABI identity, the 13-symbol export boundary, null/descriptor/alias failures,
  deep ownership, and stable borrowed views;
- C++ and Rust CPU zero-step bit identity with the stateless composite total,
  an independently assembled one-step Velocity-Verlet result, and same-lane
  bitwise repeat;
- split versus uninterrupted checkpoint continuation, bounded finite small-NVE
  execution, step overflow, HIP fail-closed behavior, and BAOAB rejection;
- whole-state and report rollback on a late typed Ewald distance failure;
- checkpoint corruption, cross-format rejection, fingerprint mismatch for a
  model field, pair provenance, and timestep, plus checkpoint-output
  transactionality.

Raw Rust bindings compile the public C11 header and C++ layout probes, exercise
the reused 80-byte options and 104-byte report layouts, and cover all raw
symbols. The safe Rust wrapper owns the native handle and exposes integration,
stable particle snapshots, absolute step, and canonical checkpoint
load/write.

## Immutable evidence

The generated profile and source manifest are:

- `config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1.json`
- `config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1_sources.json`

The manifest is canonical ASCII JSON with sorted unique path, byte-count, and
SHA-256 rows. It binds the owner, checkpoint, shared dynamics/provider,
stateless parents, public/export inputs, native tests, Rust ABI/runtime/vendor
copies, and this verifier. To keep the binding acyclic it excludes the
generated profile and manifest, unit consumer, this document, and workflow.

Normal verification is read-only:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py
```

Only after all bound sources are stable may evidence be regenerated explicitly:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py --refresh
```

Refresh stages both files, fsyncs them, atomically replaces them, runs complete
post-write verification, and restores both originals on any commit or
verification failure. Fault-injection tests cover partial replacement,
post-write failure, base exceptions, failed rollback, symlink ancestors, and
temporary-cleanup failures.

## Frozen predecessor

The verifier binds the reviewed PR #437 stateless composite evidence:

- reviewed head `454bb9ee6cdb4202cecbc807f78503ce842bdd13`;
- squash merge `f2731176fb913f600349ec6a1fbf3678d399a7c1`;
- exact tree `6017cf05e3f437443371966775bb4deb3fc73cab`;
- profile SHA-256
  `31dc3535d915980b1a7c318839162a4ce62d6a8bbf221b3415a67a98677d57e7`;
- 73-input manifest SHA-256
  `53267e95900402f60f4aba13a674e0e9530291d68310765d1a35a17146bf6afb`.

The merge must be an ancestor of HEAD. Historical profile and manifest bytes
are read directly from the merge object. The current frozen `engine.h`,
`direct_ewald.h`, `direct_ewald_composite.h`, and legacy
`native/src/dynamics/checkpoint.cpp` must also be byte-identical to their
predecessor blobs.

## Claim and execution boundary

All 15 authority fields remain false. The controlling blockers remain
`external_reservation_provider_not_operational`,
`external_reservation_endpoint_not_configured`,
`external_reservation_trust_anchor_not_configured`, and
`historical_execution_operational_authority_false`; 32 operational decisions
remain unresolved.

This CPU-only exact-neutral synthetic slice grants no reservation, molecular
A/B, D1/D2, Stage 0, Fresh-128, public benchmark, molecular execution,
scientific, acceleration, performance, product, or HIP-device authority. It
does not invoke or rerun the consumed native fixed64 CPU-v7 qualification and
does not install or launch the root supervisor.

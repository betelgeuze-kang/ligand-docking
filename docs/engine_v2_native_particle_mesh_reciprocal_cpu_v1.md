# Engine V2 native particle-mesh reciprocal CPU ABI v1

This Issue #434 development slice places the independently frozen scalar
particle-mesh reciprocal semantics from PR #439 behind a separately versioned
native CPU boundary. It remains reciprocal-space only. It is not a complete
PME method and does not add real-space, self, pair-correction, total-energy,
virial, timing, dynamics, or checkpoint composition.

The public C header is
`include/betelgeuze/particle_mesh_reciprocal.h`. Its ABI identity is 1.0.0,
its model profile is `betelgeuze.native_particle_mesh_reciprocal/1.0.0`, and
its ELF version node is `BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1.0`. The frozen
node derives directly from `BETELGEUZE_ENGINE_1.21`, not from the independent
direct-Ewald composite or dynamics chain. Engine ABI 1.21 and SOVERSION 1 stay
unchanged. The public ABI exports exactly
13 new symbols: four version queries, four transactional descriptor
initializers, model create/destroy/count/profile operations, and one context
evaluation entry point. Private `bg_rust_particle_mesh_reciprocal_*` provider
symbols must not enter the shared-library export set.

The immutable model owns atom count, canonical unit, orthorhombic cell,
Ewald alpha, three power-of-two mesh dimensions, and dielectric. It does not
own or borrow caller coordinate or charge storage. Creation validates the
frozen numeric and work envelope before allocation and commits a handle only
after success. Evaluation borrows the existing Engine context and system,
validates count/unit/channel compatibility, and commits reciprocal energy,
force channels, and force count only after the selected lane succeeds. A null
force descriptor selects the energy-only path.

## Frozen reciprocal semantics

Both CPU lanes implement cardinal B-spline order 4 with z-fast mesh indexing,
particle/x/y/z spreading order, separable z/y/x radix-2 transforms, a negative
representative for even-grid Nyquist modes, analytic assignment-derivative
forces, exact-neutral compensated charge validation, and the PR #439 checked
work cap:

`M * (1 + log2(Nx) + log2(Ny) + log2(Nz)) + P * 4^3 * 4 <= 16,000,000`.

The Rust lane independently ports the frozen scalar arithmetic order and pinned
`libm` transcendental behavior. It must reproduce the parent fixture energy
and twelve force components bit-for-bit. The C++ lane is a separate
implementation using strict non-contracting floating-point compilation. It is
bitwise repeatable within its own lane and is compared to the oracle and Rust
lane with the evidence-bound mixed tolerance
`abs(a-b) <= 5e-12 + 5e-12 * max(abs(a), abs(b))`; cross-language exact-bit
identity is not claimed.

Modes whose raw Gaussian damping underflows use the same common `2^256`
spectrum scale and log-domain rescue as the parent oracle. Regular and rescued
energy lanes are combined in the scaled domain before one final downscale.
The energy-only path may omit the inverse transform, derivative grid, and
gather, but it preserves the same spread and reciprocal energy arithmetic.

The public typed error range is 0 through 10: none, empty system, capacity,
charge-count mismatch, nonfinite coordinate, nonfinite charge, non-neutral
system, invalid cell, invalid parameter, invalid mesh, and nonfinite result.
Capacity maps to `BG_STATUS_CAPACITY_OVERFLOW`; non-neutral and nonfinite
result map to `BG_STATUS_NUMERICAL_ERROR`; other typed input failures map to
`BG_STATUS_INVALID_ARGUMENT`. ABI, null, alias, buffer, backend, allocation,
and internal failures retain an untyped code. Valid error output is cleared at
call entry, and all descriptors and output channels remain byte-transactional
on failure.

Only `BG_BACKEND_CPP_CPU_REFERENCE` and `BG_BACKEND_RUST_CPU` are accepted.
AUTO and both HIP backends fail closed before device, runtime, backend-state,
or output access and never fall back to CPU. This slice does not modify HIP
sources or execute a HIP device.

The raw Rust system crate mirrors the C layout, runs C11 and C++ layout probes,
and compiles byte-identical vendored copies. The safe runtime model is a
single-owner, non-`Send`, non-`Sync` handle whose `Drop` destroys exactly once.
It also guards and destroys an abnormal non-null handle returned with a failing
create status. The safe runtime's force-reservation and native untyped OOM
paths use borrowed static diagnostics, so reporting those OOM statuses does not
attempt another allocation. This narrow guarantee does not cover typed or
non-OOM diagnostic materialization.

## Immutable evidence

The canonical profile and sorted source manifest are:

- `config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1.json`
- `config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1_sources.json`

Normal verification is read-only:

```bash
python3 tools/verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py
```

After an intentional source change, `--refresh` rewrites only the canonical
source manifest and its profile count/hash binding. Ordinary verification
fails closed on source-byte, source-path, vendor-copy, parent-oracle, ABI,
authority, or blocker drift.

The parent PR #439 binding is exact:

- reviewed head `62d309c82aab9b4cfa45c4c3e6d11c93b3bd3786`
- merge commit `ebbd7a20538cfd7516d9b53adb2e54c6de14bd97`
- merge tree `2ae92801369c7e16147e07cbb16e19c062e52cc9`
- profile SHA-256 `d867651e8d6ce0ec1ead0c0e22dc684b4a0b6247ee35f2bcc9e17105f4c244d3`
- 22-input manifest SHA-256 `da6d669c85d63236936ba1f1324937b90e7cf57cc6dd58b16ab7d43d6278b296`
- scalar source SHA-256 `9579d213ec47fc75f70dbb4df76ff951de4a51518dc9216233c663a3e43e53c4`
- FFT source SHA-256 `e65c2a4f3837ae25ce32883671462120c6a2ac9af60c27bbe78e92d502c58c01`
- frozen fixture SHA-256 `669e4409ba56897061976c38fbf53985fb1f744e8e5b3613512b0f957951deef`
- standalone lock SHA-256 `98d90148a16d2a7fcf20b27a0cc9ab570c47759c2666ea7a9a0193067c94d80`
- 31-line observation SHA-256 `899845a391e23da253a5f0e2bdb5a78794ec7beb4dabee1f04726d6af1492144`

## Claim boundary

The profile keeps `full_pme_implemented=false`. It grants no scientific,
accuracy-at-scale, performance, acceleration, product, qualification,
reservation, molecular-execution, D1/D2, Stage 0, Fresh-128, public-benchmark,
supervisor-operation, or HIP-device authority. The four external operational
blockers and 32 unresolved operational decisions remain controlling. The
consumed native fixed64 CPU-v7 qualification is not invoked or rerun.

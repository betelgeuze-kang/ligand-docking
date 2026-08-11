# HIP safe provider

`hip_safe` is the deterministic ROCm qualification lane for the native compute
ABI. It uses binary64 arithmetic, a fixed serial device accumulation order,
explicit kernel completion, no floating-point atomics, no fast-math flags, and
no CPU fallback. The initial provider intentionally favors auditability over
throughput. The separately selected `hip_fast` lane preserves the existing
persistent-context, batched parallel implementation, but it remains
non-authoritative until parity against `rust_cpu` and `hip_safe` is frozen for
each qualified GPU architecture.

The first qualified toolchain is ROCm 6.0.2 / HIP 6.0.32831 on `gfx1030`.
The trusted qualification workflow materializes device libraries from the
matching AMD package
`rocm-device-libs_1.0.0.60002-115~22.04_amd64.deb` whose frozen package SHA-256
is `02feb9e107c7b3c567e73bab6671c3c67c94376cb1e93dd598f069e961f6ea81`.
The repository's legacy ROCm 5.7.1 bitcode fallback is intentionally never
searched or accepted by this provider.

The native fixed64 docking slice now covers Scorer v1, pose validity, stable
Top-K/direct-RMSD clustering, and bounded torsion V7 in both `hip_safe` and
`hip_fast`. Torsion V7 keeps the receptor/topology context resident on the
selected device, evaluates all 64 candidate rows without denominator deletion,
returns typed per-row failures and complete move/coordinate evidence, and
leaves molecular execution, rank mutation, pose emission, and claim authority
false. The C++ reference and Rust CPU providers remain independent parity
oracles; no HIP error may select either provider as a runtime fallback.

ABI 1.11 also executes ScorerV1 -> pose validity -> stable Top-K through one
persistent downstream handle on `hip_safe` or `hip_fast`. The host boundary
derives the exact scorer-failure binding and canonical coordinate identities;
all three device stages must succeed before any caller output is committed.
The gfx1030 suite compares the complete composed result with `rust_cpu` and
requires bit-identical repeated device runs.

Builds without a complete ROCm compiler/runtime link a fail-closed stub and
report the backend unavailable. A compiled provider still reports unavailable
unless the requested device ordinal is visible to the HIP runtime. Synthetic
device parity does not authorize molecular execution, benchmark publication,
Stage 0 admission, or product claims.

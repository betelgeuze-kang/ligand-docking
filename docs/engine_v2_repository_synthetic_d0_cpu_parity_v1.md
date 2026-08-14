# Repository synthetic D0 native CPU parity v1

This contract closes the previously explicit numeric-parity gap for the repository-owned synthetic D0 fixed64 session. The native Rust owner materializes the same 64-slot input, creates one persistent `cpp_cpu_reference` context and one persistent `rust_cpu` context, runs each context twice without timing, and compares their backend-independent scientific projections.

The comparison is complete over all 16,896 binary64 values in the projection: proposal and final coordinate states, geometric measurements, rigid and torsion objectives, all eight `ScorerV1Terms`, validity measurements, ranking scores, cluster RMSD, and final quaternions. Absolute tolerance is `1e-11` and relative tolerance is `4e-12`, matching the already-frozen CPU V7 numeric contract. Non-finite values fail closed. Denominator, stage counts, typed failures, status, validity masks, stable ranks, V7 selection, and source/allocation identities require exact parity through the backend-independent decision receipt.

Backend-bound receipt hashes and coordinate SHA-256 identities are not required to match. They deliberately bind provider-specific execution and bitwise coordinates; the receipt preserves their distinct identities and reports how many final coordinate identities are equal or different. Numeric tolerance, exact decision parity, and source identity parity remain mandatory.

The native entrypoint is `native_fixed64_repository_synthetic_d0_cpu_parity_v1`. It accepts only the exact synthetic-only acknowledgment and no caller science input. Python independently validates the closed schema and rederives the native parity receipt. The standalone surface exposes the same operation as:

```text
betelgeuze-dock verify \
  --repository-native-d0-cpu-parity \
  --test-only-synthetic \
  --output parity.json
```

This is an untimed, repeatable synthetic development gate. It does not call or reopen the consumed exactly-once CPU V7 qualification, does not measure performance, and grants no reservation, molecular execution, historical A/B, Fresh-128, public benchmark, Stage 0, scientific claim, product-performance claim, or HIP device authority. GitHub Actions remains test infrastructure only and receives no production authority.

External authority must reach blocker zero before any reservation or molecular execution. This receipt cannot be used as Stage 0 admission, a public benchmark, a molecular-science result, or a HIP parity claim.

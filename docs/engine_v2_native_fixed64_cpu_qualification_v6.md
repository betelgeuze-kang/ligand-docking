# Engine V2 native fixed64 CPU qualification v6

Profile v6 activates an account-scoped, exactly-once runner around the frozen
native fixed64 CPU measurement graph. It changes execution control and durable
evidence publication only. The v5 candidate graph, two synthetic fixtures,
64-slot denominator, ScorerV1/validity semantics, numeric tolerances, AB/BA
sampling, persistent contexts, and development-only performance gate are
unchanged.

The profile is
`config/engine_v2_native_fixed64_cpu_profile_v6.json`. Its exact SHA-256 is
`839f2f3a91ea2aeddfae2c02559a2f37ab550967318932ff6375d6f723de14c2`.
The 190-input native/Rust compiler manifest is
`config/engine_v2_native_fixed64_cpu_profile_v6_sources.json`, SHA-256
`439fd9e44057771808a3a0a6142c50d10d2b75739d61d2b6712b812f4530cf36`.

## Transaction boundary

The native binary accepts exactly one of three operations:

```text
betelgeuze-fixed64-cpu-qualify-v6 --verify-activation
betelgeuze-fixed64-cpu-qualify-v6 --preflight
betelgeuze-fixed64-cpu-qualify-v6 --run-output ABSENT_OWNER_JSON
```

Activation verification and preflight are non-consuming. The live operation is
not run by GitHub Actions and accepts no caller-supplied fixture, probe,
configuration, or molecular input. Its fixed sequence is:

1. reject GitHub Actions and verify the compile-bound activation;
2. bind an absolute, absent output under an owner-controlled directory;
3. open the login account's no-follow profile state directory;
4. create `attempt.json` with `O_EXCL` before host preflight;
5. require exact clean `main`, the frozen Ryzen 5900X host identity, disabled
   boost, CPU ordinal 2, and one process task;
6. pin the process and run the fixed 5-warmup/25-sample native C++/Rust graph;
7. publish the single owner-only artifact without replacement;
8. bind the attempt and artifact into an absent-only `terminal.json`;
9. return a decision only after re-reading the persisted terminal.

Any process loss after the attempt marker burns the profile. A blocked
preflight is recorded as a terminal `BLOCKED` result; it is not retried under
the same profile. Artifact, terminal, or output collisions fail closed.

## Evidence and authority

Each fixture records the exact payload identity, C++ and Rust decision and full
projection identities, all 25 timing samples, medians, numeric comparison
counts and maxima, generated/failure counts, repeat stability, and the frozen
64-slot denominator. The fixed payload plus the bound 190-source compiler
manifest makes the ScorerV1 terms, validity measurements, coordinate states,
refinement objectives, ranks, and typed failures rederivable from the same
native graph.

Execution never grants qualification, scientific, product-performance, public
benchmark, Stage 0, Fresh-128, reservation, molecular, or HIP authority. A
passing local synthetic gate remains development evidence only.

GitHub Actions runs only the independent static verifier and test-realm unit
transactions:

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py
python3 -m pytest -q \
  tests/unit/test_verify_engine_v2_native_fixed64_cpu_profile_v6.py
```

After the one allowed execution, the persisted files are independently checked
without rerunning the measurement:

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_v6_evidence.py \
  --artifact /absolute/owner/result.json \
  --attempt /home/ACCOUNT/.betelgeuze-engine-v2/native-fixed64-qualification/PROFILE_SHA/attempt.json \
  --terminal /home/ACCOUNT/.betelgeuze-engine-v2/native-fixed64-qualification/PROFILE_SHA/terminal.json
```

That verifier rederives all three domain-separated receipts, the exact output
path binding, profile and activation identities, the 25-sample timing
denominators and medians, fixture and numeric gates, the false-authority maps,
and the terminal's raw attempt/artifact bindings. It reports structural
integrity only and cannot grant qualification authority.

The consuming `--run-output` operation must not be invoked until this
activation is reviewed and merged, an exact clean `main` checkout passes the
non-consuming preflight, and an explicit execution review confirms that the
account-scoped state directory is absent. This activation does not alter the
external-authority blockers and does not authorize the historical molecular
A/B, Fresh-128, public benchmarking, or HIP device execution.

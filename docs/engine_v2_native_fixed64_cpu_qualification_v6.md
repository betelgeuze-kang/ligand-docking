# Engine V2 native fixed64 CPU qualification v6

Profile v6 activates an account-scoped, exactly-once runner around the frozen
native fixed64 CPU measurement graph. It changes execution control and durable
evidence publication only. The v5 candidate graph, two synthetic fixtures,
64-slot denominator, ScorerV1/validity semantics, numeric tolerances, AB/BA
sampling, persistent contexts, and development-only performance gate are
unchanged.

The profile is
`config/engine_v2_native_fixed64_cpu_profile_v6.json`. Its exact SHA-256 is
`fd83f1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928`.
The 193-input native/Rust compiler manifest is
`config/engine_v2_native_fixed64_cpu_profile_v6_sources.json`, SHA-256
`988108202cceafff669930f804a8bc292ec2a364dd8c016bd9d4b7ecdb190f45`.
The domain-bound activation SHA-256 is
`76db91350dc5859fe56f03fb9d49685a1539567a27c3aeaa00f001b10082ea56`.
The independently hashed frozen build configuration is
`792702860fdbc1a9d7b75c2b3fb3cba1f4ffb79b5d66350a6fe8546bd68dd2fd`.

The standalone `betelgeuze-runtime` crate packages byte-identical mirrors of
the profile, predecessor archive, source manifest, original pre-normalization
Cargo manifest, and workspace lock under
`rust/betelgeuze-runtime/assets/`. Both the profile verifier and CI authority
audit reject any mirror drift; packaging the mirrors grants no execution or
qualification authority.

Git-less manylinux extension-wheel builds must opt into the explicit
`BETELGEUZE_V6_NON_AUTHORITATIVE_PACKAGE_BUILD=1` compile mode. That mode still
verifies the complete frozen source graph and packaged profile bytes, but
embeds `build_commit_bound=false`; every v6 activation entry point therefore
fails closed. Ordinary debug, release, test, package, and CI builds also embed
an unbound build configuration and cannot activate. An authoritative local
qualification build must explicitly opt in and use the frozen Cargo profile:

```bash
qualification_source_root="$(pwd -P)"
env -u HIP_PATH -u ROCM_PATH \
  BETELGEUZE_V6_QUALIFICATION_BUILD=1 \
  RUSTC_WRAPPER="${qualification_source_root}/tools/verify_engine_v2_native_fixed64_cpu_v6_rustc_wrapper.py" \
  cargo build --locked --profile qualification-v6 \
  --manifest-path rust/Cargo.toml \
  -p betelgeuze-runtime \
  --bin betelgeuze-fixed64-cpu-qualify-v6
```

The build fails unless the exact Rust 1.93.0 toolchain, GNU C++ 11.4.0 binary,
x86_64 target, target features, panic/optimization profile, explicit strict-FP
C++ flags, and absence of environment flag overrides all match the frozen
configuration. The source-bound wrapper additionally checks the effective
codegen and cfg arguments received by every controlled Rust crate. Cargo 1.93
may omit an explicit library `linker-plugin-lto` option from some dependency
invocations while supplying it to others. The wrapper first rejects every
caller-supplied extra `-C` option, accepts at most one valueless Cargo-supplied
library LTO option, and injects it only when absent. The effective rustc
invocation therefore always contains exactly one library LTO mode.
The final binary must still receive `lto=fat` directly from Cargo. The wrapper
rejects Cargo CLI profile overrides, appended `cargo rustc` codegen/cfg options,
unstable options, a substituted wrapper or interpreter, and any invocation that
does not match the frozen library/binary LTO split. Non-compilation rustc calls
are limited to exact `-vV` and `--version` identity queries needed by Cargo and
dependency build scripts. GitHub Actions is statically
forbidden from setting the qualification-build opt-in. The build must also bind
the exact Git commit plus its committed profile and source-manifest blobs.

The crate build script verifies every one of the 193 manifest rows against the
actual checkout used for compilation and embeds the verified manifest identity
and source count. Packaged verification therefore requires an exact source root
through `BETELGEUZE_V6_SOURCE_ROOT`; a package cannot silently substitute a
normalized manifest or compile stale transitive sources and remain activatable.
The verified canonical source root is embedded into the binary, so packaged
preflight and post-measurement checks return to the same exact checkout rather
than Cargo's normalized package staging directory.
The build also reads the exact profile and source-manifest blobs from the Git
commit, rejects worktree substitutions, and embeds that commit plus the profile
digest. Runtime activation requires the embedded profile digest, and preflight
requires the source checkout to remain at the exact build commit.
Authoritative builds track the worktree `HEAD`, its symbolic branch ref, and
`packed-refs` as Cargo build-script inputs, so even a source-identical commit
advance refreshes the embedded build identity without requiring `cargo clean`.

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
7. revalidate exact source, model, boost, task count, and CPU affinity after
   measurement;
8. publish the single owner-only artifact without replacement;
9. bind the attempt and artifact into an absent-only `terminal.json`;
10. return a decision only after re-reading the persisted terminal.

Any process loss after the attempt marker burns the profile. A blocked
preflight is recorded as a terminal `BLOCKED` result; it is not retried under
the same profile. Artifact, terminal, or output collisions fail closed.

## Evidence and authority

The attempt, artifact, and terminal each persist and cross-bind the frozen
build-configuration SHA-256. Each fixture records the exact payload identity,
C++ and Rust decision and full
projection identities, all 25 timing samples, medians, numeric comparison
counts and maxima, separate C++ and Rust generated/failure counts, repeat
stability, and each backend's frozen 64-slot denominator. The fixed payload
plus the build-verified 192-source compiler
manifest makes the ScorerV1 terms, validity measurements, coordinate states,
refinement objectives, ranks, and typed failures rederivable from the same
native graph.

Execution never grants qualification, scientific, product-performance, public
benchmark, Stage 0, Fresh-128, reservation, molecular, or HIP authority. A
passing local synthetic gate remains development evidence only.

GitHub Actions runs only the independent static verifier, test-realm unit
transactions, and a normalized package `--verify-activation` rejection check:

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
and the terminal's raw attempt/artifact bindings. It also requires a clean,
exact trusted source checkout, compares its `HEAD` and critical committed
verifier/profile blobs, and binds every non-null artifact source commit to that
exact build identity. It reports structural integrity only and cannot grant
qualification authority.

The consuming `--run-output` operation must not be invoked until this
activation is reviewed and merged, an exact clean `main` checkout passes the
non-consuming preflight, and an explicit execution review confirms that the
account-scoped state directory is absent. This activation does not alter the
external-authority blockers and does not authorize the historical molecular
A/B, Fresh-128, public benchmarking, or HIP device execution.

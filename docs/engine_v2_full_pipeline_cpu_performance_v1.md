# Engine V2 full-pipeline CPU performance v1

This contract freezes an implementation profile for a future private,
synthetic comparison of the complete fixed64 CPU pipeline. It does not execute
or consume that comparison.

## Exact runtime input

The profile selects the successful main-push cp310 artifact produced by release
workflow run `31785070195`, attempt `1`, at main commit
`3330faa43c7fc8640d89babd84ac444c5959157c`. The selected GitHub artifact is
`9213296947`, and the profile binds its API digest, wheel, SPDX-2.3 SBOM, all
five wheel members, installed site-packages inventory, CPython 3.10 executable,
shared library, virtual-environment configuration, and native extension.

The native extension SHA-256 is
`ff7b5e6ba7c0e250cf739292d34c562d0bd142d5f7f6c842c5c191d42b2504e1`.
The verifier may inspect an owner-controlled local copy, but it does not import
the extension, launch a pipeline, start a timer, reserve an attempt, or write a
result.

```bash
python3 tools/run_engine_v2_full_pipeline_cpu_performance_v1.py \
  --verify-local-runtime \
  --artifact-directory /owner-controlled/exact-artifact \
  --runtime-root /owner-controlled/exact-cp310-runtime
```

## Predecessor disposition

The geometric-kernel v3 profile expected native extension
`a07ca2276277cd610450d45d09f5b9789a69580747f61c6c9867640b07164a55`,
but its exact runtime artifact is unavailable. Its account-scoped attempt and
terminal files were absent when this successor was frozen. This profile does not consume the predecessor v3 attempt. It also does not reconstruct its runtime,
rerun it, or reinterpret a predecessor result.

## Frozen measurement boundary

The future workload is the repository-owned synthetic D0 fixed64 source only.
It accepts no caller science input and uses two persistent prepared sessions:

- baseline: `cpp_cpu_reference`
- experimental: `rust_cpu`

Session construction is outside the timed boundary. Each timed call is
`NativeRepositorySyntheticD0PreparedSessionV1.run(surface="benchmark")`, which
includes the proposal, geometric admission, V7 refinement, complete eight-term
ScorerV1 evidence, validity, ranking, receipt materialization, and Python
evidence validation. Scientific results are never cached.

The frozen schedule has five warmups and 30 samples per backend with alternating
AB/BA order. Wall and process clocks are both recorded. P50 and P95 values are
descriptive private development evidence. No speed threshold exists in this
profile; parity, evidence completeness, denominator preservation, positive
durations, and schedule completeness are the gates.

## Activation boundary

The implementation profile has no live execution capability. A separate activation PR must bind the exact merged main commit and tree, profile,
verifier, measurement core, runner, native consumer, CPU parity implementation,
host preflight, standard-library import closure, and loaded dynamic-library
closure. Only that later review may create one account-scoped synthetic attempt.

GitHub Actions remains verification-only. Test doubles exercise schedule and
failure behavior but have no production or qualification authority. The
following remain false: reservation, molecular execution, historical A/B,
Fresh-128, public benchmark, product execution or claims, Stage 0 admission,
and HIP device execution.

Static verification is non-consuming:

```bash
python3 tools/verify_engine_v2_full_pipeline_cpu_performance_v1.py
python3 tools/run_engine_v2_full_pipeline_cpu_performance_v1.py \
  --verify-implementation
```

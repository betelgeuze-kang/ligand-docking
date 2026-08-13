# Engine V2 native fixed64 CPU v7 execution result

The one account-scoped synthetic execution for profile v7 is consumed. It ran
from clean `main` commit `5c1e4791e988d4c75a5111f933feac85236ba821` after
exact-head review, merge, activation verification, non-consuming preflight, and
an absent state check. The terminal decision is `PASS`.

This is synthetic CPU parity and development-gate evidence only. It contains no
molecular case, creates no external reservation, and grants no qualification,
product-performance, scientific, public-benchmark, Stage 0, Fresh-128, rank,
allocation, or HIP authority. The compact receipt therefore records the result
as `recorded_pass_non_authoritative`, keeps every authority and claim flag
false, and preserves the four unresolved external-authority blockers observed
after execution.

## Frozen evidence

- compact receipt SHA-256:
  `f653185c2bfc7642e2d9e73b918a2e0a9c14c0e107f5804799e140bb42c34b82`
- attempt raw SHA-256:
  `8d51c9e74fe39ecfcd5f799ca3c8c064b6638cda1c8487d84995dcb7fc357802`
- artifact raw SHA-256:
  `a850247353a90e7ce417a16ba8041872c90a9a849b95b0102c2359a8fa75330b`
- terminal raw SHA-256:
  `0febcf69013e28bfa428573bbe9b49550b7b2f9d5b64df5004d7645a1b0831f6`

The 3,029,064-byte raw artifact remains owner-only evidence outside Git. The
repository receipt stores its exact byte count, raw identity, embedded receipt
identity, source/profile identities, run nonce, output-path identity, host
invariants, and all compact fixture results. The raw files remain necessary for
full re-verification; the compact receipt is not a substitute for them.

## Recorded fixture results

| Fixture | Slots | Generated / typed failure | C++ median | Rust median | Rust/C++ | Compared f64 | Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `synthetic_complete_64` | 64 | 64 / 0 | 61,780,433 ns | 35,181,952 ns | 0.569468 | 28,544 | 0 |
| `synthetic_feature_sparse_48_plus_16` | 64 | 48 / 16 | 45,719,698 ns | 18,572,880 ns | 0.406234 | 28,544 | 0 |

Both fixtures preserve the 64-slot denominator, eight ScorerV1 terms,
generated/failure counts, repeated-run decision stability, C++/Rust decision
parity, full numeric tolerance, and independently rederivable lane-metrics
decision parity. One persistent C++ context and one persistent Rust context were
used per fixture.

## Verification

Static CI verification does not need or consume the raw artifacts:

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py
```

The owner-controlled host can additionally bind the compact receipt back to
all three original files. These arguments are intentionally all-or-none:

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.py \
  --artifact /absolute/owner-only/artifact.json \
  --attempt /absolute/account-scoped/attempt.json \
  --terminal /absolute/account-scoped/terminal.json
```

The verifier reuses the independent v7 evidence verifier to reconstruct the
complete scientific projection and lane evidence before comparing every compact
field. It never invokes the qualification runner. The consumed execution must
not be repeated.

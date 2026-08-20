# Engine V2 sampling-pool synthetic CPU observation v1

`betelgeuze-sampling-pool-observe-v1` is a non-authoritative development tool
for the source-bound native 512-row producer. It does not accept molecular,
historical, D1, Fresh-128, benchmark, product, or customer-pose input.

The three compiled fixtures are synthetic-only and freeze these generated work
denominators:

| fixture | ligand atoms | receptor atoms | generated rows | exact pairs |
| --- | ---: | ---: | ---: | ---: |
| small | 8 | 64 | 512 | 262,144 |
| medium | 24 | 256 | 512 | 3,145,728 |
| large | 48 | 512 | 512 | 12,582,912 |

Every fixture contains compatible single- and dual-anchor source geometry. The
tool freezes the exact producer receipt for each fixture and verifies a second
execution before any observation is considered usable.

## Static fixture verification

```bash
cargo run --release -p betelgeuze-docking-search \
  --bin betelgeuze-sampling-pool-observe-v1 -- --verify-fixtures
```

This operation reads no clocks and emits only deterministic fixture identities,
denominators, and all-false authority state. It is safe for ordinary tests.

## Local descriptive observation

```bash
cargo run --release -p betelgeuze-docking-search \
  --bin betelgeuze-sampling-pool-observe-v1 -- --observe 7
```

The parent launches a fresh child process for every fixture/sample pair. Fixture
construction is outside the timed boundary; the wall clock covers only
`produce_native_sampling_pool(...)`. Linux `VmHWM` is read immediately before
and after that call, and the receipt retains both absolute process peak RSS and
the largest observed increase. Wall-time p50/p95 use nearest-rank integer
selection and retain every raw nanosecond sample.

Timing mode fails closed in GitHub Actions. Results have no threshold and no
baseline comparison: wall time and peak RSS are descriptive local development
observations only. They cannot authorize or support molecular execution,
reservation, D1/Fresh-128, public benchmarks, Stage 0, HIP-device execution,
product/rank/customer-pose mutation, or performance/scientific claims.

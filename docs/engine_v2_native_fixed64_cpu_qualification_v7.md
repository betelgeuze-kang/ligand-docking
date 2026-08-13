# Engine V2 native fixed64 CPU qualification v7

Profile v7 is the non-consuming successor to the frozen v6 implementation. It
keeps the v6 synthetic candidate graph, two fixture payloads, fixed 64-slot
denominator, ScorerV1 terms, validity semantics, numeric tolerances, AB/BA
sampling, persistent contexts, and development-only performance gate unchanged.
Its only scientific change is downstream, rederivable fixed64 lane and oracle
selection evidence. It does not change proposal allocation, ranking, validity,
or any returned candidate.

The current frozen identities are:

- profile: `engine_v2_native_fixed64_cpu_synthetic_v7`
- profile SHA-256: `50c3e609a23e3bf0641a900f71dc360dcadc1a52c3bde66cdfa74b8c1affcd5d`
- 196-source manifest SHA-256: `ecb009ac228652c6c6cbdefcdd70828ce3d9aeea5a5e31d0fff0246d4d5f932e`
- build-configuration SHA-256: `6e39e4e07bcb2f9324f242adcf3f48428191b2a91418d34520c6acc1cf046068`
- activation SHA-256: `7d86f8aaa4392ed0bf540c698245e9122dbf4630d6eaab893592d94c927b0d84`
- predecessor archive SHA-256: `efb3efd0d863fb6797e9651bf7ba5ef63ab7eb09d5bcc3eef947b7fcd4709551`

The canonical profile and source manifest have byte-identical packaged mirrors
under `rust/betelgeuze-runtime/assets/`. The verifier rejects mirror drift,
source-manifest drift, predecessor substitution, unexpected candidate-graph or
fixture changes, and any authority escalation.

## Lane evidence contract

Every fixture produces exactly 64 lane observations and exactly 10 lane
summaries. Typed proposal or geometric failures remain observations in the
denominator with their exact failure code; they are never deleted to improve a
metric. Each generated observation binds the complete scientific projection,
candidate identity, proposal lineage, coordinates, score terms, validity,
rankability, geometric measurements, refinement decision, and failure state.

The reference receipt binds the synthetic case identity, source receipt,
prepared topology, reference coordinates, heavy-atom mask, and a canonical,
unique symmetry-permutation list that includes identity. Oracle RMSD is the
minimum symmetry-aware direct heavy-atom RMSD without alignment, using an exact
2.0 angstrom threshold and at most 1,024 permutations. Quaternion orientation
identity canonicalizes `q` and `-q` to one representation.

For each fixed lane, the receipt records and rederives:

- generated and typed-failure counts;
- unique coordinate and orientation counts plus duplicate rate;
- severe-penetration count and rate;
- exact-valid contribution;
- symmetry-aware oracle contribution and incremental case recovery;
- valid-pose cluster count from the pipeline's predeclared 1.5 angstrom
  direct-RMSD clustering threshold;
- candidate entropy from the frozen integer lookup;
- the eight declared conformer-by-independent-orientation pairs.

The lane receipt carries separate full and decision SHA-256 identities. Each
backend persists the canonical scientific-decision preimage, all 28,544
canonical big-endian `f64` values, the ordered 12,288-byte coordinate/proposal
digest stream, complete labeled eight-term ScorerV1 and validity rows, and the
full lane receipt. The independent Python verifier hashes the decision preimage,
reconstructs the complete scientific-projection SHA-256 from those numeric and
digest streams, cross-binds the labeled score and validity evidence, and then
rederives every observation, summary, pair interaction, oracle result, and lane
receipt hash. Decision receipts contain the discrete scientific decisions that
must be byte-identical between the C++ CPU reference and Rust CPU backend. Lane
metrics explicitly carry `authority=false`, `rank_mutated=false`, and
`result_dependent_allocation=false`.

## Build and transaction boundary

Git-less wheel packaging uses only the explicit non-authoritative mode
`BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1` plus an exact
`BETELGEUZE_V7_SOURCE_ROOT`. That mode verifies the frozen source graph but
embeds an unbound commit and rejects activation. Ordinary local and CI builds
also reject activation.

An authoritative synthetic qualification binary can only be compiled from the
exact committed source with the frozen toolchain and flags:

```bash
qualification_source_root="$(pwd -P)"
env -u HIP_PATH -u ROCM_PATH \
  BETELGEUZE_V7_QUALIFICATION_BUILD=1 \
  RUSTC_WRAPPER="${qualification_source_root}/tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py" \
  cargo build --locked --profile qualification-v7 \
  --manifest-path rust/Cargo.toml \
  -p betelgeuze-runtime \
  --bin betelgeuze-fixed64-cpu-qualify-v7
```

The binary exposes only `--verify-activation`, `--preflight`, and an owner-only,
absent-path `--run-output`. Activation verification and preflight are
non-consuming. The runner rejects GitHub Actions, caller-supplied fixtures,
molecular inputs, symlinks, replacement writes, build/profile/source drift,
host drift, and post-measurement drift. It creates an account-scoped attempt
before host preflight, publishes artifact and terminal with absent-only atomic
writes, and returns a decision only after re-reading the persisted terminal.

GitHub Actions may run static profile/evidence verification and must prove that
both the v6 archive and v7 active profile remain non-authoritative. It must never
set `BETELGEUZE_V7_QUALIFICATION_BUILD`, invoke `--run-output`, or treat a test
double as production authority.

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py
python3 tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py
python3 tools/verify_engine_v2_native_fixed64_cpu_v7_evidence.py --help
```

Profile v7 contains only synthetic data. It grants no qualification,
scientific, product-performance, public benchmark, Stage 0, Fresh-128,
reservation, molecular, rank-mutation, allocation-mutation, or HIP authority.
The consuming synthetic run remains separate from molecular execution and is
permitted only after exact-head review, merge, clean-main preflight, and an
absent account-scoped state check.

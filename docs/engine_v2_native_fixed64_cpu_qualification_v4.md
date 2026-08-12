# Engine V2 native fixed64 CPU qualification v4

Profile v4 qualifies the complete native fixed64 candidate graph rather than
the predecessor's one-candidate Python geometric-kernel sidecar. The frozen
profile is
`config/engine_v2_native_fixed64_cpu_profile_v4.json` and its measurement core
is the Rust binary `betelgeuze-fixed64-cpu-probe-v4`.

The measured graph is:

1. fixed64 proposal generation;
2. geometric admission;
3. rigid and V7 torsion refinement;
4. all eight ScorerV1 terms;
5. pose validity;
6. stable Top-K;
7. direct-RMSD clustering.

## Frozen fixtures and denominator

Both fixtures retain exactly 64 slots. `synthetic_complete_64` supplies the
complete deterministic feature inventory and must generate 64 candidates.
`synthetic_feature_sparse_48_plus_16` intentionally omits the single-anchor
feature inventory and must preserve 48 generated rows plus 16 typed generation
failures. No failed slot is removed from the denominator.
Each fixture has exactly 12 receptor atoms and 12 ligand atoms; those counts,
the full and heavy-atom penetration counts, and placement/output proposal and
coordinate identities remain in the scientific projection.

The fixtures are compiled native constants. They contain no historical,
Fresh-128, customer, or other molecular-corpus case.

## Parity boundary

Native ABI receipts bind their backend and therefore are not compared directly
between providers. `Fixed64ScientificProjection` derives two independent
identities:

- `decision_sha256` excludes floating values and backend-bound receipts while
  covering lineage, all statuses and failure codes, pair/count evidence,
  validity masks, V7 selection, stable ranks, Top-1/Top-5 membership, clustering,
  the exact 64-slot denominator, and authority disposition;
- `sha256` additionally covers every coordinate state, quaternion, refinement
  objective, ScorerV1 term, validity measurement, torsion move, score, and RMSD.

The C++ reference and Rust CPU decision hashes must be identical. Every numeric
value is compared with the frozen absolute and relative tolerances. Repeated
runs of each backend must reproduce its full projection hash exactly.

## Persistent context and timing

Each fixture creates one C++ reference context/pipeline and one Rust CPU
context/pipeline. Context construction is outside the timed scope. The same
objects are reused for five warm-up rounds and 25 measured rounds in paired
AB/BA order. The development-only non-regression gate requires the Rust CPU
median divided by the C++ reference median to be no greater than 1.25.

This ratio is engineering evidence only. It does not authorize a product,
scientific, public benchmark, or acceleration claim.

## Execution state

The checked-in profile is frozen but unconsumed. CI may compile and unit-test
the measurement core and run the static profile verifier; CI must not execute
the 25-sample live profile. A later activation must bind an exact merged source,
native binary, toolchain, host preflight, absent-only output, and account-scoped
exactly-once state before the single local execution is consumed.

Until that activation is reviewed and merged:

- qualification authority remains false;
- reservation and molecular execution remain forbidden;
- HIP device execution remains forbidden;
- Fresh-128 and the historical A/B remain forbidden;
- no performance or acceleration claim may be made.

Static verification is non-consuming:

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_profile_v4.py
```

Do not invoke the native 25-sample binary from GitHub Actions or treat a unit
probe as the exactly-once qualification result.

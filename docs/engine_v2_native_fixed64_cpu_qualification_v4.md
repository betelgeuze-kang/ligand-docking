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

Each fixture also carries a domain-separated payload SHA-256 rederived from the
complete `Fixed64PipelineContext` and `Fixed64RunInput`, including every
coordinate and chemistry channel, topology, source receipt, feature geometry,
lane allocation, and refinement parameter:

- `synthetic_complete_64`:
  `8478682324df3bd10e5fa6e2988436cec4c59e815dcf3444eaf3009f1a373df5`;
- `synthetic_feature_sparse_48_plus_16`:
  `9c93753ae23363c20d2f957fb521eedd1fe4f92fc39282c03c53d1f2674610c2`.

The frozen JSON also binds the exact qualification, native probe, Rust pipeline,
and C++ pipeline implementation source SHA-256 identities. A 151-file canonical
and vendored transitive-source manifest additionally covers the native ABI and context,
proposal/admission/refinement/scorer/validity/ranking/clustering kernels, the
Rust CPU providers, the docking-search crate, Cargo manifests and lockfile, and
the vendored-native build binding. Changing a fixture literal, run-input
construction, any measured kernel, scoring/refinement/projection/receipt
behavior, build routing, dependency identity, canonical/vendor equality, or
guard-to-measurement control flow therefore fails static verification. Every
file exposed in the compiled native vendor tree is bound; extra and symlinked
vendor inputs fail closed. Runtime tests independently
rederive and compare the full payload digest.

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
the 25-sample live profile. The library owns one compile-bound
`activation_admitted = false` constant and rejects the frozen qualification
profile before fixture construction; without activation, only the exact
two-round unit-test profile is accepted, and arbitrary custom workloads are
rejected. The checked-in native binary independently checks that same library
gate before `qualification_profile()` and exits without constructing the
qualification configuration or calling the measurement core. A later activation
must bind an exact merged source, native binary, toolchain, host preflight,
absent-only output, and account-scoped exactly-once state before the single local
execution is consumed.

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

The verifier also reads the compiled Rust qualification gate, Rust receipt
domains, C++ pipeline constant, and native probe entry point. One pipeline
profile constant feeds every Rust receipt domain and is checked against the C++
ABI identity before pipeline construction. Verification fails if the profile
ID, complete fixture payload, source identity, denominator, fixture counts,
sampling, numeric tolerances, performance ratio, or guard-to-measurement order
drifts from the canonical JSON.

Do not treat any GitHub Actions or test-double invocation as the exactly-once
qualification result. The CI inventory deliberately makes no claim that a
static parser can prove the absence of an arbitrary invocation from every shell,
interpreter, action implementation, environment expansion, or runtime-generated
program. Such a claim is not an authority boundary.

The normative fail-closed boundary is instead explicit and independently
checked:

- the canonical profile fixes `qualification_authority`,
  `github_actions_live_qualification_allowed`,
  `github_actions_production_authority_allowed`, and
  `test_double_production_authority_allowed` to `false`;
- the public library API rejects the frozen qualification profile before fixture
  construction, while the checked-in binary checks the same compile-bound gate
  before constructing its configuration or calling the measurement core;
- the authoritative CI runs only the non-consuming exact-profile/source
  verifier and unit tests; it does not possess an admission path that can turn
  output into qualification evidence.

Consequently, invoking the canonical binary exits before measurement. Patching
source or configuration at workflow runtime changes the exact source/profile
identity and still cannot produce an admitted v4 receipt. A future activation
must be a separately reviewed, versioned contract that replaces this unconsumed
state and supplies its own exactly-once admission authority.

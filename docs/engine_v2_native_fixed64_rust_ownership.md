# Engine V2 Native Fixed64 Rust Ownership

This document is the reviewer map for the Rust wrapper around the native
fixed64 docking pipeline. It records source ownership only. It does not grant
execution, reservation, benchmark, scientific, performance, product, or HIP
device authority.

## Orchestration closure

`rust/betelgeuze-runtime/src/docking.rs` is the public module root and the
owner of `Fixed64Pipeline` construction and run orchestration. The closure
ceiling for the behavior-preserving split tracked in issue #331 is:

- at most 2,000 lines in `docking.rs`;
- at most two analyzer-visible top-level runtime items: the
  `Fixed64Pipeline` struct and impl;
- no scientific, receipt, FFI ownership, or validation algorithm implemented
  directly in the orchestration root.

The reviewed main tree after PR #407 has 1,709 lines and those two items.

## Ownership map

| Source | Owned boundary |
| --- | --- |
| `docking.rs` | Public exports plus `Fixed64Pipeline` construction and run orchestration. |
| `docking/types.rs` | Public fixed64 POD inputs, evidence, rows, receipts, enums, and conversions. |
| `docking/context.rs` | Molecular context cardinality, channel, topology, digest validation, and shared identity projection. |
| `docking/prepared_input.rs` | Run-input source validation, borrowed-to-owned independent projections, and canonical pocket-normal preparation. |
| `docking/coordinates.rs` | Shared coordinate-segment access, bitwise comparison, finite/zero checks, and quaternion normalization checks. |
| `docking/receipts.rs` | Canonical hashing, context/source/policy receipts, and the expected pipeline receipt graph. |
| `docking/projection.rs` | Backend-independent scientific projection types, graph validation, decision preimage, and canonical projection hashing. |
| `docking/producer.rs` | Frozen 64-slot lane/source mapping, producer row semantics, and producer receipt authentication. |
| `docking/producer_replay.rs` | Native producer replay invocation and independent placement comparison. |
| `docking/admission.rs` | Independent geometric-admission evidence, row semantics, numeric comparison, and receipt rederivation. |
| `docking/rigid.rs` | Rigid ABI config conversion, rigid evidence validation, and independent V2/V3/V6 replay. |
| `docking/torsion.rs` | Torsion V7 row, move, coordinate-selection, and typed-failure validation. |
| `docking/refinement.rs` | Final quaternion composition and refinement aggregation/coordinate-ready validation. |
| `docking/scorer_validity.rs` | Independent ScorerV1 and validity replay, typed failures, topology conversion, and receptor-cell evidence. |
| `docking/ranking_clustering.rs` | Stable ranking, counted prefixes, direct-coordinate RMSD clustering, and Top-K reconstruction. |
| `docking/pipeline_evidence.rs` | Evidence-to-ABI conversion plus canonical downstream and pipeline receipt authentication. |
| `docking/evidence.rs` | Authenticated native ABI row conversion to the public fixed64 evidence surface. |
| `docking/output_validation.rs` | Fail-closed validation of the complete native fixed64 output graph. |
| `docking/preselected.rs` | Producer-bypass composition for a verified receipt-bound 512-to-64 batch. |
| `docking/ffi.rs` | Descriptor initialization, ABI boolean/source conversion, temporary and preselected handle ownership, backend queries, and exactly-once destruction. |
| `docking/output_validation_tests.rs` | Test-only adversarial output-graph fixtures; it has no runtime ownership. |

## Qualification-bound root path

The logical target is an orchestration root with child ownership modules. The
physical root intentionally remains `src/docking.rs`, rather than moving to
`src/docking/mod.rs`, because the current path is part of frozen evidence and
verification inputs:

- `engine_v2_native_fixed64_cpu_profile_v7_sources.json` binds the consumed-v7
  source closure to `src/docking.rs`;
- `engine_v2_native_fixed64_cpu_profile_v6_sources.json` binds the archived-v6
  source closure to the same path;
- the context-lease verifier and CI authority audit inspect that exact owner;
- the module-boundary analyzer defaults to that exact path.

Renaming the root is therefore not a behavior-preserving #331 cleanup. It
would require a separately authorized successor profile and evidence plan; the
consumed CPU-v7 qualification must not be rerun or rewritten for this purpose.

## Review invariants

Changes at any boundary above must preserve all of the following unless a
separate change explicitly authorizes and proves otherwise:

- public Rust API and native C ABI;
- schema, profile, and canonical hash domain strings;
- receipt field order and byte representation;
- exact 64-slot denominator, stable ordering, and typed failures;
- backend selection and fallback behavior;
- allocation bounds and context/handle destruction order;
- independent C++ reference, Rust CPU, and applicable HIP parity contracts;
- all-false reservation, molecular, benchmark, scientific, performance,
  product, Stage 0, Fresh-128, and HIP-device authority.

The analyzer is a lexical review aid, not scientific evidence. Exact-head CI,
reviewed-tree equality, and exact-merge-SHA postmerge checks remain required
for each behavior-preserving ownership change.

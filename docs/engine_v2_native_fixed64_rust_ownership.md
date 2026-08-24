# Engine V2 Native Fixed64 Rust Ownership

This document is the reviewer map for the Rust wrapper around the native
fixed64 docking pipeline. It records source ownership only. It does not grant
execution, reservation, benchmark, scientific, performance, product, or HIP
device authority.

## Orchestration closure

`rust/betelgeuze-runtime/src/docking/mod.rs` is the private docking module root and
the owner of `Fixed64Pipeline` construction and run orchestration. The crate's
public docking API is the explicit re-export list in
`rust/betelgeuze-runtime/src/lib.rs`. The closure ceiling for the
behavior-preserving split tracked in issue #331 is:

- at most 2,000 lines in `docking/mod.rs`;
- at most two analyzer-visible top-level runtime items: the
  `Fixed64Pipeline` struct and impl;
- no scientific, receipt, or complete output-graph validation algorithm
  implemented directly in the orchestration root. Construction-time component
  backend checks, native `profile_id` ABI validation, native handle storage,
  constructor calls, and guard transfer remain orchestration responsibilities;
  guard mechanics and destruction are owned by `docking/ffi.rs`.

The behavior-preserving orchestration root has 1,709 lines and those two items.

## Ownership map

| Source | Owned boundary |
| --- | --- |
| `lib.rs` | Crate-root public re-exports; a `pub` item inside the private docking module is externally reachable only when this owner exports it. |
| `docking/mod.rs` | Private child-module wiring plus `Fixed64Pipeline` construction/run orchestration, including construction-time component-backend checks, native `profile_id` ABI validation, owned-handle storage, native constructor calls, and transfer from temporary guards. |
| `docking/types.rs` | Public fixed64 Rust data-model inputs, evidence, rows, receipts, enums, and conversions; these borrowed and owned types do not imply a `repr(C)` layout contract. |
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
| `docking/ffi.rs` | Descriptor initialization, ABI boolean/source conversion, temporary/preselected guard mechanics, backend queries, and exactly-once destruction. |
| `docking/output_validation_tests.rs` | Test-only adversarial output-graph fixtures; it has no runtime ownership. |

## Current root path and historical evidence

The orchestration root and its child ownership modules now use the physical
target layout at `src/docking/mod.rs`. Current-checkout tools inspect that exact
path:

- the context-lease verifier and CI authority audit inspect that exact owner;
- the module-boundary analyzer defaults to that exact path.

The consumed-v7 verifier reads its source manifest and source files from the
historical qualified commit, whose manifest intentionally retains the then-current
`src/docking.rs` path. This current-checkout move does not rewrite that frozen
evidence or require rerunning the consumed qualification. The archived-v6
verifier instead validates frozen profile/archive metadata and does not inspect a
current or historical source tree, so the move likewise does not alter that
archive. The current context-lease verifier, authority audit, analyzer, and
their path-regression test move together with the physical root.

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

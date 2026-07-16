# Engine v2 scientific evidence roadmap

Status: planned evidence program; no scientific or product promotion

Observed baseline: `main@d4156e63bd3cb2052752e5223e5d842a998a24c5`

This roadmap separates implemented source contracts from future scientific,
benchmark, hardware, and product evidence. A green source-level test or CI job
does not satisfy a later stage and cannot promote a claim flag.

## Current claim boundary

The current repository state keeps all of the following false:

- `scientific_validation=false`
- `public_benchmark_validation=false`
- `gpu_parity=false`
- `customer_execution=false`
- `commercial_readiness=false`

The capability-level fields `claim_safe`, `scientifically_validated`,
`benchmark_validated`, and `customer_execution_enabled` also remain `false`.
Each stage below requires separately reviewed evidence; stages cannot be
collapsed or inferred from one another.

## Stage gates

| Stage | Required evidence | Explicit non-claim |
|---|---|---|
| 1. Contract correctness | Deterministic identities; serialization round trips; units and dimensions; failure-inclusive ledgers; finite-difference energy/force checks; invariance and fail-closed tests | Does not calibrate a force field or validate docking accuracy. |
| 2. Frozen public benchmark protocol | Versioned CASF/PDBBind-style protocol where licensing permits; split provenance; symmetry-aware RMSD; PoseBusters-style validity; failure-inclusive denominators; frozen manifest and executable/scorer fingerprints; predefined thresholds; no test-set tuning | Protocol readiness is not a successful benchmark result. |
| 3. External baseline receipts | Reviewed offline Vina/GNINA/Smina receipts; binary/version/container identity; exact case coverage; retained failures; input/output hashes; comparable score semantics | Receipt integrity is not public benchmark validation or endorsement of an external engine. |
| 4. Docking evidence | Pose success, scoring, ranking, and valid screening/enrichment metrics; uncertainty intervals; predefined acceptance thresholds; complete denominator | Passing one metric does not establish general docking accuracy or commercial fitness. |
| 5. Physics evidence | Reviewed parameter provenance and applicability domain; independent energy/force references; force validation before dynamics; dedicated protocol for any free-energy claim | Stable execution alone is not physical accuracy. |
| 6. GPU parity | CPU/GPU tolerance contract; deterministic fixtures; kernel-level and end-to-end comparisons; failures retained; performance measured separately | Throughput is not numerical correctness, and CPU tests do not imply GPU parity. |
| 7. Product qualification | Threat model; tenant isolation; artifact integrity; durable quota/rate state; rollback; operational evidence; explicit authorization review | Customer routes remain disabled until every required gate is accepted. |

## Evidence record requirements

Every stage artifact must record:

- immutable input and protocol identities;
- code, dependency, executable, and environment fingerprints appropriate to the
  stage;
- exact case coverage with failures retained in the denominator;
- units, score direction, aggregation, thresholds, and uncertainty method;
- artifact hashes and path-confinement verification;
- reviewer, timestamp, supersession, and revocation status;
- separate values for `implemented`, `scientifically_validated`,
  `benchmark_validated`, `customer_execution_enabled`, and `claim_safe`.

Missing, stale, partial, unsigned, or mismatched evidence must fail closed. A
stage artifact may reference an earlier accepted artifact but must not copy its
claim status without revalidating the dependency and freshness chain.

## Review and promotion rules

1. Define the protocol and acceptance thresholds before observing held-out
   results.
2. Keep training, validation, and test provenance explicit and prevent
   test-set tuning.
3. Review scientific evidence independently from API security and release CI.
4. Review GPU correctness independently from GPU performance.
5. Require a dedicated PR for every claim transition, with the exact evidence
   bundle and affected capability fields in scope.
6. Reject partial promotion: an implementation flag may become true without
   changing any scientific, benchmark, customer, or commercial claim.
7. Keep the customer execution path disabled until product qualification and
   explicit operator authorization are both accepted.

## Near-term work queue

- Keep the bounded coordinate, scalar-value, canonical-topology, and first neutral
  acyclic C/O/H chemical-graph preparation carriers executable. The graph has no
  generated hydrogen coordinates, reviewed parameter source, or `AllAtomSystem`;
  parameterability, geometry quality, and scientific validity remain false.
- Keep the exact-input 30-case synthetic supported/failure contract corpus and
  51-axis coverage ledger executable. It classifies 17 axes as supported, 27 as
  explicitly unsupported, and 7 as not implemented; it is not parameter-fitting
  data and does not make V2-1 exit-ready.
- Keep exact selected source assembly metadata, generation, and Cartesian-
  operation rows bound while blocking preparation whenever any selected assembly
  category is present. Category absence does not prove that the deposited
  asymmetric unit is the biological assembly; identifiers, operation expressions,
  matrices, composition, coordinate expansion, and biological correctness remain
  uninterpreted.
- Keep both official source observation-gap categories bound and classify
  `occupancy_flag` 0 as zero occupancy and 1 as unobserved. Any such declaration
  blocks preparation before chemistry; absence of both optional categories does
  not prove structural completeness, and no identity, missingness, repair, or
  coordinate inference is performed.
- Keep source water and bounded monoatomic metal/nonmetal-ion composition roles
  executable without inferring general ligand, cofactor, modified-residue, or
  biological function. Metal/ion preparation remains explicitly unsupported.
- Keep unresolved general nonpoly components from being guessed as cofactors. The
  explicit unsupported boundary is not evidence that a component is biologically
  not a cofactor.
- Keep `_pdbx_struct_mod_residue` source declarations joined to bounded polymer
  label identity while atom-site observation, parent chemistry, modification
  nature, auth/model/insertion semantics, and preparation remain blocked.
- Keep the complete atom-site model-number set classified while only `{1}` is
  execution-eligible. Multi-model and singleton non-1 input remain explicit
  failure rows; selection, ensemble, trajectory, averaging, and cross-category
  reconciliation remain unimplemented.
- Keep explicit nonpoly atom-site alternate locations as a frozen preparation
  failure row. Conformer selection, occupancy population, and altloc chemistry
  remain unimplemented.
- Keep known nonpoly insertion-code markers exactly joined across scheme,
  atom-site, and connection endpoint identity. This does not interpret polymer
  insertion/deletion, canonical renumbering, or general author/label semantics.
- Next, close the 7 implementation-gap rows by independent capability slices and
  add a licensing/provenance-reviewed real-world supported/failure corpus. Do not
  start production parameter fitting while either requirement remains open;
  coordinate-bearing hydrogen is the next preparation priority.
- Freeze a licensing-compatible public benchmark manifest and failure-inclusive
  reporting contract; do not run or publish a result as part of that protocol
  definition PR.
- Define independent parameter provenance and applicability-domain records for
  H5 reference physics before proposing any validation study.
- Design CPU/GPU parity fixtures only after the CPU reference behavior and
  tolerances are frozen.
- Close the remaining same-UID artifact TOCTOU, unsigned ledger, and runtime
  receipt re-evaluation risks before considering a customer-route review.

Until those evidence programs are executed and independently accepted, the
repository remains a bounded implementation and evidence-verification
scaffold, not a scientifically validated or commercially ready platform.

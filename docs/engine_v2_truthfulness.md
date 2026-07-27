# Engine v2 Truthfulness and Evidence Layers

Engine v2 deliberately separates software implementation from scientific and
commercial promotion.  A component may exist, have focused tests, and be wired
to a canonical process while production execution, durable result evidence,
independent result review, scientific validation, benchmark validation, product
qualification, and customer execution all remain closed.

The executable policy is implemented in
`betelgeuze_engine_v2.truthfulness`.  Its small frozen policy document is
`config/independent_engine_v2_truthfulness_policy.json`.

## Lifecycle vocabulary

Each derived capability row reports these states independently:

| Field | Meaning |
|---|---|
| `implemented` | Source implementation exists. |
| `component_tested` | The implemented reference contract has focused executable tests. |
| `canonical_entrypoint_applicable` | The capability requires a process-level canonical entrypoint. |
| `canonical_entrypoint_wired` | The process-level entrypoint is connected to its bounded components. |
| `internal_reference_execution_enabled` | Internal reference APIs may execute within their bounded contract. |
| `production_execution_authorized` | External production authorization exists for the selected run. |
| `production_result_receipt_present` | A durable production result receipt exists for that authorized run. |
| `independent_result_reviewed` | An independent reviewer accepted the durable result evidence. |
| `scientifically_validated` | Independent scientific acceptance exists for the claimed scope. |
| `benchmark_validated` | Frozen public holdout evidence supports the benchmark wording. |
| `product_qualified` | Product integration and operational qualification are complete. |
| `customer_execution_enabled` | The capability is admitted to a customer route. |
| `claim_safe` | All evidence required by the exact claim boundary is present. |

The following implications are prohibited:

```text
implemented
≠ canonical entrypoint wired
≠ production execution authorized
≠ production result receipt present
≠ independently reviewed result
≠ scientifically validated
≠ benchmark validated
≠ product qualified
≠ customer enabled
≠ claim safe
```

## Current implementation corrections

The current lifecycle layer records that the CPU energy/force validation and CPU
minimization validation process entrypoints are implemented and wired.  It does
**not** claim that a production authorization, production result receipt, or
independent result review exists.

The frozen four-case public redocking cohort has a result-free reference-ligand
matcher and bounded heavy-atom symmetry materializer.  A separate 300-case
contract now freezes a result-independent subset of the published PoseBusters
308-case journal list and defines failure-complete Engine V2/Vina/GNINA
Top-1/3/5, validity, runtime, subgroup, paired-delta, and bootstrap-CI reporting.
Its local runner may execute only against operator-supplied, hash-verified
public inputs and retains failures and receipts. It records the common pocket
source but does not claim equal search-region geometry between Engine V2's
sphere and the external autobox. Its standard-residue receptor charge proxy and
RDKit Gasteiger ligand charges enable Scorer v1 execution but are explicitly
uncalibrated and not scientifically validated. Runtime deltas do not claim
equivalent process-start boundaries. Unevaluated PoseBusters validity checks
abort rather than count as valid, and row commands are checked against their
declared engine mode. Neither contract supplies a public holdout result,
equal-search-effort or equal-region comparison, statistical
representativeness, independent attestation, scientific validation, product
qualification, production authorization, or customer execution.

Frozen historical contracts are not rewritten to make their old blocker text
appear current.  `superseded_blockers` records implementation blockers that are
closed in the current source, while `current_blockers` retains the external
scientific and production evidence still missing.

## Scoped metric evidence

Every metric promoted into an evidence packet must include:

- `scope_id`, `task_id`, `dataset_id`, and `dataset_version`;
- `split_id` and `target_family`;
- `scorer_id`, `scorer_version`, and exact `engine_commit`;
- `metric_id`, finite `value`, confidence interval, and confidence level;
- a positive all-case `failure_denominator`;
- `as_of_utc`; and
- an explicit `claim_boundary`.

A bare value such as “PR-AUC 0.81,” “green,” or “commercial parity” is not an
admissible metric evidence row.

## Review and ruleset evidence

Operational release evidence must be supplied externally.  The verifier
requires:

- a protected-branch ruleset identity and digest;
- no administrator bypass;
- stale-approval dismissal;
- CODEOWNER approval from a person distinct from the PR author;
- zero unresolved review conversations;
- an up-to-date PR head;
- successful required checks; and
- security, numerical-methods, or scientific reviewer approvals when those
  change categories are present.

Passing this verifier establishes only that the supplied operational review
evidence satisfies the frozen contract.  It never grants scientific validation,
benchmark validation, product qualification, customer execution, or a
claim-safe result.

## Verification

Run:

```bash
python tools/check_engine_v2_truthfulness.py
python -m pytest -q tests/unit/test_engine_v2_truthfulness.py
```

Optional external evidence can be checked with:

```bash
python tools/check_engine_v2_truthfulness.py \
  --metric-row scoped_metric.json \
  --review-evidence review_evidence.json
```

The repository intentionally bundles no production ruleset receipt, human
approval, production authorization, result receipt, or independent scientific
acceptance artifact.

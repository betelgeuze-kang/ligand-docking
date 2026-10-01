# E1–E3: joint identity evidence and paired post-freeze rank evaluation

These changes are development tools, not a new docking engine, source-admission
policy, customer model, physical affinity model or demonstration of AI value.
The existing four-arm runner, source/role admission, binary-label evaluation,
fixed-Ridge trainer, engine arithmetic and conservative execution budgets are
unchanged. No holdout or external experimental data are bundled.

## E1: evidence-derived identity completeness

The installed `betelgeuze_product.public_assay_preflight` emits
`public_assay_joint_preflight_v2`. A declared chemical identity must have at least
one canonical, connectivity or InChIKey-connectivity key, and declared document
identity must have a document key. A record/source-ligand ID or scaffold alone
is insufficient. This checks the presence of supported metadata key kinds, not
chemical correctness or equivalence of microstates.

Serialized legacy nodes and their declarations are not rewritten or resealed.
For example, the historical builder can declare an empty identity object present;
the new preflight derives effective completeness from its actual keys and marks
that candidate incomplete. False declarations remain incomplete. Incomplete
candidates remain graph vertices and can still bridge another candidate to a
reserved or unknown-policy component. All training/calibration/independent-
evaluation/prepared flags remain false even for clear candidates.

CLI results bind the preflight, component and residual-policy implementation
bytes, with pre/post checks, plus both full input hashes. Input and decompressed
input sizes are bounded. A fully written temporary result is linked exclusively,
so partial writes never replace an existing result. No signature, independent
execution attestation or resistance to consistently rewriting all evidence is
claimed. Existing `tools.product` module aliases continue to reference the owner.

## E2: reuse actual prediction/engine execution, then compare the same targets

`tools.product.compare_prepared_candidate_ranks` wraps the existing
`compare_prepared_candidate_policies` runner rather than reimplementing its four
arms (`similarity`, `engine`, `ai_engine`, `similarity_engine`). The wrapper first
validates and publishes an explicit rank plan; only then can the original runner
produce predictions and engine observations. Its existing cold/reused-model
semantics, time/call budgets, failures, unsupported candidates and no-free-retry
rules remain in force. The wrapper's resume requires the identical plan and
implementation and delegates existing interrupted-arm behavior to that runner.

A rank plan contains exactly:

```json
{
  "schema_version": "prepared_rank_plan_v1",
  "target_annotation": "YOUR_DECLARED_TARGET",
  "endpoint": "IC50",
  "unit": "nM",
  "domain_id": "catalogue_development_not_verified_physical_state",
  "assay_ids": ["YOUR_ASSAY_ID"],
  "comparisons": [["engine", "ai_engine"], ["similarity_engine", "ai_engine"]],
  "score_directions": {
    "similarity": "higher_is_better",
    "engine": "lower_is_better",
    "ai_engine": "lower_is_better",
    "similarity_engine": "lower_is_better"
  },
  "max_pair_work": 5000000
}
```

Use genuine target/assay metadata, not these example identity placeholders. The
assay list must exactly cover the frozen development pool. Supported endpoint
names are IC50, Ki and Kd; this does not combine different endpoints. Native
ChEMBL target/endpoint must match the existing fit intake. The domain is a
declaration, not a proven prepared-state/assay correspondence. Candidate exclusions
are not added post hoc: prepare the admissible metadata pool before freezing.

```bash
python -m tools.product.compare_prepared_candidate_ranks run \
  --protocol protocol.json --plan rank-plan.json --output-dir rank-run
```

This writes `rank-plan.json` before execution, delegates to `execution/`, then
publishes a hash-bound `ready.json`. Keep the returned ready SHA-256 as the
out-of-band input to evaluation. The comparison/plan/frozen references and every
committed arm summary are checked again before outcomes are read. Source and
input changes reject evaluation, and checks repeat before final publication.
Hashes prove internal binding, not an independently attested historical order.

Synthetic outcomes have the exact shape
`{"schema_version":"synthetic_rank_endpoints_v1", "plan_sha256": "...",
"endpoints": {"candidate": {"value": 10, "relation": ">"}, "missing": null}}`.
The endpoint IDs must exactly equal the frozen pool. The synthetic entry point
cannot supply outcomes for a native run:

```bash
python -m tools.product.compare_prepared_candidate_ranks evaluate \
  --ready rank-run/ready.json --ready-sha256 REAL_READY_SHA256 \
  --synthetic endpoints.json --synthetic-sha256 REAL_ENDPOINTS_SHA256 \
  --output-dir rank-evaluation --details
```

Native evaluation instead uses `--evaluation-dir` and `--summary-sha256` and calls
the existing post-freeze intake loader. Split/scope, candidate/component/assay and
target identities must match. No unbound native-label JSON override is provided.
Only the two exact-point exclusions (`measurement_not_exact` and
`measurement_not_supported_exact_point`) may be ignored for a **descriptive**
strict-right-censored observation with no other issues. No source/chemistry/role
exclusion is waived; the existing intake/training/binary-label policies are not
changed. Unsupported relations, conflicts, missing outcomes and other exclusions
remain `None` with counted reasons, not invented negatives or exact values.
Comparisons are calculated separately by assay in nM.

The result shows full-cohort counts/coverage AND the common candidate/ordered-pair
metrics for each prespecified arm pair. Equal score counts are not asserted to
mean equal candidate IDs. Pair identities are hashed; both sides use the exact
same common pair set. A descriptive common-pair difference is not significance,
independence or overall superiority, and is None if no comparison is possible.
Full failure/missingness denominators are preserved beside common-set results.

Original arm cost and worker/model observations are retained without adding
nested/inclusive durations. Validation, outcome reading and metric/detail output
are timed separately. The common wrapper/runner overhead is not free, but upstream
acquisition/preparation and model-development history remain unmeasured. Equal
budget caps do not imply identical CPU work or wall time.

## E3: exact bounded-memory summaries and optional details

The installed `paired_rank_metrics.compare_cohort` snapshots and validates its
inputs, encodes each candidate ID once, and computes truth ordering once per pair
for all arms. It retains counts and common candidate sets, not an all-pairs list
per arm. The old `censored_rank_metrics` API and detailed result shape are unchanged.
None endpoints are explicitly counted as unavailable; missing scores, unknown
orders, endpoint/score ties remain distinct. Scores passed to the primitive must
already be higher-is-better. The runner adapter negates lower-is-better energy
scores under the frozen plan without adding assay and energy scores together.

Optional detail callbacks receive chunks of at most 4096 rows (default 1024).
Their exception aborts the calculation; the adapter cannot publish a completion
marker after detail-write failure. Chunk files, stream hash and full summaries
are preserved. No O(N) claim is made for exact pairwise arithmetic; the bounded
work reservation accounts for all arm and paired comparisons before execution.
Summary memory is O(N times arms/comparisons) plus one chunk, not O(arms*N^2).

`tools/benchmark_paired_rank_metrics.py` records 32/128/256-candidate, three-arm
synthetic comparisons, two warmups and seven alternating repetitions, with
separate tracemalloc peak observations. The task compares legacy detailed output
to exact summaries, not to identical evidence storage. Optional streaming details
are checked separately. Allocation peaks are not process RSS and stage timings
are not whole-docking speedups. No flaky timing threshold gates CI.

## Verification and deployment boundary

New dedicated Python 3.10/3.11/3.12 CI runs the existing and new source tests,
including real CPU arms and native-shaped synthetic intake. It also builds the
root product wheel and checks E1 and E3 under isolated installed Python without
source imports. That stdlib-only installation intentionally uses `--no-deps` and
is not a full dependency/engine installation claim. Like its existing runner, the
E2 orchestration adapter remains a `tools.product` source-checkout development
command; it is not newly advertised as an installed product entrypoint.

Tests retain original assertions; the old preflight test fixture now includes a
real synthetic canonical key so its "clear" assertion continues to exercise the
intended complete-input case. New tests separately cover document-only, empty,
scaffold-only, incomplete-bridge and direct-dependency drift cases. Real native
sources are not downloaded and no fresh/blind evaluation or new scientific claim
is part of these changes.

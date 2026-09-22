# F1/F2: recoverable rank publication and explicit D3 policy execution

This change preserves the existing rigid-pose protocols and scoring arithmetic.
It is not an affinity calibration, new chemical parameterization, 512-atom D3
extension, GPU/MD capability, or demonstrated AI advantage.

## F1: planning and publication

`paired_rank_metrics.validate_cohort` and the computing function share admission,
input snapshots and the same arithmetic work bounds. Planning validates IDs,
endpoints, comparisons, types and limits but never enumerates pairs. Actual exact
rank computation remains pairwise; no linear-time metric claim is made.

The rank wrapper commits `run-cost.json` BEFORE `ready.json`. Ready format v2
hash-binds cost, plan, predictions and frozen input. On interrupted invocation,
resume reuses completed worker results under the original runner's no-free-retry
rules. If no original wrapper cost was committed, the next cost record describes
only the observed resumed invocation and explicitly marks prior cost unknown;
it does not infer or reconstruct a lost duration. Cost/ready publication itself
is excluded, and existing nested worker timing is not summed as whole-run time.

Rank `evaluate` now accepts `--resume`. The requested ready/outcomes references,
implementation and details mode are bound before outcome access. Ordered detail
chunks, a complete staged report, the public report and completion receipt are
published exclusively. A report/completion write interruption can be finalized
from the verified stage without recalculating metrics or repeating the workers.
A partial pre-stage attempt may recompute metrics, but must match any previously
published detail chunks. Changed plans, inputs, hashes, output bytes, symlinks or
inconsistent chunks reject rather than overwrite. The wrapper uses a nonblocking
local file lock; this is not a distributed lease or a guarantee about power loss
on every filesystem. Recovery's new validation/publication overhead is not
retroactively inserted into the original report timing.

Old source-bound executions are not migrated: their implementation closure must
match the original code. Ready v1 is not silently promoted to ready v2, and no
missing historical cost is fabricated. Existing low-level metric result formats
and rigid runner protocol v1/v2 retain their meanings.

```bash
python -m tools.product.compare_prepared_candidate_ranks evaluate \
  --ready rank-run/ready.json --ready-sha256 ACTUAL_SHA256 \
  --synthetic outcomes.json --synthetic-sha256 ACTUAL_OUTCOMES_SHA256 \
  --output-dir evaluation --details --resume
```

For catalogue development, retain the existing `--evaluation-dir` and
`--summary-sha256` route instead of a synthetic override. Native source/role,
chemistry and experimental-endpoint gates remain unchanged. Hashes check internal
binding, not authenticity or independently attested chronological execution.

## F2: use the existing D3 without duplicating its numerical solver

The four-arm runner accepts explicit `prepared_candidate_comparison_protocol_v3`.
It retains v2's required `selection_seed`, `tie_policy: seeded_pool_order` and
`arm_order`, and additionally requires exactly:

```json
"calculation": {
  "backend": "fixed_receptor_d3_v1",
  "score_quantity": "uncalibrated_scorer_v1_dimensionless_minimize"
}
```

Other fields (source, requests, candidate-call/time budgets, top_k) keep their
existing definitions. Each non-null candidate request references a COMPLETE
`cpu_fixed_receptor_request/1.0.0` JSON with canonical receptor/ligand state,
internal parameters, extensions, cross parameters, known pocket, pose budget,
solver and selection. Only `same_candidates` and `solvation: null` are admitted
inside this backend. The outer four-arm time/call comparison remains independent
of the inner matched-pose comparison. Missing candidate preparation remains an
unsupported row; inconsistent supplied preparation rejects before workers start.
Preparation/validation time is observed separately, not hidden in engine calls.

`policy_adapter` reuses D3's existing candidate generator, projected minimizer,
actual-coordinate rescore, baseline preservation, strain/total-energy/convergence
policy and report verifier. It runs baseline and D3 on matched source poses for
each outer candidate. No atoms, charges or bonded terms are inferred. Existing
limits remain 256 ligand/8192 receptor atoms, CPU float64 and nonperiodic sources.
The baseline and refined pose evidence, internal/cross/total energy terms, actual
force/score counts, failures, convergence and chosen variant are all retained.

The outer score is the minimum **ScorerV1 dimensionless score of the policy-
selected actual coordinates**. It is NOT the minimized total potential, cross-only
energy or physical affinity. It may come from an original pose when refinement
is rejected; that fact is explicit, never relabeled as an improved pose. If no
original/refined pose satisfies policy, the outer candidate fails with no score.
A failed refinement can still preserve an eligible original.

One outer engine call now means one complete matched baseline/D3 pose comparison,
not one force call. Nested pose counts, force/score calls and force reservations
are retained separately; wall-clock worker termination and no-free-retry rules
are unchanged. Lost pre-commit work remains uncertain in the existing worker
records, not reported as exact zero. All policy arms use the same backend and
score meaning within a run. Legacy rigid cross-energy scores must not be pooled
with ScorerV1 as though they were the same quantity. Rank evaluation records the
backend, each arm's score quantity and candidate D3 observations.

This integration evaluates selection policies AND exposes paired pre/post pose
evidence. It does not yet provide a separately calibrated causal experiment of
refinement versus no refinement at identical total runtime. Common-candidate
scores can be identical when deterministic D3 is applied by different selection
policies; useful coverage/order effects require full denominators and budgets.
Experimental target/chemical-state correspondence remains unverified unless
separately established by the source preparation; no holdout is used here.

## Verification scope

New tests cover plan nonenumeration, identical rejection contracts, injected
cost/ready/report/completion failures, no metric/worker rerun after finalization,
damaged/changed evidence, actual four-arm D3 execution, post-refinement coordinate
and energy preservation, explicit score meaning, failed-refinement fallback,
source mutation and deadlines. Original assertions and numerical tolerances
remain unchanged. Existing supported-version CI gains these tests and an actual
installed D3 adapter probe outside checkout with `python -I` and no PYTHONPATH.
The installed D3 venv shares the pinned CPU dependencies; it is not hermetic.
The source-side wrapper remains development tooling under `tools.product`.

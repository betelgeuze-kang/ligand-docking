# Prepared candidate policy comparison

`tools/product/compare_prepared_candidate_policies.py` runs four offline research
arms over exactly the same preassigned development pool: fit-only Morgan/Tanimoto
nearest-neighbor prediction, source-order V2 scoring, Ridge-prioritized V2 scoring,
and similarity-prioritized V2 scoring. The two selectors determine execution order;
the engine arms rank completed candidates by the existing cross-only energy.
Assay predictions and energy are never added. The approved product checkpoint
registry and the V2 force-field implementation remain unchanged.

## Scope and inputs

Run with `python -m tools.product.compare_prepared_candidate_policies run
--protocol protocol.json --output-dir new-directory`. The protocol has these exact
fields:

| Field | Contract |
| --- | --- |
| `schema_version` | `prepared_candidate_comparison_protocol_v1` |
| `source` | `chembl_fit_intake` with absolute `input_dir` and `summary_sha256`, or explicitly `synthetic_constants` with fixture `rows` |
| `requests` | Every development-test record ID, mapped to an existing rigid-pose request's `path` and `sha256`; `null` preserves a missing preparation |
| `budget_seconds_per_arm` | Same positive wall budget, at most 3,600 seconds, for each of the four CPU worker processes |
| `max_engine_calls_per_arm` | Same positive candidate evaluation call cap for each engine arm; failed calls consume it |
| `top_k` | Prespecified positive count for post-freeze metrics |
| `reuse_ai_from` (optional) | Bound `path` and `sha256` of a completed cold comparison's `comparison.json`; all other protocol fields, inputs, fit rows and runtime must match |

The native adapter invokes the existing source-bound ChEMBL loader. That loader
reconstructs metadata components and their preassigned roles before retrieving
the phase's labels. Non-fit observations are required to be withheld in the
comparison input. The full native context and exclusions are retained by the
owning intake. The comparison cannot replace that context with a hand-written
role list. The `synthetic_constants` route exists only for software tests and
does not authenticate source data or declare a scientific split.

The native AI arm calls the existing ChEMBL trainer, including its fixed Morgan
features, Ridge fit, weighting, model serialization and predictions before
evaluation labels. The similarity arm uses the same feature representation and
fit-only endpoint values. Replicate SMILES collapse before nearest-neighbor
voting; equally similar nearest neighbors receive equal weight. Features do not
include IDs, component names, assay values from other roles, or engine outputs.

Prepared requests pass through the existing rigid-pose reader and unchanged V2
kernel. Every supplied pose must complete and pass the existing absolute scalar
numeric check before a candidate can receive an engine rank. Partial failures
remain failed candidates with complete pose denominators. No source atoms,
charges, poses or negative assay observations are invented. The caller still
needs an independently verified assay/chemical/prepared-state link before any
scientific interpretation: this runner does not supply that link.

When assembling or rechecking a completed result, the similarity arm's scored
value must match its committed priority prediction. Each scored rigid-engine row
must have a hash-matched pose report whose independent scalar check passes,
whose denominators match the row, and whose minimum cross energy equals the
recorded score. Failed and unsupported rows cannot carry a score. This
verification runs before native post-freeze outcome loading. It binds the software
receipt to its numerical evidence; it does not establish physical validity.
The receipt also replays similarity predictions from fit-only rows and refits the
AI Ridge selector from those rows. For native intake it uses the source-bound
summary's prescribed assay or connected-component replicate weighting, and
checks the saved protocol, checkpoint coefficients and intercept against that
fit (relative and absolute tolerance 1e-12). Resealing a model, priority, rows and
final summary cannot substitute a selector outside that fit tolerance while
retaining those frozen fit inputs. These are local consistency checks, not source authentication or
independent proof of execution history.
Selector dependency versions (scikit-learn and SciPy) are part of the frozen
runtime. An absent package is recorded as null rather than required by metadata
inspection; paths that need it still require it at execution. Version or
installed/absent changes reject resume, as do source/runtime fingerprint changes.

## Cost and interruption

Each arm has a fresh CPU process. Its budget includes process startup/imports,
features, cold fit and inference where used, prepared-input parsing, supplied-pose
scoring, numeric checks, failure handling, and worker output writes. A parent
deadline terminates its own process group. Completed results beyond the deadline
receive no rank. Measured termination overhead is reported instead of hidden.
Common preflight and final source verification are measured separately. Peak
process memory and CPU time are recorded for workers that complete their receipt;
a killed worker has no fabricated resource measurement.
`receipt_verification_cost` records parent wall time for each arm's read-only
receipt check, including selector fit replay, and the final source recheck. This
work occurs after each worker and outside its equal deadline; it cannot improve
that arm's candidate order or grant a retry. The saved measurement describes the
original completed run, not a later `--resume` verification invocation. Parent
`orchestrator_wall_seconds` includes this cost, but upstream preparation remains
unmeasured, so `end_to_end_cost_measured` stays false.

Acquisition, original molecular preparation, and pose generation already happened
before these supplied requests. Their costs are **unmeasured** here. Consequently
this is a provided-pose experiment, not an end-to-end docking speedup. A cold run
includes training. A separate run with `reuse_ai_from` measures loading and using
the same bound model and retains the original cold-run cost. Its worker does not
refit; the separately measured parent receipt check replays the fit.
The native model uses the existing checkpoint predictor; model or fit-source
mutation rejects reuse. Repeated cost measurements and suitable real data remain
necessary for any performance conclusion. Resuming a completed journal is not
a model-reuse performance run.

`--resume` verifies input bytes, runtime/code hashes, completed rows and pose
reports. An inherited worker lease prevents a second parent from finalizing work
while an orphaned worker remains active. An interrupted attempt with uncertain
cost forfeits its original budget and retains its committed rows; it cannot gain
a free retry. Missing, unsupported, failed and unprocessed candidates all remain
in the original pool denominator. Immutable publication never overwrites prior
results. A final successful comparison receipt also rechecks its original inputs.

## Evaluation and interpretation

The separate `evaluate` command requires the comparison and frozen-file paths
and SHA-256 values, an existing evaluation intake directory and summary hash,
and a new output path. It checks the saved comparison and the original input
binding, checks the evaluation plan/scope before decoding its outcomes, then
uses the owning native evaluation loader. Only eligible exact endpoint values
receive the scope's existing activity threshold. Other observations remain
unknown; they are not negatives. Metrics are separated by assay and include the
whole pool's coverage, unfilled top-k positions and known-positive recall.
Boundary ties receive fractional expected counts instead of an ID-based advantage.
`evaluate_synthetic` is a Python API for independently stored boolean test labels.

Neither output establishes primary-source correctness, assay/prepared-state
equivalence, blind evaluation, calibrated uncertainty, scientific qualification,
end-to-end speedup, or AI superiority. A negative AI result is retained. Repeating
and varying protocols on observed development data does not make them blind.

## Validation

`tests/unit/test_prepared_candidate_comparison.py` exercises real CPU workers and
V2 calculations on synthetic prepared inputs, a synthetic native ChEMBL intake
through the existing trainer, pre-label role rejection, hard time/call limits,
complete failure denominators, input mutation, live-worker leases, resume and
post-freeze metrics. No public assay source is downloaded by these tests.

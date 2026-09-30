# Fair Docking Comparison Contract (Betelgeuze vs Vina/GNINA)

Status: reference. Priority 3 of the product-vision roadmap (CASF/PDBbind harness
+ Vina/GNINA comparison adapter).

Source of truth:
- Comparison gate: `betelgeuze_product/docking_comparison_contract.py` (dep-free)
- Metric names: `betelgeuze_engine/benchmark/docking_gold.py`
- Pose RMSD / success: `tools/accounting/build_pdbbind_casf_pose_affinity_results.py`,
  `betelgeuze_engine/biodiscovery/pose.py`
- Claim wording: `.kiro/steering/claim_safe_wording.md`

## Why a contract

A "we beat Vina/GNINA" number is meaningless unless the comparison is fair. The
v1 contract makes fairness a **fail-closed gate**: a comparison is valid only when
every tool shares the same dataset, preparation policy, metric definitions,
pose-success threshold, and complex universe with explicit missing/failed
accounting. An invalid comparison declares **no winner**.

## V1 fairness keys (must be identical across all tools)

`FAIRNESS_KEYS`:
- `dataset_id`
- `dataset_manifest_sha256`
- `prep_policy_sha256`
- `metric_def_version`
- `pose_success_rmsd_threshold_a`

If any differs across tools, `comparison_valid=false` and
`unfairness_reasons` lists the mismatched key(s). A comparison also requires at
least one `subject` tool (Betelgeuze) and one `baseline` tool (Vina/GNINA), and
unique `tool_id`s.

## V1 pose-success comparison

`build_pose_success_comparison(rows)` ingests per-tool aggregate rows (from a
`docking_gold`-style evaluator):

Required per row: `tool_id`, `tool_kind` (`subject`/`baseline`), the 5 fairness
keys, `complex_count`. Optional: `evaluated_complex_count`,
`missing_complex_count`, `failed_pose_complex_count`, `top1_pose_success_rate`,
`top5_pose_success_rate`, `top1_mean_rmsd_a`, `top5_best_mean_rmsd_a`,
`posebusters_valid_rate`, `result_artifact_sha256`.

Output: per-tool rows + (when valid) `subject_vs_baseline_deltas` with
`top1_success_delta` / `top5_success_delta`. Missing and failed-pose complexes
are preserved per tool (no silent drops).

## Enrichment comparison (DUD-E / LIT-PCBA)

`build_enrichment_comparison(rows)` compares `ef1` (EF@1%), `ef_point1`
(EF@0.1%), `bedroc`, `roc_auc`, `pr_auc` under the same fairness gate (minus the
pose threshold) and emits `ef1_delta` / `ef_point1_delta` / `bedroc_delta`
vs each baseline.

## Failure accounting

Each tool reports `missing_complex_count` and `failed_pose_complex_count`
explicitly. A tool with high success but many dropped complexes is visible, not
hidden. Comparisons never infer a missing tool's result from another tool.

## How to run a fair comparison (operational)

1. Freeze one dataset manifest (e.g. CASF-2016 core) and compute
   `dataset_manifest_sha256`.
2. Apply one preparation policy to all tools; record `prep_policy_sha256`.
3. Run Betelgeuze, Vina, and GNINA on that exact set; produce aggregate rows
   with the same `metric_def_version` and `pose_success_rmsd_threshold_a`.
4. Feed the rows into `build_pose_success_comparison` /
   `build_enrichment_comparison`. Only cite the result if `comparison_valid=true`.

## Out of scope

- Pose generation, Vina/GNINA execution, dataset download, and preparation run
  under numpy/RDKit/GPU/CI, not in this contract layer.
- Comparison results are claim-safe only under the benchmark ledger
  (`tracked_ranking_parity` / external-safe scope); broad parity stays locked.

## Version 2: two explicit pose comparison scopes

`build_scoped_pose_success_comparison(rows, scope=...)` emits
`docking_comparison_contract_v2`. It is a separate opt-in API; the v1 functions
and their output schema remain unchanged. Every input row must declare the v2
`schema_version` and the same `comparison_scope` as the call. Mixing scopes, or
omitting a scope, raises `DockingComparisonError`. Deltas are only computed within
one scope. Do not aggregate deltas from the two scopes into one winner.

Both scopes require a subject and baseline with unique `tool_id`s; nonempty
`tool_version`, `dataset_id`, `dataset_manifest_sha256`,
`candidate_manifest_sha256`, `metric_def_version`, and `result_artifact_sha256`;
the same positive `pose_success_rmsd_threshold_a`; and the same
`complex_count` across tools. These are caller-supplied provenance fields; the
validator does not resolve or authenticate their artifacts. Hash fields should
be content hashes of frozen artifacts, with the hash algorithm and canonical
serialization defined by the producing benchmark protocol.

| Scope | Additional required acceptance fields | Interpretation |
| --- | --- | --- |
| `controlled_core` | Equal `chemical_state_sha256`, `receptor_state_sha256`, `pocket_definition_sha256`, `shared_preparation_sha256`, and `canonical_prepared_input_sha256` across tools. Each row records `input_conversion` with nonempty `method`, `version`, `source_sha256`, `output_sha256`. | Shared chemistry, receptor, pocket, candidate universe, and preparation. Every conversion source must equal the shared canonical prepared-input hash; each tool's converted output remains distinct and visible. |
| `full_workflow` | Each row records its own `preparation_policy_sha256` and `preparation_recommendation_ref`; `preparation_failed_complex_count`; `peak_rss_kib`; `expert_intervention_count`, `expert_intervention_wall_seconds`, and `expert_intervention_log_sha256`; plus nonnegative finite `preparation_wall_seconds`, `compute_wall_seconds`, `validation_wall_seconds`, `recovery_wall_seconds`, and `elapsed_wall_seconds`. | Each tool can use its recommended preparation, with a reference to that recommendation. Preparation failures and human effort remain visible alongside runtime and memory. |

For full-workflow receipts, the four phase times and expert-intervention time
are **nonoverlapping wall-clock segments** of one run, measured on the same
monotonic clock from start through completion or stop. Preparation covers input
and receptor preparation; compute covers docking; validation covers result and
metric checks; recovery covers retry and failure handling; expert intervention
covers human work or waits during that run. If a producer cannot separate these
segments, it cannot emit a valid full-workflow v2 row by inventing times. Their
sum must not exceed `elapsed_wall_seconds`; the validator emits the remainder
as `other_wall_seconds` for startup, scheduling, and unclassified overhead.
`peak_rss_kib` is the maximum sampled sum of resident memory for the worker
process tree during that same run; zero is rejected as unmeasured. A zero
intervention count requires zero intervention
time, and a positive count requires positive time; the log hash binds a recorded
event list, including an empty list when the count is zero.
`preparation_failed_complex_count` counts complexes whose first terminal
failure occurred during preparation and cannot exceed
`failed_complex_count`. Other failures are the remainder and must retain
per-complex reasons in the source receipt.

Every v2 row also requires nonnegative integer `completed_complex_count`,
`failed_complex_count`, `unprocessed_complex_count`, `top1_success_count`, and
`top5_success_count`. The first three must sum exactly to `complex_count`, and
`top1_success_count <= top5_success_count <= completed_complex_count`.
The validator derives top-1 and top-5 rates using **all** complexes as the
denominator, including failed and unprocessed cases; caller-supplied rates are
rejected. A completed complex means the tool produced a result eligible for pose
assessment, including an unsuccessful pose. A failed complex includes any
preparation, compute, validation, or recovery failure. An unprocessed complex
has no eligible result and no confirmed failure. The source receipt must retain
per-complex IDs and reasons so these aggregate counts can be independently
checked. Invalid rows raise an error; unfair shared fields yield
`comparison_valid=false` and no deltas.

V2 validates receipt structure, not docking execution or scientific fairness by
itself. Acceptance for a real comparison additionally requires artifact-bound
input conversions, per-complex failure and timing records, independent metric
recalculation, identical evaluation rules, and a frozen eligible dataset. The
four-arm provided-pose candidate-policy runner documented in
`prepared_candidate_comparison.md` measures a different experiment; its
synthetic tests and cost receipt do not constitute Vina/GNINA comparison data.
For this reason, a consistent v2 row reports
`status=declared_comparison_consistent_unverified`,
`source_artifacts_verified=false`, and
`metrics_independently_recomputed=false`; a later independent verifier must
establish those facts before results support any performance claim.

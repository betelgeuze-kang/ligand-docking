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

A "we beat Vina/GNINA" number is meaningless unless the comparison is fair. This
contract makes fairness a **fail-closed gate**: a comparison is valid only when
every tool shares the same dataset, preparation policy, metric definitions,
pose-success threshold, and complex universe with explicit missing/failed
accounting. An invalid comparison declares **no winner**.

## Fairness keys (must be identical across all tools)

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

## Pose-success comparison

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

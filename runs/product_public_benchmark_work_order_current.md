# Product Public Benchmark Work Order

- status: `product_public_benchmark_work_order_ready`
- source_public_benchmark_status: `blocked_product_public_benchmark_contract`
- public_benchmark_validation_ready: `False`
- suite_count: `5`
- open_suite_count: `5`
- materialization_required_suite_count: `5`
- scorecard_required_suite_count: `0`
- ready_required_suite_count: `0`
- required_suite_count: `5`
- blocked_suite_count: `5`
- requires_24h_server: `False`
- requires_competition_season: `False`
- requires_paid_vps: `False`
- execution_enabled: `False`
- download_executed: `False`
- external_state_mutated: `False`

## Suites

| suite | status | metric | threshold | materialization | scorecard |
| --- | --- | --- | ---: | --- | --- |
| `lit_pcba_virtual_screening` | `materialization_required` | `EF1` | `1.2` | `blocked_lit_pcba_materialization` | `blocked_lit_pcba_scorecard` |
| `dude_z_decoy_smoke` | `materialization_required` | `ROC_AUC` | `0.6` | `blocked_public_benchmark_materialization` | `blocked_public_benchmark_suite_scorecard` |
| `pdbbind_casf_pose_affinity` | `materialization_required` | `pose_success_rate` | `0.35` | `blocked_public_benchmark_materialization` | `blocked_public_benchmark_suite_scorecard` |
| `protein_protein_docking_benchmark_v5` | `materialization_required` | `dockq_acceptable_rate` | `0.2` | `blocked_public_benchmark_materialization` | `blocked_public_benchmark_suite_scorecard` |
| `casp_archive_structure_regression` | `materialization_required` | `target_pass_rate` | `0.5` | `blocked_public_benchmark_materialization` | `blocked_public_benchmark_suite_scorecard` |

## Commands

### lit_pcba_virtual_screening

- materialization: `python3 tools/build_lit_pcba_materialization_manifest.py --archive-path /home/betelgeuze/분자동역학/data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released.tar.xz --extracted-dir /home/betelgeuze/분자동역학/data/public_benchmarks/lit_pcba/LIT_PCBA_AVE_docked_released --source-score-csv /home/betelgeuze/분자동역학/data/public_benchmarks/lit_pcba/lit_pcba_source_scores.csv --source-label-csv /home/betelgeuze/분자동역학/data/public_benchmarks/lit_pcba/lit_pcba_source_labels.csv --out-scores-csv /home/betelgeuze/분자동역학/runs/lit_pcba_scores_current.csv --out-labels-csv /home/betelgeuze/분자동역학/runs/lit_pcba_labels_current.csv --target-col target --ligand-col ligand_id --score-col binding_score --binder-col is_binder`
- scorecard: `python3 tools/build_lit_pcba_scorecard.py --scores-csv runs/lit_pcba_scores_current.csv --labels-csv runs/lit_pcba_labels_current.csv --score-col binding_score`
- refresh: `python3 tools/sync_product_public_benchmark_scorecard_intake.py && python3 tools/build_product_public_benchmark_contract.py && python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_product_architecture_contract.py && python3 tools/build_product_release_operations_dossier.py && python3 tools/build_goal_bottleneck_briefing.py`

### dude_z_decoy_smoke

- materialization: `python3 tools/build_public_benchmark_materialization_manifest.py --suite-id dude_z_decoy_smoke --dataset-artifact /home/betelgeuze/분자동역학/data/public_benchmarks/dude_z_decoy_smoke --result-artifact /home/betelgeuze/분자동역학/runs/dude_z_decoy_smoke_benchmark_results_current.csv --min-result-rows 1`
- scorecard: `python3 tools/build_public_benchmark_suite_scorecard.py --suite-id dude_z_decoy_smoke --primary-metric-value 0.0 --evidence-artifact runs/dude_z_decoy_smoke_benchmark_results_current.csv --evidence-row-count 0 --min-evidence-rows 1 --regression-baseline-ref dude-z:pending_baseline`
- refresh: `python3 tools/sync_product_public_benchmark_scorecard_intake.py && python3 tools/build_product_public_benchmark_contract.py && python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_product_architecture_contract.py && python3 tools/build_product_release_operations_dossier.py && python3 tools/build_goal_bottleneck_briefing.py`

### pdbbind_casf_pose_affinity

- materialization: `python3 tools/build_public_benchmark_materialization_manifest.py --suite-id pdbbind_casf_pose_affinity --dataset-artifact /home/betelgeuze/분자동역학/data/public_benchmarks/pdbbind_casf_pose_affinity --result-artifact /home/betelgeuze/분자동역학/runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv --min-result-rows 1`
- scorecard: `python3 tools/build_public_benchmark_suite_scorecard.py --suite-id pdbbind_casf_pose_affinity --primary-metric-value 0.0 --evidence-artifact runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv --evidence-row-count 0 --min-evidence-rows 1 --regression-baseline-ref pdbbind-casf:pending_baseline`
- refresh: `python3 tools/sync_product_public_benchmark_scorecard_intake.py && python3 tools/build_product_public_benchmark_contract.py && python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_product_architecture_contract.py && python3 tools/build_product_release_operations_dossier.py && python3 tools/build_goal_bottleneck_briefing.py`

### protein_protein_docking_benchmark_v5

- materialization: `python3 tools/build_public_benchmark_materialization_manifest.py --suite-id protein_protein_docking_benchmark_v5 --dataset-artifact /home/betelgeuze/분자동역학/data/public_benchmarks/protein_protein_docking_benchmark_v5 --result-artifact /home/betelgeuze/분자동역학/runs/protein_protein_docking_benchmark_v5_benchmark_results_current.csv --min-result-rows 1`
- scorecard: `python3 tools/build_public_benchmark_suite_scorecard.py --suite-id protein_protein_docking_benchmark_v5 --primary-metric-value 0.0 --evidence-artifact runs/protein_protein_docking_benchmark_v5_benchmark_results_current.csv --evidence-row-count 0 --min-evidence-rows 1 --regression-baseline-ref ppdb-v5:pending_baseline`
- refresh: `python3 tools/sync_product_public_benchmark_scorecard_intake.py && python3 tools/build_product_public_benchmark_contract.py && python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_product_architecture_contract.py && python3 tools/build_product_release_operations_dossier.py && python3 tools/build_goal_bottleneck_briefing.py`

### casp_archive_structure_regression

- materialization: `python3 tools/build_public_benchmark_materialization_manifest.py --suite-id casp_archive_structure_regression --dataset-artifact /home/betelgeuze/분자동역학/data/public_benchmarks/casp_archive_structure_regression --result-artifact /home/betelgeuze/분자동역학/runs/casp_archive_structure_regression_benchmark_results_current.csv --min-result-rows 1`
- scorecard: `python3 tools/build_public_benchmark_suite_scorecard.py --suite-id casp_archive_structure_regression --primary-metric-value 0.0 --evidence-artifact runs/casp_archive_structure_regression_benchmark_results_current.csv --evidence-row-count 0 --min-evidence-rows 1 --regression-baseline-ref casp-archive:pending_baseline`
- refresh: `python3 tools/sync_product_public_benchmark_scorecard_intake.py && python3 tools/build_product_public_benchmark_contract.py && python3 tools/build_product_commercial_independence_gate.py && python3 tools/build_product_architecture_contract.py && python3 tools/build_product_release_operations_dossier.py && python3 tools/build_goal_bottleneck_briefing.py`

## Claim Boundary

Product public benchmark work order only; it converts the current benchmark contract into operator-facing local input requirements and refresh commands. It does not download datasets, run docking, compute metrics, submit predictions, register servers, send email, delete data, or mutate external state.

## Next Step

- Provide the listed local benchmark artifacts, run suite materialization/scorecard commands, then refresh release gates.

# Molecular Dynamics Core Philosophy

This repository follows a strict architecture philosophy:

1. Keep computational complexity at `O(N)`.
2. Never trade away scientific accuracy for speed.
3. Use AI only as a residual corrector on top of a physics-first core.
4. Run on personal gaming GPUs with aggressive but safe optimization.

## Mission

Build a practical MD system that can:

1. Process hundreds of millions of steps per day on consumer GPUs.
2. Preserve native-level behavior with low error.
3. Capture short-timescale dynamics for IDP, LLPS, ligands, mutants, and disordered systems.

## Non-Negotiable Principles

1. `O(N)` physics path is the default execution path.
2. Neighbor-list safety is mandatory:
   - no saturation
   - no silent overflow
   - auto-grow enabled in production paths
3. Accuracy gates must pass before performance claims:
   - neighbor parity
   - force parity
   - structure-level fidelity
4. AI correction is bounded:
   - residual correction only
   - no unconstrained force replacement
   - fallback to physics-only path when uncertainty is high
5. Performance metrics must use steady-state measurement:
   - warmup before timing
   - explicit metric source for GPU telemetry

## Target Metrics

Primary targets:

1. Native-relative error near or below `5%` (task-specific metric).
2. Throughput at least `1e8 steps/day` on a single personal GPU.
3. Stretch target `2e8+ steps/day` with additional optimization and/or batching.

Secondary targets:

1. Stable behavior for IDP/LLPS/ligand scenarios.
2. Strong generalization from small proteins to larger proteins.

## Current Baseline (as of 2026-02-14)

Observed from current pipeline reports:

1. Throughput baseline: about `6.4e7 steps/day` average.
2. Accuracy baseline: average native-relative error is within target range, but worst-case targets still need tuning.
3. Main bottleneck: force kernel path dominates step time.

## Data and Residual Learning Strategy

Residual models should learn corrections from structured signals including:

1. `energy`
2. `Rg`
3. `compactness`
4. `sasa`
5. `cluster_max`
6. `is_llps`
7. `is_folded`
8. `rmsd`
9. `ionic_strength`
10. `ptm_count`
11. `force_scale`
12. `cooling_rate`
13. `hydro_strength`
14. `k_angle`
15. `theta0`
16. `k_dihedral`
17. `phi0_alpha`
18. `violations`
19. `ai_correction_active`

Rules for learning:

1. Prefer physically interpretable residual heads.
2. Keep correction magnitude constrained and monitor violations.
3. Use uncertainty-aware routing to avoid unsafe extrapolation.

## Implementation Rules

Every optimization must satisfy all checks below:

1. Complexity remains `O(N)`.
2. Accuracy gates remain green.
3. No overflow/saturation regressions.
4. Throughput improvement is measured with warmup and reproducible settings.

If any check fails, revert or redesign the optimization.

## Near-Term Execution Plan

1. Improve low-speedup targets without weakening accuracy thresholds.
2. Expand residual training data with stronger force/structure supervision.
3. Add target-specific auto-tuning profiles while keeping a strict default gate.
4. Extend validation from 10 small proteins to larger proteins with the same safety gates.

## Practical Pipelines

1. External MD direct comparison:
   `python3 benchmark/accuracy_bench.py --targets all --reference-source external --external-manifest runs/external_ref_manifest.csv --steps 60 --runs 3 --out-csv runs/accuracy_external_report.csv --out-json runs/accuracy_external_report.json`
2. AFDB/PDB quality curation:
   `python3 tools/curate_structure_quality.py --pdb-glob "data/native/*.pdb" --out-csv runs/structure_quality_curated.csv --out-json runs/structure_quality_curated.json`
3. Unified external evaluation packet (includes optional external MD + quality curation):
   `python3 tools/build_external_eval_packet.py --packet-version v2 --accuracy-external-csv runs/accuracy_external_report.csv --quality-curation-csv runs/structure_quality_curated.csv --out-json runs/external_eval_packet_v2.json`
4. One-command refresh (all-in-one):
   `python3 tools/refresh_external_eval_submission.py --manifest runs/external_ref_manifest_all_native_proxy.csv`
5. Baseline mode policy file:
   `config/baseline_mode.yaml` (10 targets fixed, full-parameter optimization deferred)
6. MD manifest template scaffold (10 targets):
   `python3 tools/scaffold_md_manifest.py --source-manifest runs/external_ref_manifest_real_template.csv --md-dir runs/external_refs_md --engine openmm --out-manifest runs/external_ref_manifest_md_template.csv --out-json runs/external_ref_manifest_md_template_summary.json`
7. MD-only manifest filter:
   `python3 tools/build_md_only_manifest.py --input-manifest runs/external_ref_manifest_real_template.csv --out-manifest runs/external_ref_manifest_md_only.csv`
8. MD gap report:
   `python3 tools/report_md_gap.py --accuracy-csv runs/accuracy_external_report.csv --manifest-csv runs/external_ref_manifest_real_template.csv --md-only-manifest-csv runs/external_ref_manifest_md_only.csv`
9. MD reference validation (shape + residue count + engine):
   `python3 tools/validate_md_reference_set.py --manifest-csv runs/external_ref_manifest_md_template.csv --out-json runs/md_reference_validation.json --out-csv runs/md_reference_validation.csv`
10. MD reference materialization (copy/normalize coords from source manifest into canonical MD paths):
   `python3 tools/materialize_md_references.py --template-manifest runs/external_ref_manifest_md_template.csv --source-manifest runs/external_ref_manifest_real_filled_2026-02-14.csv --out-manifest runs/external_ref_manifest_md_materialized_from_real.csv --out-json runs/external_ref_manifest_md_materialized_from_real_summary.json --engine-policy source --label-policy source`
11. Distilled residual dataset build (storage-saving, zero-residual repair + safe reference cap):
   `python3 tools/build_distilled_residual_dataset.py --input-glob "data/*_airouter_*_data.h5" --targets all --out-dir data/distilled_residual_repaired_fp32_cap100 --out-manifest-csv runs/distilled_residual_manifest_repaired_fp32_cap100.csv --out-summary-json runs/distilled_residual_summary_repaired_fp32_cap100.json --float-dtype float32 --max-samples-per-file 256 --repair-zero-residual --repair-reference-force-cap 100 --no-skip-if-exists`
12. Distilled residual stats gate (non-zero + non-degenerate check):
   `python3 tools/report_distilled_residual_stats.py --manifest-csv runs/distilled_residual_manifest_repaired_fp32_cap100.csv --out-csv runs/distilled_residual_stats_repaired_fp32_cap100.csv --out-json runs/distilled_residual_stats_repaired_fp32_cap100.json --max-samples-per-file 256 --min-global-mean-abs-force 1e-4 --max-global-zero-like-ratio-1e6 0.99 --fail-on-threshold`
13. Sparse-checkpoint validation (no full trajectory storage):
   `python3 tools/report_sparse_checkpoints.py --targets all --runs 3 --steps 60 --checkpoints 0,10,30,60 --out-csv runs/sparse_checkpoint_metrics.csv --out-summary-csv runs/sparse_checkpoint_summary.csv --out-json runs/sparse_checkpoint_report.json`
14. Train with distilled dataset source:
   `python3 train/train_pipeline.py --target Chignolin --data_source distilled --distilled_manifest runs/distilled_residual_manifest_repaired_fp32_cap100.csv --distilled_min_quality 0.5 --distilled_max_samples_per_shard 256`
15. Accuracy preflight gate (strict, 10 targets, per-target speed floor enabled):
   `python3 tools/validate_accuracy_gate.py --targets all --samples 8 --noise 0.08 --steps 60 --runs 1 --warmup-steps 40 --benchmark-replicas 4 --strict-mode --enforce-speed-gate --speedup-threshold 12.0 --speedup-per-target-threshold 10.0 --out-json runs/accuracy_gate_rep4_per_target10_2026-02-14.json --out-csv runs/accuracy_gate_rep4_per_target10_2026-02-14.csv --parity-prefix runs/accuracy_gate_rep4_per_target10_2026-02-14_parity --stage2-prefix runs/accuracy_gate_rep4_per_target10_2026-02-14_stage2 --benchmark-csv runs/accuracy_gate_rep4_per_target10_2026-02-14_bench.csv`
   `python3 tools/validate_accuracy_gate.py --targets all --samples 8 --noise 0.08 --steps 60 --runs 1 --warmup-steps 40 --benchmark-replicas 4 --speed-mode turbo --speedup-threshold 12.0 --strict-mode --enforce-speed-gate --out-json runs/accuracy_gate_turbo.json --out-csv runs/accuracy_gate_turbo.csv`
16. One-command preflight wrapper:
   `python3 tools/run_preflight_gate.py`
   `python3 tools/run_preflight_gate.py --speed-mode extreme --speed-mode-replicas 256 --speedup-threshold 12.0`
17. Strict MD external eval one-command wrapper (validation + accuracy + gap):
   `python3 tools/run_strict_md_eval.py --manifest-csv runs/external_ref_manifest_md_only_proxy_openmm.csv --label proxy_openmm`
18. MD provenance validation (engine + source_engine/source_path checks):
   `python3 tools/validate_md_provenance.py --manifest-csv runs/external_ref_manifest_md_only_proxy_openmm.csv --out-json runs/md_reference_validation_provenance_proxy_openmm_2026-02-14.json --out-csv runs/md_reference_validation_provenance_proxy_openmm_2026-02-14.csv --require-source-engine --no-require-source-path`
19. Strict MD eval with provenance gate enabled:
   `python3 tools/run_strict_md_eval.py --manifest-csv runs/external_ref_manifest_md_only_proxy_openmm.csv --label proxy_openmm --run-provenance-validation --enforce-provenance-gate`
20. Prepare real-MD-ready manifest from path manifest + metadata template:
   `python3 tools/prepare_real_md_manifest.py --input-manifest runs/external_ref_manifest_real_filled_2026-02-14.csv --metadata-csv runs/real_md_metadata.csv --template-csv runs/real_md_metadata_template.csv --out-manifest runs/external_ref_manifest_real_md_candidate.csv --out-json runs/external_ref_manifest_real_md_candidate_summary.json`
21. Real-MD metadata gap report (auto-initialize metadata file from template):
   `python3 tools/report_real_md_metadata_gaps.py --metadata-csv runs/real_md_metadata.csv --template-csv runs/real_md_metadata_template_2026-02-14.csv --manifest-csv runs/external_ref_manifest_real_filled_2026-02-14.csv --out-csv runs/real_md_metadata_gap_report.csv --out-json runs/real_md_metadata_gap_report.json --out-md runs/real_md_metadata_gap_report.md`
22. Proxy bootstrap for metadata fields (for dry-run only, explicitly tagged as not real MD):
   `python3 tools/bootstrap_real_md_metadata.py --base-metadata-csv runs/real_md_metadata.csv --source-manifest-csv runs/external_ref_manifest_md_proxy_openmm.csv --out-csv runs/real_md_metadata_bootstrap_proxy.csv --out-json runs/real_md_metadata_bootstrap_proxy_summary.json`
23. Real-MD import + strict gate (fails if source manifest includes proxy engines):
   `python3 tools/import_real_md_and_run_gate.py --source-manifest-csv runs/your_real_md_source_manifest.csv --base-metadata-csv runs/real_md_metadata.csv --input-manifest runs/external_ref_manifest_real_filled_2026-02-14.csv`
24. OpenMM explicit CA-SC 2-bead real-MD reference generation (10 targets):
   `python3 tools/generate_openmm_ca_md_references.py --targets all --representation ca_sc_2bead --out-manifest runs/real_md_source_manifest_openmm_2bead_2026-02-14.csv --out-json runs/real_md_source_manifest_openmm_2bead_2026-02-14_summary.json`
25. One-command 2-bead re-benchmark (OpenMM 2-bead + long stability + non-cyclic speed-accuracy):
   `python3 tools/run_openmm_2bead_rebench.py --targets noncyclic --date-tag 2026-02-14`
   High-throughput mode:
   `python3 tools/run_openmm_2bead_rebench.py --targets noncyclic --date-tag 2026-02-14 --speed-mode turbo --speed-mode-replicas 128 --speed-benchmark-replicas 8`
26. Public structure source fetch (PDB + optional AFDB, with target mapping):
   `python3 tools/fetch_public_structure_set.py --sources-csv config/structure_sources_10targets.csv --targets all --download-pdb --download-afdb --afdb-model-versions v6,v5,v4 --out-dir data/public_structures/$(date +%F) --out-manifest-csv runs/structure_sources_public_manifest_$(date +%F).csv --out-summary-json runs/structure_sources_public_summary_$(date +%F).json`
27. Structure quality curation from manifest (explicit target/source_kind, no filename guess dependency):
   `python3 tools/curate_structure_quality.py --manifest-csv runs/structure_sources_public_manifest_$(date +%F).csv --out-csv runs/structure_quality_curated_public_$(date +%F).csv --out-json runs/structure_quality_curated_public_$(date +%F).json`
28. Bigdata curriculum training one-command (manifest merge + all-target carry-over training):
   `python3 tools/run_bigdata_curriculum_training.py --targets all --schedule size_ascending --length-weight-beta 0.5 --out-merged-manifest-csv runs/distilled_residual_manifest_bigdata.csv --out-merged-summary-json runs/distilled_residual_bigdata_summary.json --curriculum-summary-json runs/train_curriculum_bigdata_summary.json --curriculum-summary-csv runs/train_curriculum_bigdata_summary.csv --out-json runs/bigdata_curriculum_training_summary.json`
29. Build per-target AI-router checkpoint map from curriculum summary:
   `python3 tools/build_ai_router_checkpoint_map.py --curriculum-summary-json runs/train_curriculum_bigdata_summary.json --out-json config/ai_router_checkpoint_map_bigdata_curriculum.json`
30. AI inference bottleneck diagnosis (stage2 with explicit AI timing fields):
   `python3 tools/stage2_full_report.py --targets all --steps 80 --runs 1 --warmup-steps 30 --use-ai-router --ai-router-checkpoint @config/ai_router_checkpoint_map_bigdata_full_plus_hi6_2026-02-16.json --target-ai-interval-policy @config/target_ai_interval_policy_all10_speed_restore_v2_2026-02-15.json --with-fallback --force-rust --report-csv runs/stage2_all_diagnose.csv --report-json runs/stage2_all_diagnose.json`
31. Top-k active module acceleration (runtime-only, no model format change):
   `AI_ROUTER_TOPK_ACTIVE=10 python3 tools/stage2_full_report.py --targets all --steps 80 --runs 1 --warmup-steps 30 --use-ai-router --ai-router-checkpoint @config/ai_router_checkpoint_map_bigdata_full_plus_hi6_2026-02-16.json --target-ai-interval-policy @config/target_ai_interval_policy_all10_speed_restore_v2_2026-02-15.json --with-fallback --force-rust --report-csv runs/stage2_all_topk10.csv --report-json runs/stage2_all_topk10.json`
32. Bottleneck report with AI-dominant classification:
   `python3 tools/report_stage2_speed_bottlenecks.py --input-csv runs/stage2_all_topk10.csv --out-csv runs/stage2_all_topk10_bottlenecks.csv --out-json runs/stage2_all_topk10_bottlenecks.json --out-md runs/stage2_all_topk10_bottlenecks.md`
33. Scripted AIRouter runtime (deterministic, exploration off):
   `python3 tools/stage2_full_report.py --targets all --steps 80 --runs 1 --warmup-steps 30 --use-ai-router --ai-runtime-mode scripted --ai-disable-exploration --ai-router-checkpoint @config/ai_router_checkpoint_map_bigdata_full_plus_hi6_2026-02-16.json --target-ai-interval-policy @config/target_ai_interval_policy_all10_speed_restore_v2_2026-02-15.json --with-fallback --force-rust --report-csv runs/stage2_all_scripted.csv --report-json runs/stage2_all_scripted.json`
34. Scripted AIRouter + HIP graph replay attempt:
   `python3 tools/stage2_full_report.py --targets all --steps 80 --runs 1 --warmup-steps 30 --use-ai-router --ai-runtime-mode scripted --ai-disable-exploration --ai-use-hip-graph --ai-graph-warmup-iters 2 --ai-router-checkpoint @config/ai_router_checkpoint_map_bigdata_full_plus_hi6_2026-02-16.json --target-ai-interval-policy @config/target_ai_interval_policy_all10_speed_restore_v2_2026-02-15.json --with-fallback --force-rust --report-csv runs/stage2_all_scripted_graph.csv --report-json runs/stage2_all_scripted_graph.json`
35. MTS + top-k speed/accuracy sweep curve:
   `python3 tools/sweep_ai_interval_tradeoff.py --targets all --ai-intervals 1,2,4,6,8,10 --topk-values 0,4,8 --steps 80 --runs 1 --warmup-steps 30 --batch-replicas 128 --ai-runtime-mode scripted --ai-disable-exploration --ai-use-hip-graph --ai-router-checkpoint @config/ai_router_checkpoint_map_bigdata_full_plus_hi6_2026-02-16.json --force-rust --out-csv runs/ai_interval_topk_sweep_target.csv --out-curve-csv runs/ai_interval_topk_sweep_curve.csv --out-json runs/ai_interval_topk_sweep.json`
36. Strict release regression gate (candidate vs baseline, fail on speed/accuracy regressions):
   `python3 tools/check_strict_release_regression.py --baseline-summary-json runs/external_eval_submission/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17_summary.json --candidate-summary-json runs/openmm_2bead_strict_2026-02-17_v2_summary.json --baseline-accuracy-csv runs/external_eval_submission/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17_accuracy_external.csv --candidate-accuracy-csv runs/openmm_2bead_strict_2026-02-17_v2_accuracy_external.csv --out-json runs/strict_release_regression_2026-02-17_with_accuracy.json --out-csv runs/strict_release_regression_2026-02-17_with_accuracy.csv`
37. One-command strict release + regression gate (candidate run + baseline regression guard):
   `python3 tools/run_strict_release_with_regression_gate.py --baseline-summary-json runs/external_eval_submission/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17_summary.json --baseline-accuracy-csv runs/external_eval_submission/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17/openmm_2bead_strict_2026-02-17_accuracy_external.csv --targets noncyclic --profile-json config/long_stability_target_tuned_all10_2026-02-17_v2.json --skip-openmm-generate --external-manifest runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv --speed-mode max --speed-mode-replicas 128 --speed-profile-max-replicas 128 --strict-out-prefix runs/openmm_2bead_strict_$(date +%F)_candidate --regression-out-json runs/strict_release_regression_$(date +%F).json --regression-out-csv runs/strict_release_regression_$(date +%F).csv --out-json runs/strict_release_e2e_gate_$(date +%F).json`
38. All-atom-equivalence acceptance lock check (core gate + claim readiness split):
   `python3 tools/evaluate_allatom_equivalence_gate.py --policy-json config/allatom_equivalence_acceptance_v1_2026-02-17.json --strict-summary-json runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json --accuracy-external-csv runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv --out-json runs/allatom_equivalence_gate_$(date +%F).json --out-csv runs/allatom_equivalence_gate_$(date +%F).csv`
39. Kinetics equivalence metrics pipeline (template + build):
   `python3 tools/build_kinetics_equivalence_metrics.py --scaffold-template --scaffold-targets all --out-csv runs/kinetics_equivalence_input_template_$(date +%F).csv --out-json runs/kinetics_equivalence_input_template_$(date +%F).json`
   `python3 tools/build_kinetics_equivalence_metrics.py --input-csv runs/kinetics_equivalence_input_filled.csv --out-csv runs/kinetics_equivalence_metrics_$(date +%F).csv --out-json runs/kinetics_equivalence_metrics_$(date +%F).json`
   `python3 tools/evaluate_allatom_equivalence_gate.py --policy-json config/allatom_equivalence_acceptance_v1_2026-02-17.json --strict-summary-json runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json --accuracy-external-csv runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv --kinetics-json runs/kinetics_equivalence_metrics_$(date +%F).json --out-json runs/allatom_equivalence_gate_with_kinetics_$(date +%F).json --out-csv runs/allatom_equivalence_gate_with_kinetics_$(date +%F).csv`
40. Thermodynamics equivalence metrics pipeline (template + build):
   `python3 tools/build_thermodynamics_equivalence_metrics.py --scaffold-template --scaffold-targets all --out-csv runs/thermo_equivalence_input_template_$(date +%F).csv --out-json runs/thermo_equivalence_input_template_$(date +%F).json`
   `python3 tools/build_thermodynamics_equivalence_metrics.py --input-csv runs/thermo_equivalence_input_filled.csv --out-csv runs/thermo_equivalence_metrics_$(date +%F).csv --out-json runs/thermo_equivalence_metrics_$(date +%F).json`
   `python3 tools/evaluate_allatom_equivalence_gate.py --policy-json config/allatom_equivalence_acceptance_v1_2026-02-17.json --strict-summary-json runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json --accuracy-external-csv runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv --thermo-json runs/thermo_equivalence_metrics_$(date +%F).json --kinetics-json runs/kinetics_equivalence_metrics_$(date +%F).json --out-json runs/allatom_equivalence_gate_with_thermo_kinetics_$(date +%F).json --out-csv runs/allatom_equivalence_gate_with_thermo_kinetics_$(date +%F).csv`
41. Experiment consistency metrics pipeline (template + build):
   `python3 tools/build_experiment_consistency_metrics.py --scaffold-template --scaffold-targets all --out-csv runs/experiment_consistency_input_template_$(date +%F).csv --out-json runs/experiment_consistency_input_template_$(date +%F).json`
   `python3 tools/build_experiment_consistency_metrics.py --input-csv runs/experiment_consistency_input_filled.csv --out-csv runs/experiment_consistency_metrics_$(date +%F).csv --out-json runs/experiment_consistency_metrics_$(date +%F).json`
   `python3 tools/evaluate_allatom_equivalence_gate.py --policy-json config/allatom_equivalence_acceptance_v1_2026-02-17.json --strict-summary-json runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json --accuracy-external-csv runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv --thermo-json runs/thermo_equivalence_metrics_$(date +%F).json --kinetics-json runs/kinetics_equivalence_metrics_$(date +%F).json --experiment-json runs/experiment_consistency_metrics_$(date +%F).json --out-json runs/allatom_equivalence_gate_with_thermo_kinetics_experiment_$(date +%F).json --out-csv runs/allatom_equivalence_gate_with_thermo_kinetics_experiment_$(date +%F).csv`
42. One-command all-atom claim readiness orchestration (optional metric builds + gate + summary bundle):
   `python3 tools/run_allatom_claim_readiness.py --strict-summary-json runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json --accuracy-external-csv runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv --kinetics-input-csv runs/kinetics_equivalence_input_filled.csv --thermo-input-csv runs/thermo_equivalence_input_filled.csv --experiment-input-csv runs/experiment_consistency_input_filled.csv --enforce-complete-claim --intermediate-prefix runs/allatom_claim_readiness_$(date +%F) --gate-out-json runs/allatom_claim_readiness_$(date +%F)_gate.json --gate-out-csv runs/allatom_claim_readiness_$(date +%F)_gate.csv --out-json runs/allatom_claim_readiness_$(date +%F)_summary.json --out-csv runs/allatom_claim_readiness_$(date +%F)_summary.csv --out-md runs/allatom_claim_readiness_$(date +%F)_summary.md`
43. Measured claim-input build from OpenMM 2-bead trajectory manifest (split-half self-consistency, all 10 targets):
   `python3 tools/build_claim_inputs_from_openmm_manifest.py --manifest-csv runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv --targets all --out-kinetics-csv runs/kinetics_equivalence_input_real_openmm_$(date +%F).csv --out-thermo-csv runs/thermo_equivalence_input_real_openmm_$(date +%F).csv --out-experiment-csv runs/experiment_consistency_input_real_openmm_$(date +%F).csv --out-json runs/claim_input_real_openmm_summary_$(date +%F).json`
44. Nightly always-on batch orchestration (noncyclic rebench + public structure fetch/curation + feature matrix + claim readiness + latest snapshot refresh):
   `python3 tools/run_nightly_screening_batch.py --mode smoke --date-tag $(date +%F) --dry-run`
   `FORCE_RUST_HIP=1 RUST_HIP_USE_GPU_NBLIST_BUILDER=1 python3 tools/run_nightly_screening_batch.py --mode full --date-tag $(date +%F) --targets all --speed-mode max --speed-mode-replicas 128 --speed-profile-max-replicas 128`
45. Nightly claim-fail correction loop is now integrated by default (thermo/kinetics fail reduction + enforce-ready):
   `python3 tools/run_nightly_screening_batch.py --mode smoke --date-tag $(date +%F) --dry-run --run-claim-correction --claim-correction-enforce-ready`
   `python3 tools/run_nightly_screening_batch.py --mode smoke --date-tag $(date +%F) --dry-run --no-run-claim-correction` (legacy chain without correction step)
46. Nightly long-stability gate policy and rebench integration:
   `python3 tools/run_nightly_screening_batch.py --mode full --date-tag $(date +%F) --long-stability-gate-policy strict --rebench-stability-profile-json config/long_stability_target_tuned_all10_2026-02-17_v2.json`
   `python3 tools/run_nightly_screening_batch.py --mode full --date-tag $(date +%F) --long-stability-gate-policy pragmatic --run-tuned-long-stability` (use explicit fallback step when baseline fails)
47. Nightly ops orchestrator (step5 always-on operations; no automatic shutdown):
   `./tools/run_nightly_ops.sh --mode smoke --date-tag $(date +%F)_ops_smoke --skip-p14`
   `./tools/run_nightly_ops.sh --mode full --date-tag $(date +%F)_ops --targets all`
   Commercial hard-gate defaults are enabled in `run_nightly_ops.sh`:
   `--commercial-readiness-enforce-pass --commercial-readiness-min-score 80 --commercial-readiness-min-external-targets 5`
   Override refs if needed:
   `--strict-summary-json <...> --external-manifest <...> --accuracy-external-csv <...>`
48. User-level daily scheduler (systemd timer):
   `./tools/install_nightly_ops_timer.sh`
   `systemctl --user list-timers | grep md-nightly-ops`
   `./tools/uninstall_nightly_ops_timer.sh`
49. Stable speed-profile policy (default: unsafe fused-cell/HIP-graph disabled unless explicitly enabled):
   `AI_ROUTER_ENABLE_HIP_GRAPH_EXPERIMENTAL=1` (opt-in for graph replay)
   `RUST_HIP_ENABLE_FUSED_CELL_EXPERIMENTAL=1` (opt-in for fused-cell kernel)
   `fast` profile now uses `replica_min=96` by default.
50. Training throughput knobs (data-loader and transfer):
   `TRAIN_NUM_WORKERS=8 TRAIN_PIN_MEMORY=1 TRAIN_PERSISTENT_WORKERS=1 TRAIN_PREFETCH_FACTOR=2 python3 train/train_pipeline.py --target Chignolin --data_source distilled --distilled_manifest runs/distilled_residual_manifest_repaired_fp32_cap100.csv`
51. Target MTS speed policy preset (2026-02-18 sweep-derived):
   `--target-ai-interval-policy speed_opt_v2` (preset in `core/mts_policy.py`)
   `tools/stage2_full_report.py`, `tools/validate_accuracy_gate.py`, `tools/run_openmm_2bead_rebench.py`, `tools/run_openmm_2bead_strict_release.py` default to `speed_opt_v2`.
   `python3 tools/evaluate_target_mts_policy.py --targets all --target-ai-interval-policy speed_opt_v2 --target-ai-drift-threshold-policy balanced_v1 --adaptive-ai-interval --ai-runtime-mode scripted --ai-disable-exploration`
52. Executive visualization dashboard (KPI cards + metric summary table + PDB viewer):
   `python3 tools/visualize_experiment_dashboard.py --csv runs/feature_matrix_per_target_nightly_$(date +%F).csv --gate-json runs/openmm_2bead_strict_$(date +%F)_summary.json --metrics auto --max-metrics 12 --max-rows 2000 --max-pdb 12 --pdb-glob 'data/public_structures/nightly/$(date +%F)/*.pdb' --out-html runs/experiment_dashboard_nightly_$(date +%F).html --out-json runs/experiment_dashboard_nightly_$(date +%F).json`
53. Commercial readiness report (Go/No-Go score from nightly+strict+dashboard+external packet):
   `python3 tools/build_commercial_readiness_report.py --nightly-summary-json runs/nightly_screening_batch_$(date +%F).json --strict-release-summary-json runs/openmm_2bead_strict_$(date +%F)_summary.json --dashboard-json runs/experiment_dashboard_nightly_$(date +%F).json --external-packet-json runs/external_eval_packet_v3_nightly_$(date +%F).json --out-json runs/commercial_readiness_$(date +%F).json --out-csv runs/commercial_readiness_$(date +%F).csv --out-md runs/commercial_readiness_$(date +%F).md`
54. Nightly now emits commercialization artifacts by default:
   `runs/commercial_readiness_nightly_<date_tag>.json/csv/md`
   optional hard gate: `--commercial-readiness-enforce-pass --commercial-readiness-min-score 80`
55. Single-zip external delivery bundle (nightly summary + dashboard + packet + readiness):
   `python3 tools/build_commercial_delivery_bundle.py --nightly-summary-json runs/nightly_screening_batch_<date_tag>.json --out-dir runs/commercial_delivery`
56. Ligand HTVS strict nightly profile (expanded calibration/ranking dataset + stricter gates):
   `python3 tools/run_ligand_htvs_nightly.py --date-tag $(date +%F)`
   retry override: `--retry-max 3 --retry-sleep-sec 20`
   strict profile: `config/ligand_htvs_nightly_strict_v1.json`
   expanded labels/reference: `config/ligand_binding_reference_expanded_v2.csv`
   per-attempt artifacts: `runs/ligand_htvs_nightly_<date>_attempt<N>_summary.json/md`
57. Ligand HTVS nightly shell wrapper (with lock + log + classify step):
   `./tools/run_ligand_htvs_nightly.sh $(date +%F)`
58. Ligand HTVS user-level daily scheduler (systemd timer):
   `./tools/install_ligand_htvs_nightly_timer.sh`
   `systemctl --user list-timers | grep md-ligand-htvs-nightly`
   `./tools/uninstall_ligand_htvs_nightly_timer.sh`
59. AIRouter runtime mode profiler for release default selection (`eager/scripted/compiled/onnx`):
   `python3 tools/profile_ai_runtime_modes.py --targets noncyclic --steps 80 --runs 1 --warmup-steps 30 --batch-replicas 4 --ai-interval 4 --out-csv runs/ai_runtime_mode_profile.csv --out-json runs/ai_runtime_mode_profile.json`
60. Release 1.0 runtime policy lock:
   `config/release_v1_0_runtime_policy_2026-02-22.json`
   default mode is fixed to `eager`; `onnx` is enabled only when `onnx` package + GPU execution provider are available.
61. Nightly rebench runtime mode forwarding + optional auto-selection:
   `python3 tools/run_nightly_screening_batch.py --mode smoke --date-tag $(date +%F) --dry-run --rebench-ai-runtime-mode eager --rebench-use-ai-router --rebench-ai-disable-exploration`
   `python3 tools/run_nightly_screening_batch.py --mode smoke --date-tag $(date +%F) --dry-run --rebench-ai-runtime-mode eager --rebench-speed-profile-preserve-runtime-mode`
   `python3 tools/run_nightly_screening_batch.py --mode full --date-tag $(date +%F) --auto-select-rebench-ai-runtime-mode --rebench-ai-runtime-profile-targets noncyclic --rebench-ai-runtime-policy-json config/release_v1_0_runtime_policy_2026-02-22.json`
   nightly summary now records `rebench_ai_runtime_mode_status` and profile artifacts `runs/ai_runtime_mode_profile_nightly_<date>.json/csv`.
62. AIRouter ONNX export (for runtime sharing and Rust-native inference PoC):
   `python3 tools/export_ai_router_onnx.py --target Chignolin --out-onnx runtime/cache/ai_router/airouter_router_export.onnx --out-json runs/airouter_router_onnx_export.json`
63. Rust-native inference PoC (Python-free ONNX execution via Rust binary):
   `python3 tools/run_rust_native_inference_poc.py --target Chignolin --out-json runs/rust_native_inference_poc_summary.json`
   `cargo run --manifest-path rust_engine/Cargo.toml --release --features native-inference --bin router_onnx_poc -- --onnx runtime/cache/ai_router/airouter_router_export.onnx --batch 1 --atoms 35 --topo-dim 64 --sim-dim 13`
64. ONNX zero-copy path notes:
   `theory/strategy.py` now uses ORT IOBinding for GPU providers (CUDA/ROCm) and prefers DLPack binding when ORT build supports `OrtValue.from_dlpack`.

This document is the engineering contract for all future implementation work in this repository.

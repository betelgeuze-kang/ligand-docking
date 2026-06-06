# Ligand Scale-Up Benchmark Plan

## Purpose

Measure whether the production speedpack path is strong enough to move the current ligand pipeline from `10k` validation jobs toward `100k` and `1M` operational screening, without weakening the accepted claim set.

The current reference artifact is:

- `runs/ligand_scaleup_kpi_current.md`
- `runs/cross_family_residual_shadow_layer_plan_current.md`

## Baseline

All speedpack benchmarks should compare against the frozen accepted baseline:

- `runs/biorxiv_submission_freeze_current.json`

That baseline anchors:

- accepted run identity
- accepted reviewer package
- current temporal readiness state
- seed-shift robustness state

## Benchmark Layers

### Equal-Size Speedpack A/B

Purpose:

- isolate the speedpack effect from library-size effects
- answer whether a target-specific speedpack change is still claim-safe when the ligand set and decoy regime are held constant
- use this as the cleanest gate before promoting a domain-specific speedpack profile into broader `100k` or `1M` benchmarking

Interpretation:

- this is the clean comparison for questions like `TRPV1 baseline vs TRPV1 speedpack`
- unlike the `100k` pilot, the primary readout is not size-shift survivability but equal-size A/B quality preservation plus measured throughput gain

Required outputs:

- baseline summary artifact
- candidate summary artifact
- comparison artifact
- baseline and candidate SLA summaries for measured stage2 speedup
- `PR-AUC`, `EF1`, and `top20 hit rate` deltas on the equal-size task surface

Acceptance guardrails:

- no `pass -> fail` transition on the equal-size regression slice
- `PR-AUC` drop no worse than `0.01` absolute
- `top20` hit-rate drop no worse than `0.05` absolute
- measured `stage2` latency speedup at least `1.2x`

Commercialization-facing readout:

- `python3 tools/build_ligand_speedpack_ab_summary.py`
- this tool merges equal-size A/B metadata, baseline/candidate/comparison artifacts, and optional SLA summaries
- if the lightweight A/B metadata JSON is absent, it falls back to `runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json` to reconstruct the selected task surface
- it answers:
  - whether the A/B remains claim-safe
  - whether measured stage2 speedup is actually present
  - whether the candidate is ready to graduate into larger `100k` or `1M` throughput runs

### 100k Pilot

Purpose:

- prove the production path is operationally better than the frozen validation path
- confirm that quality does not fall apart under a `10x` larger screening volume

Interpretation:

- this is a size-shift operational benchmark, not an apples-to-apples metric-comparison benchmark
- the primary question is whether the production path stays claim-safe while materially improving throughput at larger screening size
- metric movement is still important, but the main readout is operational stability under a much larger library

Required outputs:

- stage2 rows/sec
- stage3 rows/sec
- end-to-end wall time
- artifact size
- retry / resume behavior
- `PR-AUC`, `EF1`, `top20 hit rate` on the frozen regression slice

Acceptance guardrails:

- no `pass -> fail` transition on the regression slice
- `PR-AUC` drop no worse than `0.02` absolute
- `top20` hit-count drop no worse than `1`
- measured end-to-end speedup at least `1.8x` on the slowest domain

### 1M Pilot

Purpose:

- confirm that throughput, failure handling, and ranking quality still scale once the pipeline is no longer in `validation-size` territory

Required outputs:

- the same metrics as the `100k` pilot
- shard-level throughput stability
- scaling efficiency relative to `100k`
- GPU-hour or wall-clock per million compounds

Acceptance guardrails:

- no `pass -> fail` transition on the regression slice
- `PR-AUC` drop no worse than `0.03` absolute
- `top20` hit-rate drop no worse than `0.05` absolute
- stage2 throughput at `1M` remains at least `70%` of the measured `100k` throughput

## Domain-Specific Wall-Clock Targets

These targets assume the production speedpack reaches the realistic `2x -> 3x` range discussed in the speedpack plan.

### 100k

- GPCR full tasks: target `<= 15 -> 25 min`
- ion-channel full tasks: target `<= 35 -> 50 min`
- kinase/protease full tasks: target `<= 10 -> 15 min`

### 1M

- GPCR full tasks: target `<= 2.0 -> 3.0 hr`
- ion-channel full tasks: target `<= 6.0 -> 10.0 hr`
- kinase/protease full tasks: target `<= 1.0 -> 2.0 hr`

These are production targets, not paper claims.

## KPI Table To Track

For every full ligand task, track:

- `total_latency_sec_10k`
- `total_latency_source` (`sla_total_latency_sec` vs `recomputed_stage_sum`)
- `stage2_trajectory_sec_10k`
- `stage2_share_pct`
- `queue_rate_stage2_rows_per_sec`
- `queue_rate_stage3_rows_per_sec`
- `timing_coverage_tier` (`measured_full`, `measured_partial`, `measured_latency_only`, `derived_partial`, `derived_only`)
- projected `100k` wall time
- projected `1M` wall time
- projected `100k` and `1M` times under `2x` and `3x` speedpack assumptions
- `gap_to_target_100k_min` and `gap_to_target_1m_hr`
- `required_speedup_to_target_100k`, `required_speedup_to_target_1m`, and `max_required_speedup_to_target`
- speedpack priority
- `pacing_rank_1m` and `domain_pacing_rank_1m`

The current automatically generated artifact is:

- `runs/ligand_scaleup_kpi_current.csv`
- `runs/ligand_scaleup_kpi_current.md`
- `runs/ligand_scaleup_100k_pilot_current.md`

The KPI summary should now be read in three layers:

- row table: per-task speedpack priority, projected wall-clock, and whether the timing is directly measured or reconstructed
- domain rollups: which domain is pacing `100k` / `1M`, how far its pacing task sits above the current target band, and whether that readout is backed by full measurement coverage
- coverage summary: how many tasks have measured total latency plus both queue-rate surfaces, which prevents weak projections from being mistaken for planning-grade evidence
- target-gap items: which tasks need the largest additional speedup to land inside the current `100k` / `1M` planning band

Interpretation note:

- `measured_full` is the preferred planning tier because it has measured end-to-end latency and both queue-rate surfaces
- `derived_partial` or `derived_only` rows are still useful for prioritization, but they should be treated as planning estimates until the missing SLA fields are backfilled
- the `pacing_items` section is the first place to look when deciding which domain/task pair blocks a realistic `100k` or `1M` launch
- the `required_speedup_to_target_*` fields are the cleanest comparison surface when two candidate speedpack profiles both look faster but only one materially closes the remaining target-band gap

The production-only 100k pilot scaffold is generated by:

- `tools/build_ligand_scaleup_100k_pilot.py`
- `tools/product/run_ligand_scaleup_100k_pilot_current.py`
- `tools/product/build_ligand_scaleup_benchmark_summary.py`

The additive next scaffold for the documented `1M` milestone is:

- `tools/product/ligand_scaleup_pilot_helper.py`
- `tools/build_ligand_scaleup_1m_pilot.py`
- `tools/run_ligand_scaleup_1m_pilot_current.py`

## Cascade Planning Artifacts

The current commercialization-facing cascade planning layer now has two dedicated artifacts:

- `runs/global_residual_correction_target_list_current.md`
- `runs/ligand_cascade_speedup_envelope_current.md`

And the companion design notes are:

- `docs/global_residual_correction_target_list.md`
- `docs/topk_cascade_architecture_plan.md`
- `docs/gpcr_residual_prototype_plan.md`

Current GPCR prototype artifacts:

- `runs/gpcr_residual_prototype_spec_current.md`
- `runs/gpcr_residual_ab_summary_current.md`

Use them in this order:

1. read the measured `100k` validity and failure artifacts
2. read the residual target list
3. read the cascade speedup envelope
4. read the GPCR residual prototype and equal-size A/B scaffold
5. then decide whether the next prototype should stay score-only or become a true `stage2` router

Why this shape:

- `1M` is the next explicit milestone in the plan, so it is the highest-value next pilot surface
- the new helper keeps the existing `100k` builder and runner untouched while reusing the same governance, smoke/full split, and dry-run comparison preflight pattern
- the `1M` wrappers stay thin so future scale steps can be added without hand-copying the full scaffold again

Current scaffold shape:

- full ligand tasks in `set1_core_blind` and `set2_expanded_ood` are upsized from `10k` to `100k`
- smoke ligand tasks in `set3_operational_smoke` stay at `64`
- smoke keeps the baseline-style decoy regime rather than forcing the full 100k production decoy shape
- the pilot profiles enable:
  - `traj_prod_stage2_preset=auto`
  - `traj_prod_stage2_preset_strict=true` whenever the profile intends auto family resolution to be a hard guardrail rather than a soft hint
  - `traj_prod_speedpack=true`
  - `traj_prod_early_stop_enabled=true`
  - `traj_prod_light_artifacts=true`

Preset governance guardrail:

- production benchmarks should prefer `traj_prod_stage2_preset_strict=true` for regression-facing runs
- this turns mixed-family auto detection or explicit preset mismatch into a preflight failure instead of a silent fallback
- use `strict=false` only for exploratory tuning where a soft fallback is acceptable

Execution note:

- the direct pilot runner is intentionally lighter than the reviewer-package wrapper
- this is meant for operational throughput measurement and regression comparison, not for producing a new reviewer-facing accepted package
- the current scaffold is runnable and validate-only checked, but by itself it is not yet benchmark evidence
- intended reading order:
  - `prelaunch`: start with `python3 tools/product/run_ligand_scaleup_100k_pilot_current.py --dry-run` and inspect the pilot scaffold plus readiness/blocker surface before compute
  - `post-run`: once baseline/candidate/comparison artifacts exist, read `python3 tools/product/build_ligand_scaleup_benchmark_summary.py` first because it upgrades the scaffold into measured commercialization evidence
- when using the full commercialization suite wrapper, the runner now writes canonical current artifacts directly:
  - dry-run:
    - `runs/ligand_scaleup_suite_dryrun_current.json`
    - `runs/ligand_scaleup_suite_dryrun_current.md`
  - execute:
    - `runs/ligand_scaleup_suite_execution_current.json`
    - `runs/ligand_scaleup_suite_execution_current.md`
  - stdout still mirrors the same JSON payload, so piping with `tee` remains optional rather than required
- the commercialization-facing readout should be built with:
  - `python3 tools/product/build_ligand_scaleup_benchmark_summary.py`
  - this tool merges the pilot scaffold, KPI table, and baseline/candidate/comparison artifacts when available
  - it produces a guardrail-oriented summary that answers:
    - whether claim safety is still preserved
    - which guardrails are already satisfied versus still pending
    - which slowest-domain throughput target remains the main commercialization blocker
  - when post-run baseline and candidate artifacts exist, it also walks the run summaries into per-task `pipeline_summary_json` SLA payloads so the slowest-domain speedup guardrail can move from `pending` to measured `pass` or `fail`
  - the resulting `claim_safe_status` is therefore more specific than the raw boolean and distinguishes:
    - `claim_safe_pending_speed_evidence`
    - `claim_safe_with_measured_speedup`
    - `claim_safe_but_speedup_guardrail_failed`
    - `claim_safe_size_shift_speed_diagnostic`
    - `regression_guardrail_failed`
  - the practical file order after a real run is:
    - `runs/ligand_scaleup_suite_dryrun_current.json` for the suite contract, enabled stages, and prelaunch blocker surface
    - `runs/ligand_scaleup_suite_dryrun_current.md` for the same contract in a quick operator-readable form
    - `runs/ligand_scaleup_suite_execution_current.json` for the executed stage order, return codes, and final suite refresh summary
    - `runs/ligand_scaleup_suite_execution_current.md` for the same execution payload in a quick operator-readable form
    - `runs/ligand_scaleup_suite_status_current.md` for the suite-level A/B vs `100k` vs `1M` stage board and launch/comparison state
    - `runs/ligand_scaleup_100k_pilot_current.md` or `runs/ligand_scaleup_1m_pilot_current.md` for scope and guardrail intent
    - `runs/ligand_scaleup_kpi_current.md` for pacing-domain context
    - `runs/ligand_scaleup_benchmark_summary_current.md` for the actual claim-safe / speedup verdict
- use `python3 tools/product/run_ligand_scaleup_100k_pilot_current.py --dry-run` first to inspect the selected task surface, resolved baseline run root, candidate run root, and planned comparison label before launching compute
- the dry-run payload now also exposes:
  - `selected_scope_summary` for the smoke/full split
  - `guardrail_summary` for the benchmark acceptance readout
  - `launch_readiness` for a single readiness/blocker verdict before compute
  - `comparison_enabled` and `comparison_skip_reason` so compare behavior is explicit before launch
  - builder markdown artifacts now surface `Launch Readiness` next to `Drift Audit`, so the same verdict is visible without opening the JSON payload
  - the actual launch path uses `tools/run_external_validation_blind_sets.py` directly rather than the heavier reviewer-package wrapper
- for a detailed live status window during the actual `100k` run:
  - `python3 tools/product/monitor_ligand_scaleup_pilot.py --run-root runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v1 --loop --interval-sec 5 --clear-screen --color`
  - this monitor combines:
    - runtime state (`running`, `stopped`, `stale`, `completed`)
    - active task inference from live processes
    - per-task `PASS / RUN / PEND` board
    - pilot contract shape (`full=100k`, `smoke=64`)
    - drift-audit and launch-readiness state
- for a commercialization-facing suite view across the three current stages:
  - `python3 tools/monitor_ligand_scaleup_suite.py --loop --interval-sec 5 --clear-screen --color`
  - intended reading order inside the suite monitor:
    - `Speedpack A/B`: read the equal-size A/B scaffold or summary first
    - `100k Pilot`: read dry-run readiness and live run-root state next
    - `1M Pilot`: read dry-run readiness and live run-root state last
  - when benchmark/comparison artifacts already exist, the suite monitor upgrades the matching stage from scaffold-only readiness into `comparison_ready`
  - when a stage has not been launched, the monitor falls back cleanly to `not_launched`, `prelaunch_ready`, or `blocked_prelaunch` instead of treating the missing run root as an error
  - the saved suite-status and suite-execution artifacts can be bundled into submission assets when present:
    - `runs/ligand_scaleup_suite_dryrun_current.json`
    - `runs/ligand_scaleup_suite_dryrun_current.md`
    - `runs/ligand_scaleup_suite_execution_current.json`
    - `runs/ligand_scaleup_suite_execution_current.md`
    - `runs/ligand_scaleup_suite_status_current.json`
    - `runs/ligand_scaleup_suite_status_current.csv`
    - `runs/ligand_scaleup_suite_status_current.md`
  - those suite-status files should be read before the benchmark summary because they answer a narrower operational question:
    - which commercialization stage is only scaffolded
    - which stage has a live run root
    - which stage already has comparison evidence
- the same preflight contract now exists for the `1M` scaffold:
  - `python3 tools/build_ligand_scaleup_1m_pilot.py`
  - `python3 tools/run_ligand_scaleup_1m_pilot_current.py --dry-run`

## Do Not Attempt 10M Full-Fidelity Yet

Do not treat `10M` as the next immediate milestone.

The right order is:

1. freeze accepted baseline
2. speedpack the existing stage2 path
3. prove `100k`
4. prove `1M`
5. only then decide whether `10M` can stay full-fidelity or needs a cascade

This keeps us from mixing two different problems:

- engineering efficiency
- algorithmic cascade design

## Decision Rule After 1M

Current 2026-05-13 readout:

- `runs/ligand_scaleup_suite_status_current.json` reports `commercialization_ready_suite_count=3/3` and `pending_suite_ids=[]`.
- The 1M package passes `set3_operational_smoke`, `set1_core_blind`, and `set2_expanded_ood`.
- The 1M benchmark summary reports `claim_safe=true`, `claim_safe_status=claim_safe_size_shift_speed_diagnostic`, and `commercialization_ready=true`.
- Treat the 1M run as scale/accuracy evidence. Keep speed/throughput wording tied to equal-size speedpack A/B unless a future 1M run explicitly passes the speed guardrail.

After the `1M` pilot:

- if speedpack reaches the `2x -> 3x` band and quality is stable, continue scaling the same path
- if the hardest domain still exceeds practical wall-clock or cost limits, branch into a cascade or surrogate design

That is the right point to revisit residual-correction or other architectural shortcuts.

# Stage2 Production Speedpack Plan

## Goal

Move the current ligand stack from a validation-grade execution path to a production-oriented path that can support `100k -> 1M` library screening without changing the accepted scientific baseline. The accepted validation path remains frozen at `runs/biorxiv_submission_freeze_current.json`; the speedpack path should live on a separate production branch or config family.

## Why Stage2 First

The current accepted run is dominated by `stage2_trajectory_generation`.

- `GPCR core`: about `139.9s / 167.7s`
- `TRPV1 chembl50`: about `525.1s / 583.8s`
- `kinase strict`: about `83.9s / 110.7s`

The current KPI artifact is:

- `runs/ligand_scaleup_kpi_current.md`

Across the full non-smoke ligand tasks, stage2 is the main wall-clock sink. This means a production speed effort should start there rather than in ranking, calibration, or packaging.

## Guardrail

The speedpack path must not silently replace the accepted validation path.

- Keep the accepted path frozen for paper and reviewer artifacts.
- Introduce production-only configs and flags.
- Require regression checks against the frozen `v7r1` accepted baseline.

## Priority Order

### 1. Adaptive Frame Budget And Early Stop

Add a production-only stage2 mode that can stop trajectory rollout early when the score and contact statistics stabilize.

Candidate controls:

- `traj_prod_speedpack`
- `traj_prod_adaptive_frame_budget`
- `traj_prod_frame_budget_tiers`
- `traj_prod_min_frames_smoke`
- `traj_prod_min_frames_full`
- `traj_prod_early_stop_enabled`
- `traj_prod_early_stop_min_frames_smoke`
- `traj_prod_early_stop_min_frames_full`
- `traj_prod_early_stop_window`
- `traj_prod_early_stop_contact_drift`
- `traj_prod_early_stop_min_distance_drift_A`
- `traj_prod_early_stop_max_mean_min_distance_A`

Implementation note:

- keep production early-stop metric evaluation batched on the tensor path and record backend/count telemetry so the early-stop overhead does not erase the rollout savings it is meant to capture

Expected value:

- highest leverage
- likely `25% -> 45%` stage2 reduction if tuned conservatively

Primary code touchpoints:

- `tools/run_ligand_htvs_pipeline.py`
- `tools/generate_ligand_trajectory_engine.py`

This first slice is primarily a trajectory-budget layer, not a pure systems-only optimization layer. It changes how much stage2 work is requested and how early that work may stop, while remaining production-only and off by default.

### 2. Target-Specific Stage2 Presets

The current dynamic ADRESS and batch settings are still mostly generic. The slowest target family, especially `TRPV1`, should not share exactly the same preset shape as faster GPCR or kinase tasks.

Presets should control:

- systems-only knobs:
  - `traj_job_batch_autotune_candidates`
  - `traj_writer_workers`
  - `traj_writer_max_pending`
- production speedpack knobs:
  - `traj_prod_frame_budget_tiers`
  - `traj_prod_min_frames_*`
  - `traj_prod_early_stop_*`
- `traj_dynamic_adress_*`
- optional target-specific `traj_force_backend` overrides if ever needed

Expected value:

- likely `15% -> 30%`
- also reduces tuning noise by keeping target families on stable presets

Initial pipeline slice:

- add `--traj-prod-stage2-preset`
- keep default `off` so the accepted validation path is unchanged
- support `auto`, `gpcr`, `ion_trpv1`, `kinase_protease`, and fallback `default`
- apply presets only inside the production stage2 command assembly
- keep preset-level changes conservative by shifting family differences into production speedpack knobs rather than generic reviewer-path defaults

Current design intent:

- systems-only tuning should remain separable from trajectory-budget tuning
- target presets are allowed to change production-only batch, writer, ADRESS, and speedpack behavior
- target presets should not silently redefine the accepted reviewer-facing validation path
- operational runs should surface the resolved preset family and effective production settings at the top level of the SLA summary, so debugging does not require digging through nested stage records
- strict preset diagnostics should be readable from the same SLA summary path, including:
  - requested preset
  - resolved preset
  - strict status (`ok`, `warn`, `error`)
  - prod-light effective writer settings
  - frame-budget / early-stop effective settings
- stress-validation closeout artifacts should mirror the same production-intent/runtime metadata in the per-run CSV and markdown summary, so scale-up audits can confirm the effective preset family without opening each child pipeline JSON

### 3. Artifact-Light Production Mode

Validation mode writes excellent reviewer artifacts, but production mode should write much less.

Production mode should:

- keep only the minimum manifest needed for stage3
- disable verbose stage2 markdown output
- reduce chunk and tail-report fanout
- keep compressed machine-readable summaries only

Current production-only surface:

- `traj_prod_light_artifacts`
- `traj_prod_light_progress_every_jobs`
- pipeline -> engine wiring through `--prod-light-artifacts`

Current top-level telemetry surface:

- `stage8_sla.traj_stage2_engine_summary`
- `stage8_sla.traj_stage2_engine_prod_mode`
- `stage8_sla.traj_stage2_engine_prod_light_artifacts`
- `stage8_sla.traj_stage2_engine_prod_frame_budget_applied_count`
- `stage8_sla.traj_stage2_engine_prod_early_stop_batch_count`
- `stage8_sla.traj_stage2_engine_prod_early_stop_row_count`
- `stage8_sla.traj_stage2_engine_mean_sim_frames_count`
- `stage8_sla.traj_stage2_engine_mean_frames_effective_cap`
- `stage8_sla.traj_stage2_engine_job_batch_derate_count`

This is meant to make A/B and `100k` triage faster:

- the top-level pipeline summary can now answer whether production mode was actually used
- whether artifact-light mode really disabled tail/chunk fanout
- whether adaptive frame budgeting and early stop were exercised at all
- whether batch derating happened under the current target family

Without this layer, we had to open the nested stage2 engine summary JSON every time.

Expected value:

- likely `10% -> 20%`
- most helpful for large `100k+` screening loops

Primary code touchpoints:

- `tools/run_ligand_htvs_pipeline.py`
- `tools/generate_ligand_trajectory_engine.py`

### 4. Persistent Warm Stage2 Worker

Today the pipeline still pays repeated process startup and cache warmup costs. A long-lived worker or service mode can keep:

- protein cache
- engine cache
- target preset state
- writer pool

warm across shards.

Expected value:

- likely `10% -> 15%`
- more important for `100k` shard farms than for a single `10k` job

### 5. Stage3 Slim Path

Stage3 is not the main bottleneck, but it still matters once stage2 improves.

Stage3 production mode should:

- remain `score_only`
- minimize delivery artifacts
- keep worker counts target-aware

Expected value:

- likely `5% -> 10%` end-to-end

## Expected Aggregate Gain

Realistic total expectations if the work is done conservatively:

- near-term: `1.5x -> 2.0x`
- strong production pass: `2.0x -> 3.0x`
- favorable target upper bound: `3.0x -> 5.0x`

The realistic ceiling without changing architecture is not `10x`. Beyond that, a cascade or surrogate path is likely required.

## Implementation Sequence

1. Add production-only flags and config family.
2. Implement `adaptive frame budget + early stop`.
3. Add target-specific stage2 presets.
4. Add artifact-light production mode.
5. Add persistent warm worker/service mode.
6. Tighten stage3 slim path after stage2 gains are measured.

## Success Criteria

The speedpack is worth keeping only if all three hold:

1. `no pass -> fail` on the frozen `v7r1` regression slice
2. `PR-AUC` and `top20` degradation stay within the benchmark plan guardrails
3. measured end-to-end speedup is at least `1.8x` on the slowest target family

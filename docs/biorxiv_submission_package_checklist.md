# bioRxiv Submission Package Checklist

## Required Top-Level Files

- one-shot runner status files:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/oneshot_status.json`
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/oneshot_status.md`
- one-shot stage logs:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/validation_stage.log`
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/package_stage.log`
- reviewer HTML index after package build:
  - `runs/biorxiv_external_validation_package_<tag>/reviewer_index.html`

- protocol doc:
  - `docs/biorxiv_architecture_validation_protocol.md`
- active rerun spec:
  - `config/external_validation_biorxiv_blind_sets_v6.json`
- archived original spec:
  - `config/external_validation_biorxiv_blind_sets_v1.json`
- run summary:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/summary.json`
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/summary.md`

## Required Per-Set Files

For each of:

- `set1_core_blind`
- `set2_expanded_ood`
- `set3_operational_smoke`

include:

- `manifest.json`
- `manifest.md`
- zipped bundle
- copied domain artifacts under `files/`

## Required Provenance Fields

- protocol id and version
- frozen timestamp
- current baseline references
- per-task run return code
- per-task run log path
- per-task raw pass vs effective pass
- acceptance note when smoke-specific override is used

## Required IDP Artifacts

- current release manifest
- release regression
- release report
- current smoke summary/regression for the smoke set

## Required Ligand Artifacts

- outer stress summary
- nested pipeline summary
- stage5 ranking summary
- stage45 integrity summary when available
- copied config profile used for the run

## Reviewer-Facing Notes

- operational smoke is supportive evidence, not the primary claim set
- smoke acceptance uses preregistered diagnostic override only for `ranking_eval_unique_keys` at `n=64`
- full ligand runs and full IDP runs are interpreted without smoke-specific overrides

## Final Packaging Command

After the preregistered run finishes:

```bash
python3 tools/build_biorxiv_external_validation_package.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_<tag>
```

## One-Shot Runner

```bash
python3 tools/run_biorxiv_external_validation_current.py \
  --tag <tag> \
  --sets set3_operational_smoke,set1_core_blind,set2_expanded_ood
```

## Validate Spec Before Running

```bash
python3 tools/run_external_validation_blind_sets.py \
  --set-spec-json config/external_validation_biorxiv_blind_sets_v6.json \
  --validate-only
```

## Partial Package Mode

If validation stops before the full run summary is written, you can still build a reviewer-facing partial package:

```bash
python3 tools/build_biorxiv_external_validation_package.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_<tag> \
  --allow-partial
```

## Resume a Stale Run

If the one-shot wrapper becomes stale, resume it with the frozen tag/spec/sets:

```bash
python3 tools/resume_biorxiv_external_validation.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_<tag>
```

Check status with:

```bash
python3 tools/monitor_biorxiv_external_validation.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_<tag>
```

## Recovery Planner

To write a recovery plan and suggested next actions for a stale or partial run:

```bash
python3 tools/recover_biorxiv_external_validation.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_<tag>
```

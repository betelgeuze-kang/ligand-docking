# IDP Release Changelog

## 2026-03-21

### Promoted Full Baseline

- current release label:
  - `idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3`
- canonical manifest:
  - `runs/idp_3bead_release_manifest_current.json`
- canonical report:
  - `runs/idp_3bead_release_report_current.md`

### Acceptance

- `all_fold_pass = true`
- `corrected_pass_folds = 20 / 20`
- `combined_gate_pass = true`
- regression:
  - `runs/idp_3bead_release_regression_current.json`
  - `pass = true`

### Runtime Delta Versus Previous Current

- `train_eval_speedup_frac = 0.02058`
- `eval_corrected_speedup_frac = 0.01291`

### What Changed

- promoted `speedopt3` as the new current baseline
- default-off pairwise contact diagnostics in the Rust sticker/bridge path:
  - `sticker_contacts`
  - `pi_pi_contacts`
  - `cation_pi_contacts`
  - `bridge_contacts`
- kept diagnostics opt-in through:
  - `IDP_PAIRWISE_CONTACT_DIAGNOSTICS=1`

### Reliability Hardening

- evaluator stages now retry once on retryable GPU memory faults
- monitor distinguishes:
  - `RUNNING`
  - `COMPLETED`
  - `STALE`
  - `STOPPED`
- stale progress files no longer imply active execution

### Promoted Smoke Reference

- current smoke label:
  - `idp_3bead_release_smoke_current_2026-03-20_speedopt3full`
- canonical smoke meta:
  - `runs/idp_3bead_release_smoke_current.json`
- canonical smoke summary:
  - `runs/idp_3bead_release_smoke_summary_current.json`

### Current Validation Snapshot

- local CI + current smoke:
  - `runs/idp_3bead_release_ci_smoke_current_2026-03-21.json`
- result:
  - `pytest: 15 passed`
  - `smoke: 7 / 7 pass`

### Notes

- release criterion remains fold-level:
  - `all_fold_pass = true`
- mixed-branch combined gate now uses branch-conditioned relevant PR-AUC metrics
- raw global aggregation PR-AUC remains diagnostic only


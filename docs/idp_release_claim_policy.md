# IDP Release Claim Policy

## Release Criterion

- Release verdict follows `all_fold_pass`.
- `combined_gate_pass` is diagnostic and does not override a `20/20` fold-level pass.
- Regression acceptance requires:
  - candidate `pass = true`
  - candidate `all_fold_pass = true`
  - no drop in corrected fold pass count versus the promoted baseline

## Allowed External Claims

- `The current release passed 20/20 fold-level holdout evaluation.`
- `The promoted baseline is the holdout run referenced by runs/idp_3bead_release_manifest_current.json.`
- `Branch/state/ranking fold-level gates are the release criterion.`
- `Combined macro gate metrics are tracked as diagnostics.`
- `Physics hotspot diagnostics are tracked and must remain zero for the promoted baseline.`

## Allowed Internal Claims

- `combined_gate_pass` may remain false when `all_fold_pass` is true.
- `combined_gate_pass` may also be true under branch-conditioned combined metrics without changing the fold-level release criterion.
- `aggregation_flag_pr_auc` may be below the historical macro threshold without blocking release if fold-level gates all pass.
- `aggregation_relevant_pr_auc` is the release-facing aggregation metric for mixed-branch combined evaluation.
- calibrated global aggregation diagnostics may be used for internal monitoring, trend review, and candidate comparison.
- `physics_gate_mode` may remain `advisory` while hotspot diagnostics are zero.

## Disallowed Claims

- `Absolute physical observables are production-accurate across all targets.`
- `Combined macro aggregation PR-AUC passes the release threshold.`
- `The engine no longer requires expert review.`
- `generic_nonbonded replacement is part of the promoted baseline.`
- `pairwise fastpair optimization is part of the promoted baseline.`
- `The release is suitable for fully automated external decision-making without guardrails.`

## Rejected Experimental Paths

- `runs/idp_3bead_holdout_v7_fastpair_2026-03-16_r1` is not promoted.
- Reason:
  - representative 3-fold stayed pass
  - full 20-fold regressed to `18/20`
  - end-to-end runtime gain was too small to justify the regression
- Current promoted baseline remains the manifest referenced by:
  - `runs/idp_3bead_release_manifest_current.json`

## Required Artifacts

- `runs/idp_3bead_release_baseline_current.json`
- `runs/idp_3bead_release_manifest_current.json`
- `runs/idp_3bead_release_regression_current.json`
- `runs/idp_3bead_release_report_current.md`
- `runs/idp_3bead_release_smoke_current.json`
- holdout summary and combined gate JSON referenced by the current manifest

## Current Baseline

- full release:
  - `idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3`
- smoke reference:
  - `idp_3bead_release_smoke_current_2026-03-20_speedopt3full`

# GPCR Residual Prototype Plan

## Purpose

This note narrows the next commercialization experiment to the smallest useful slice:

- the measured `GPCR 100k` failure
- an equal-size `10k` A/B scaffold
- a shadow-only residual prototype

Current artifacts:

- `runs/gpcr_residual_prototype_spec_current.md`
- `runs/gpcr_residual_ab_summary_current.md`

## Why This Slice First

The current `100k` commercialization run is already execution-valid:

- `runs/ligand_scaleup_100k_test_audit_current.md`

The one measured quality failure is:

- `gpcr_core_full`

and its error mode is already known:

- top-rank hard-decoy intrusion
- prior-dominated decoys with weak geometry/contact support

That makes GPCR the right first family for a residual prototype.

## Prototype Rules

The prototype should be:

- `shadow_only`
- `equal_size`
- `claim_safe by construction`

That means:

- no release promotion
- no 100k routing yet
- no hidden score replacement

Only these should change:

- residual metadata
- A/B candidate profiles
- comparison scaffolding

## Current Plan

1. use `runs/gpcr_residual_prototype_spec_current.md` as the feature contract
2. use `runs/gpcr_residual_ab_summary_current.md` as the candidate scaffold
3. use the stage3 scoring runtime hook that now emits shadow residual telemetry at `stage5_ranking`
4. run equal-size baseline/candidate GPCR A/B
5. inspect:
   - `pass -> fail` transitions
   - `PR-AUC` drift
   - `top20` drift
   - whether the false-positive GPCR pattern actually shrinks
6. only then consider a `100k` router experiment

## What Counts As Success

- `no pass -> fail`
- first two binders remain stable
- later GPCR binders recover upward relative to current `100k`
- correction stays inside the prototype delta caps
- the runtime hook remains auditable and easy to disable

## What Counts As Failure

- any equal-size regression that breaks the current GPCR accepted slice
- residual deltas that are large but poorly explained
- behavior that depends on run-level scaling instead of stable family calibration
- speed costs without a plausible path to future routing gains

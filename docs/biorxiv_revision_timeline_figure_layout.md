# Figure Layout Draft: Corrective Validation Timeline

## Purpose

This figure should help a reviewer understand two things quickly:

1. why multiple corrective reruns existed, and
2. why `v6r3` is the accepted close-out rather than an arbitrary late-stage run.

The figure should feel like an audit trail, not a marketing graphic.

## Recommended Format

- landscape layout
- `5` panels total
- simple left-to-right reading order
- use one accent color for accepted nodes and one muted color for failed/intermediate nodes
- avoid dense paragraphs inside the figure; keep explanations in the legend

## Panel A: Revision Timeline

### Title

`A. Corrective validation timeline`

### Content

Render a left-to-right timeline with the following nodes:

- `v1`
- `v2`
- `v3`
- `v4`
- `v5`
- `v6r1`
- `v6r3`

### Suggested node text

- `v1`
  - original frozen preregistration
  - kinase infra + split confounds discovered
- `v2`
  - writable heavy root
  - disjoint no-leak kinase split
- `v3`
  - blind GPCR/TRPV1 score wiring fixed to produced score
- `v4`
  - kinase gate mismatch corrected
- `v5`
  - narrow GPCR score exploration
- `v6r1`
  - GPCR live-run metadata propagation bug discovered
- `v6r3`
  - accepted close-out
  - all preregistered sets passing

### Arrow labels

- `v1 -> v2`: infra + leakage correction
- `v2 -> v3`: score wiring correction
- `v3 -> v4`: kinase gate correction
- `v4 -> v5`: GPCR-only residual blocker
- `v5 -> v6r1`: GPCR scorefix3 live rerun
- `v6r1 -> v6r3`: inline-score ligand priors fix

## Panel B: Set-Level Outcome Summary

### Title

`B. Final preregistered set outcomes`

### Content

Small table or matrix with rows:

- `Core Blind Set`
- `Expanded OOD Set`
- `Operational Smoke Set`

Columns:

- `Claim role`
- `Accepted result`

Values:

- `Core Blind Set` / `primary` / `PASS`
- `Expanded OOD Set` / `secondary_generalization` / `PASS`
- `Operational Smoke Set` / `reproducibility_support` / `PASS`

### Design note

This panel should be visually minimal. It is the “all three sets passed” anchor.

## Panel C: Domain-by-Set Main Table

### Title

`C. Cross-domain validation matrix`

### Content

Use `runs/biorxiv_external_validation_main_table_current.md` as the direct source.

Rows:

- `set1_core_blind`
- `set2_expanded_ood`
- `set3_operational_smoke`

Columns:

- `GPCR`
- `Ion channel`
- `Kinase`
- `IDP`

### Suggested emphasis

Bold the `GPCR core blind` cell because it was the final blocker that was closed in `v6r3`.

## Panel D: GPCR Core Close-Out

### Title

`D. GPCR core blind blocker closed in v6r3`

### Content

Simple before/after comparison between:

- `v4r1 gpcr_core_full`
- `v6r3 gpcr_core_full`

Metrics to show:

- `PR-AUC`
- `top20 hit rate`
- `top20 hits`

### Recommended numbers

- `v4r1`
  - `PR-AUC = 0.4336`
  - `top20 hit rate = 0.15`
  - `top20 hits = 3`
- `v6r3`
  - `PR-AUC = 1.0`
  - `top20 hit rate = 0.30`
  - `top20 hits = 6`

### Caption note

Call out that the close-out came from:

- `binding_score_composite_v7`
- plus the inline-score ligand-prior propagation fix

and not from a blanket GPCR gate relaxation.

## Panel E: Reviewer-Ready Package

### Title

`E. Accepted package and audit status`

### Content

Show the final accepted package identity:

- accepted run:
  - `2026-03-22_biorxiv_v6r3`
- package:
  - `runs/biorxiv_external_validation_package_current.zip`
- audit:
  - `pass = true`
  - `failure_count = 0`

Optional small file list:

- `reviewer_summary_current.md`
- `claim_matrix_current.md`
- `main_table_current.md`
- `supplementary_task_table_current.md`

## Figure Styling Notes

- keep backgrounds clean and light
- use green only for final accepted states
- use muted gray for archived revisions
- use amber for corrective intermediate revisions
- use red only for explicit blockers discovered at a given revision
- do not overload the figure with raw logs or file paths except in Panel E

## Source Files For Figure Construction

- timeline context:
  - `docs/biorxiv_protocol_revision_notes.md`
- accepted summary:
  - `runs/biorxiv_external_validation_reviewer_summary_current.md`
- main table:
  - `runs/biorxiv_external_validation_main_table_current.md`
- supplementary table:
  - `runs/biorxiv_external_validation_supplementary_task_table_current.md`
- package audit:
  - `runs/biorxiv_external_validation_audit_current.json`

## Suggested Figure Caption

`Figure X. Corrective revision history and final accepted cross-domain validation package. The original frozen preregistration record (v1) was preserved unchanged, and subsequent revisions addressed infrastructure, split leakage, score wiring, kinase-specific gate mismatch, and finally a GPCR live-run metadata propagation bug. The accepted reviewer-ready package is v6r3, which passes all three preregistered sets: Core Blind, Expanded OOD, and Operational Smoke.`

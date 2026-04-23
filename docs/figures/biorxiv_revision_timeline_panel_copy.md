# Figure Panel Copy: Corrective Validation Timeline

## Panel A

Title:
- `A. Corrective validation timeline`

Short node labels:
- `v1`: Frozen preregistration; kinase infra and split confounds discovered
- `v2`: Writable heavy root; disjoint no-leak kinase split
- `v3`: Blind GPCR/TRPV1 score wiring fixed to produced score
- `v4`: Kinase gate mismatch corrected
- `v5`: Narrow GPCR residual blocker exploration
- `v6r1`: GPCR live-run metadata propagation bug discovered
- `v6r3`: First all-pass close-out
- `v7r1`: Promoted current package after baseline gauntlet

Arrow labels:
- `v1 -> v2`: infra + leakage correction
- `v2 -> v3`: score wiring correction
- `v3 -> v4`: kinase gate correction
- `v4 -> v5`: GPCR-only residual blocker
- `v5 -> v6r1`: scorefix3 live rerun
- `v6r1 -> v6r3`: inline-score ligand priors fix
- `v6r3 -> v7r1`: winner-informed score remapping

## Panel B

Title:
- `B. Final preregistered set outcomes`

Rows:
- `Core Blind Set | primary | PASS`
- `Expanded OOD Set | secondary_generalization | PASS`
- `Operational Smoke Set | reproducibility_support | PASS`

## Panel C

Title:
- `C. Cross-domain validation matrix`

Source:
- `runs/biorxiv_external_validation_main_table_current.md`

Callout:
- Bold the `set1_core_blind / GPCR` cell because it was the final blocker closed in `v6r3`.

## Panel D

Title:
- `D. GPCR core blind blocker closed in v6r3`

Before/after:
- `v4r1`
  - `PR-AUC = 0.4336`
  - `top20 hit rate = 0.15`
  - `top20 hits = 3`
- `v6r3`
  - `PR-AUC = 1.000`
  - `top20 hit rate = 0.30`
  - `top20 hits = 6`

Callout text:
- `Close-out came from binding_score_composite_v7 plus the inline-score ligand-prior propagation fix, not from a blanket GPCR gate relaxation.`

## Panel E

Title:
- `E. Promoted package and audit status`

Display:
- `First all-pass close-out: 2026-03-22_biorxiv_v6r3`
- `Current promoted package: 2026-03-22_biorxiv_v7r1`
- `Package: runs/biorxiv_external_validation_package_current.zip`
- `Audit: pass = true; failure_count = 0`

Optional file list:
- `reviewer_summary_current.md`
- `claim_matrix_current.md`
- `main_table_current.md`
- `supplementary_task_table_current.md`

## Suggested Caption

`Figure X. Corrective revision history and final promoted cross-domain validation package. The original frozen preregistration record (v1) was preserved unchanged, and subsequent revisions addressed infrastructure, split leakage, score wiring, kinase-specific gate mismatch, and finally a GPCR live-run metadata propagation bug. The first fully passing close-out is v6r3. The current promoted reviewer-ready package is v7r1, which preserves all three preregistered set passes and improves selected ligand tasks under the same frozen evaluator.`

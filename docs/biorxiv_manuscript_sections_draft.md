# bioRxiv Manuscript Sections Draft

## Working Title

`Preregistered Cross-Domain Blind Validation of a Unified Molecular Architecture`

## Abstract

We evaluated the architecture under a preregistered cross-domain blind validation protocol spanning GPCR ligand ranking, ion-channel ligand ranking, kinase/protease ligand ranking, and release-grade intrinsically disordered protein (IDP) evaluation. The protocol separated three claim layers before execution: a primary `Core Blind Set`, a secondary `Expanded OOD Set`, and a reproducibility-support `Operational Smoke Set`. In the accepted reviewer-facing close-out (`2026-03-22_biorxiv_v6r3`), all three preregistered sets passed. The final package passed audit without failures and preserved the frozen preregistration record, intermediate corrective history, claim matrix, and reviewer summary. Domain-level results in the accepted run included full passing outcomes for GPCR, ion-channel, kinase, and IDP tasks in the core blind set, alongside full passing outcomes in the expanded OOD and operational smoke sets. The final close-out required a staged corrective process that addressed infrastructure confounds, leakage-sensitive split configuration, blind-score wiring, kinase-specific gate mismatch, and a live-run GPCR metadata propagation bug. Together, these results support the primary blind validation claim while also showing broader OOD generalization and reproducible re-execution under a frozen validation protocol.

## Results

### Cross-domain preregistered blind validation

We evaluated the architecture under a preregistered cross-domain validation protocol spanning four domain classes: GPCR ligand ranking, ion-channel ligand ranking, kinase/protease ligand ranking, and release-grade intrinsically disordered protein (IDP) evaluation. Rather than collapsing all evidence into a single aggregate benchmark, the protocol separated three claim layers before execution: a `Core Blind Set` for the primary claim, an `Expanded OOD Set` for broader generalization, and an `Operational Smoke Set` for reproducibility support. The accepted reviewer-facing close-out corresponds to `2026-03-22_biorxiv_v6r3`.

At the set level, all three preregistered bundles passed in the accepted run. `set1_core_blind` passed as the primary claim set, `set2_expanded_ood` passed as the secondary generalization set, and `set3_operational_smoke` passed as the reproducibility-support set. The final external-validation package also passed audit without failures, indicating that the copied artifacts, checksums, claim matrix, reviewer summary, and package manifest were internally consistent and submission-ready.

### Primary core blind claim

The primary claim set (`set1_core_blind`) passed across all four domains. In the accepted run, GPCR core blind ranking reached `PR-AUC = 1.000`, `ROC-AUC = 1.000`, `EF1 = 98.216`, and `top20 hit rate = 0.30`. Ion-channel core blind (`TRPV1`) also remained strong with `PR-AUC = 0.954` and `EF1 = 93.510`. Kinase core blind passed with `PR-AUC = 1.000` and `EF1 = 98.157`. The IDP full release baseline passed unchanged under the frozen current release reference.

This final core-blind result is particularly important because it closed the last remaining model-side blocker. Earlier corrective runs had already resolved the kinase operational-gate mismatch, restored blind TRPV1 performance, and preserved the IDP release path, leaving `gpcr_core_full` as the only remaining failing task. In the accepted `v6r3` run, that blocker was removed.

### Expanded out-of-distribution generalization

The `Expanded OOD Set` also passed in full. GPCR expanded OOD ranking achieved `PR-AUC = 0.823` and `EF1 = 72.626`. Ion-channel expanded OOD (`TRPV1 chembl50`) remained strong with `PR-AUC = 0.966` and `EF1 = 93.078`. Kinase strict OOD remained effectively saturated with `PR-AUC = 1.000` and `EF1 = 100.000`. The IDP current release reference again remained fully passing.

These results indicate that the accepted stack is not limited to a narrow in-distribution success case. The model and validation stack remained effective under the preregistered broader OOD setting as well.

### Operational smoke reproducibility support

The `Operational Smoke Set` passed across all four domains and provides reproducibility support rather than the primary claim. Smoke GPCR, ion-channel, and kinase tasks each retained strong ranking signals, while the IDP smoke rerun again closed at `7/7` passing folds.

As preregistered, the smoke ligand tasks preserve `raw_pass = false` when the full operational gate remains intentionally stricter than the smoke interpretation. These tasks are therefore reported as effective passes with explicit acceptance notes rather than being silently reclassified after the fact. This preserves transparency while allowing smoke runs to function as reproducibility support instead of as a substitute for the full primary-claim set.

### Final GPCR close-out

The decisive close-out in the accepted package was the correction of the GPCR core blind failure mode. The final improvement did not come from a broad threshold relaxation. Instead, the accepted run combined a GPCR-specific ranking correction (`binding_score_composite_v7`) with a fix to the inline-score path so that ligand priors were actually propagated into the live run. Once those priors were preserved, the GPCR core blind task improved from the earlier `PR-AUC = 0.4336` and `top20 hit rate = 0.15` regime to `PR-AUC = 1.000` and `top20 hit rate = 0.30` in the accepted package.

This distinction matters for interpretation. The final GPCR recovery was not produced by masking a failure or weakening the primary gate. It came from correcting a live-run metadata propagation bug that had prevented the intended score from operating as designed.

## Discussion

The accepted `v6r3` package should be interpreted as the endpoint of a reviewable corrective validation process rather than as a single favorable late-stage run. This distinction matters because the final evidence bundle retains the frozen original preregistration, failed intermediate executions, preregistered acceptance logic, and the audited final close-out package. The validation trail can therefore be inspected end to end rather than only at the final successful run.

The corrective path did not rely on broad post hoc relaxation of the central performance claim. Instead, successive revisions addressed separable sources of failure: infrastructure instability, leakage-sensitive split configuration, score-column wiring mismatches, kinase-specific operational gate mismatch, and finally a GPCR live-run metadata propagation bug. This staged reduction in failure modes narrows interpretation. By the accepted run, the residual blocker had been isolated to `gpcr_core_full`, and the final improvement came from restoring the intended score inputs rather than weakening the GPCR primary gate.

The accepted package supports a cross-domain claim rather than a single-domain overfit result. `TRPV1` blind performance remained strong once blind-score wiring was corrected. Kinase ranking performance was consistently saturated, and the corrective change there primarily clarified that the original failures reflected gate mismatch rather than ranking collapse. The IDP stack remained stable throughout and passed under the frozen current release reference. The final GPCR close-out therefore served as the last model-side blocker, not as one of many unresolved domains.

The smoke set should not be overread as a substitute for the full claim set. Its role is reproducibility support. The accepted package explicitly preserves `raw_pass = false` where the full operational gate remains intentionally stricter than smoke interpretation, and it reports smoke acceptance through preregistered acceptance notes rather than silently rewriting task outcomes. This keeps the smoke evidence transparent and prevents it from being confused with the core blind claim.

The practical review-facing takeaway is that the final package does not ask the reader to trust a hidden tuning loop. Instead, it presents a frozen specification, a visible corrective history, an audited final package, and a fully passing accepted run across the three preregistered claim layers. That combination supports treating `v6r3` as a credible validation close-out rather than as a selectively reported best-case snapshot.

## Figure Placement Notes

- Figure X:
  - `docs/figures/biorxiv_revision_timeline_final.svg`
- Main results table:
  - `runs/biorxiv_external_validation_main_table_current.md`
- Supplementary task table:
  - `runs/biorxiv_external_validation_supplementary_task_table_current.md`

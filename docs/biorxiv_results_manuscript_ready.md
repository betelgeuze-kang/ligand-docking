# Manuscript-Ready Results Draft For bioRxiv

## Cross-domain preregistered blind validation

We evaluated the architecture under a preregistered cross-domain validation protocol spanning four domain classes: GPCR ligand ranking, ion-channel ligand ranking, kinase/protease ligand ranking, and release-grade intrinsically disordered protein (IDP) evaluation. Rather than collapsing all evidence into a single aggregate benchmark, the protocol separated three claim layers before execution: a `Core Blind Set` for the primary claim, an `Expanded OOD Set` for broader generalization, and an `Operational Smoke Set` for reproducibility support. The first fully passing corrective close-out corresponded to `2026-03-22_biorxiv_v6r3`, and the current promoted reviewer-facing package is `2026-03-22_biorxiv_v7r1`.

At the set level, all three preregistered bundles passed in both the initial all-pass close-out and the promoted current package. `set1_core_blind` passed as the primary claim set, `set2_expanded_ood` passed as the secondary generalization set, and `set3_operational_smoke` passed as the reproducibility-support set. The current external-validation package also passed audit without failures, indicating that the copied artifacts, checksums, claim matrix, reviewer summary, and package manifest were internally consistent and submission-ready.

## Primary core blind claim

The primary claim set (`set1_core_blind`) passed across all four domains. In the promoted current run, GPCR core blind ranking reached `PR-AUC = 1.000`, `ROC-AUC = 1.000`, `EF1 = 98.216`, and `top20 hit rate = 0.30`. Ion-channel core blind (`TRPV1`) improved further to `PR-AUC = 1.000` and `EF1 = 98.431`. Kinase core blind passed with `PR-AUC = 1.000` and `EF1 = 98.157`. The IDP full release baseline passed unchanged under the frozen current release reference.

This final core-blind result is particularly important because it closed the last remaining model-side blocker and remained stable after subsequent score-selection refinement. Earlier corrective runs had already resolved the kinase operational-gate mismatch, restored blind TRPV1 performance, and preserved the IDP release path, leaving `gpcr_core_full` as the only remaining failing task. In `v6r3`, that blocker was removed. In `v7r1`, the pass was preserved while TRPV1 core blind improved further under the winner-informed score mapping.

## Expanded out-of-distribution generalization

The `Expanded OOD Set` also passed in full. In the promoted current package, GPCR expanded OOD ranking improved to `PR-AUC = 0.988` and `EF1 = 88.568`, while ion-channel expanded OOD (`TRPV1 chembl50`) improved to `PR-AUC = 0.983` and `EF1 = 95.059`. Kinase strict OOD remained effectively saturated with `PR-AUC = 1.000` and `EF1 = 100.000`. The IDP current release reference again remained fully passing.

These results indicate that the accepted stack is not limited to a narrow in-distribution success case. The model and validation stack remained effective under the preregistered broader OOD setting as well.

## Baseline-guided promotion

After the first fully passing `v6r3` close-out, we ran a frozen score-column gauntlet before promoting the current reviewer-facing package. Across the `4` ligand tasks whose score mappings changed between `v6r3` and `v7r1`, the promoted package improved PR-AUC in `3` tasks and regressed in `0`. The largest gains were observed for `gpcr_chembl50_full` (`ΔPR-AUC = +0.1655`, `ΔEF1 = +15.9422`), `ion_trpv1_chembl20_full` (`ΔPR-AUC = +0.0460`, `ΔEF1 = +4.9216`), and `ion_trpv1_chembl50_full` (`ΔPR-AUC = +0.0171`, `ΔEF1 = +1.9804`). No set-level passes were lost during the `v6r3 -> v7r1` transition, so the promoted package should be interpreted as a baseline-guided refinement of the first all-pass close-out rather than as a threshold-relaxed replacement.

## Operational smoke reproducibility support

The `Operational Smoke Set` passed across all four domains and provides reproducibility support rather than the primary claim. Smoke GPCR, ion-channel, and kinase tasks each retained strong ranking signals, while the IDP smoke rerun again closed at `7/7` passing folds.

As preregistered, the smoke ligand tasks preserve `raw_pass = false` when the full operational gate remains intentionally stricter than the smoke interpretation. These tasks are therefore reported as effective passes with explicit acceptance notes rather than being silently reclassified after the fact. This preserves transparency while allowing smoke runs to function as reproducibility support instead of as a substitute for the full primary-claim set.

## Robustness battery

We then executed a completed robustness battery over the promoted `v7r1` stack while keeping targets, labels, gates, and task definitions frozen. This battery covered three perturbation modes: an embed-seed shift (`embed_seed_shift1`), a hard-decoy resampling shift (`decoy_seed_shift1`), and a harsher decoy-pressure extension with `12k` synthetic decoys (`decoy_pressure_12k`). All three scenarios again passed all preregistered sets (`set1_core_blind`, `set2_expanded_ood`, and `set3_operational_smoke`), showing that the promoted claim set was not dependent on a single favorable stochastic realization or on the original default decoy pressure.

At the task level, the robustness battery showed limited but interpretable metric drift rather than invariance. Across the completed scenarios, there were `0` pass-to-fail transitions. The near-invariant scenario was `embed_seed_shift1`, whereas the largest regression occurred in `gpcr_core_full` under `decoy_seed_shift1`, where `PR-AUC` decreased by `0.1574` and `top20 hit rate` by `0.05` while still remaining above the acceptance threshold. Under the harsher decoy-pressure scenario, `gpcr_core_full` and `gpcr_chembl50_full` both remained passing despite modest PR-AUC erosion, `TRPV1` shifts remained small, and kinase PR-AUC stayed flat while the full kinase claim set remained passing. We therefore interpret the accepted package as robust at the claim level under embed-seed perturbation, hard-decoy resampling, and increased decoy pressure, with the GPCR core task remaining the most perturbation-sensitive ligand task inside the still-passing regime.

## Final GPCR close-out

The decisive close-out in the corrective sequence was the correction of the GPCR core blind failure mode. The initial recovery did not come from broad threshold relaxation. Instead, `v6r3` combined a GPCR-specific ranking correction (`binding_score_composite_v7`) with a fix to the inline-score path so that ligand priors were actually propagated into the live run. Once those priors were preserved, the GPCR core blind task improved from the earlier `PR-AUC = 0.4336` and `top20 hit rate = 0.15` regime to `PR-AUC = 1.000` and `top20 hit rate = 0.30`. The subsequent `v7r1` promotion kept that GPCR recovery intact and improved selected non-GPCR ligand tasks without introducing regressions.

This distinction matters for interpretation. The final GPCR recovery was not produced by masking a failure or weakening the primary gate. It came from correcting a live-run metadata propagation bug that had prevented the intended score from operating as designed.

## Temporal-readiness boundary

We also prepared a runnable temporal-validation scaffold on top of the promoted package, but the temporal claim remains explicitly provisional. Since the initial provenance inventory, the ligand side has been promoted from dataset-level anchoring to full item-level readiness through ChEMBL-backed and named-ligand provenance facts. The IDP side has now been promoted further as well: `16/20` holdouts are item-level ready, including the full PDB-backed subset, `alpha_synuclein_full`, and a curated synthetic subset with construct-level literature anchors. The remaining `4/20` synthetic holdouts still rely on dataset-level anchors derived from the accepted current release manifest rather than per-holdout publication dates. One of those unresolved rows, `prion_like_polyq_control`, is intentionally retained as a dataset-level synthetic control until a construct-matched public disorder anchor is identified; the other three unresolved rows remain dataset-level because the current conservative curation sweep did not identify safe construct-matched public anchors. Accordingly, the temporal scaffold is now best interpreted as a mixed item-level and dataset-level package: ligand rows support item-level temporal claims, most IDP rows support item-level temporal claims, and only the remaining unresolved synthetic IDP rows stay dataset-level anchored pending further curation.

## Interpretation

The accepted validation package supports three claims simultaneously. First, the architecture passes the primary cross-domain blind validation claim under the `Core Blind Set`. Second, the architecture retains strong performance under the preregistered broader generalization regime captured by the `Expanded OOD Set`. Third, the frozen stack reruns reproducibly across the same domain mix under the `Operational Smoke Set`, with smoke-specific acceptance rules preserved explicitly rather than rewritten post hoc.

Taken together, the `v6r3 -> v7r1` close-out path should be interpreted as the end state of a reviewable corrective validation process rather than as a single favorable late-stage run. The submission bundle preserves the frozen preregistration record, failed intermediate history, revision notes, preregistered acceptance logic, the baseline-gauntlet comparison, and the audited promoted artifacts, allowing the validation trail to be reviewed end to end.

## Supporting Artifacts

- Main manuscript table:
  - `runs/biorxiv_external_validation_main_table_current.md`
- Baseline-gauntlet manuscript table:
  - `runs/biorxiv_baseline_gauntlet_main_table_current.md`
- Supplementary task table:
  - `runs/biorxiv_external_validation_supplementary_task_table_current.md`
- Robustness battery comparison:
  - `runs/biorxiv_robustness_comparison_summary_current.md`
- Robustness battery paragraph:
  - `runs/biorxiv_robustness_results_paragraph_current.md`
- Temporal provenance inventory:
  - `runs/biorxiv_temporal_provenance_inventory_current.md`
- Reviewer summary:
  - `runs/biorxiv_external_validation_reviewer_summary_current.md`
- Promoted current package:
  - `runs/biorxiv_external_validation_package_current.zip`

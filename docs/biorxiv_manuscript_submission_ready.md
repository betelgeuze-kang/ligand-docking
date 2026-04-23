# Submission-Ready Manuscript Draft

## Working Title

`Preregistered Cross-Domain Blind Validation of a Unified Molecular Architecture`

## Author Metadata

- Authors:
  - `JI HOON KANG`
- Affiliations:
  - `No institutional affiliation`
- Corresponding author:
  - `JI HOON KANG, betelgeuze0619@gmail.com`
- Author metadata template:
  - `docs/biorxiv_author_metadata_template.md`

## Introduction

Machine-learning and hybrid physics-based molecular ranking systems are often summarized through isolated benchmark wins, but those wins are hard to interpret when leakage controls, task definitions, and acceptance criteria vary across domains. The problem becomes sharper when a single architecture is claimed to support substantially different settings such as GPCR ligand ranking, ion-channel ligand ranking, kinase/protease prioritization, and intrinsically disordered protein (IDP) assessment. Under those conditions, a favorable result on one benchmark is not enough to support an architecture-level claim.

We therefore framed the present study around a preregistered cross-domain validation protocol rather than a post hoc benchmark collection. The protocol prospectively separated three claim layers: a `Core Blind Set` for the primary claim, an `Expanded OOD Set` for broader generalization, and an `Operational Smoke Set` for reproducibility support. This separation was intended to make interpretation stricter and easier to audit: full blind and OOD sets carry the main claims, whereas smoke reruns are explicitly limited to reproducibility support.

An additional design goal was to preserve the corrective history rather than overwrite it. During execution, successive issues emerged, including infrastructure instability, leakage-sensitive split configuration, blind-score wiring mismatch, kinase-specific gate mismatch, and finally a GPCR live-run metadata propagation bug. Rather than discarding those intermediate runs, we preserved them as reviewable evidence and used them to define a staged corrective close-out path. The accepted package should therefore be read as the endpoint of a visible debugging and validation trail rather than as an isolated favorable run.

The goal of this work is therefore narrower and more defensible than a claim of universal molecular prediction performance. We ask whether a single architecture, evaluated under a frozen and reviewable protocol, can pass a preregistered cross-domain blind claim set while also retaining broader OOD performance, reproducible rerun behavior, and interpretable provenance boundaries for the next temporal-validation layer. The first all-pass corrective close-out was `2026-03-22_biorxiv_v6r3`; the current promoted package is `2026-03-22_biorxiv_v7r1`, which preserves those passes while improving selected ligand tasks under the same frozen evaluator. A separate three-scenario robustness battery further tests whether that accepted package remains valid under changed ligand randomness and harsher decoy pressure without altering targets, labels, or thresholds.

## Abstract

We evaluated the architecture under a preregistered cross-domain blind validation protocol spanning GPCR ligand ranking, ion-channel ligand ranking, kinase/protease ligand ranking, and release-grade intrinsically disordered protein (IDP) evaluation. The protocol separated three claim layers before execution: a primary `Core Blind Set`, a secondary `Expanded OOD Set`, and a reproducibility-support `Operational Smoke Set`. The first fully passing corrective close-out was `2026-03-22_biorxiv_v6r3`, and the current promoted reviewer-facing package is `2026-03-22_biorxiv_v7r1`, which preserved all set passes while improving selected ligand tasks under a frozen evaluator. A completed robustness battery also preserved all three preregistered set passes under embed-seed perturbation, hard-decoy resampling, and increased decoy pressure, although the GPCR core task remained the most perturbation-sensitive ligand component within the still-passing regime. The final package passed audit without failures and preserved the frozen preregistration record, intermediate corrective history, claim matrix, reviewer summary, and comparison artifacts. Domain-level results in the promoted current package included full passing outcomes for GPCR, ion-channel, kinase, and IDP tasks in the core blind set, alongside full passing outcomes in the expanded OOD and operational smoke sets. In parallel, we prepared a runnable temporal scaffold whose provenance state is now mostly item-level (`202/206` rows item-ready), with the remaining `4/206` rows explicitly policy-coded rather than hidden; this scaffold should be interpreted as a conservative temporal extension layer rather than as a completed future-only benchmark. Together, these results support a strong computational blind-validation claim while also showing broader OOD generalization, score-selection robustness, robustness-battery stability at the claim level, and a transparent path toward stricter temporal validation, while stopping short of any prospective wet-lab hit-discovery claim.

## Results

### Preregistered cross-domain validation design

The validation protocol was designed to separate evidentiary roles before execution rather than collapse all outcomes into a single mixed benchmark. `set1_core_blind` carried the primary claim, `set2_expanded_ood` evaluated broader generalization, and `set3_operational_smoke` served as reproducibility support. The first full-pass close-out corresponds to `2026-03-22_biorxiv_v6r3`, while the currently promoted reviewer-facing package corresponds to `2026-03-22_biorxiv_v7r1`, and the associated package audit passed without failures.

### Primary core blind claim

The primary blind set passed across all four domains. GPCR core blind reached `PR-AUC = 1.000`, `ROC-AUC = 1.000`, `EF1 = 98.216`, and `top20 hit rate = 0.30`. Ion-channel core blind (`TRPV1`) improved further to `PR-AUC = 1.000` and `EF1 = 98.431`. Kinase core blind passed with `PR-AUC = 1.000` and `EF1 = 98.157`. The frozen current IDP release baseline also passed unchanged.

This core-blind outcome is especially important because it closed the final model-side blocker. Earlier corrective runs had already restored TRPV1 blind performance, resolved the kinase operational-gate mismatch, and preserved the IDP release path, leaving `gpcr_core_full` as the only remaining failing task. In `v6r3`, that blocker was removed, and in `v7r1` that core-blind pass was preserved.

### Expanded out-of-distribution generalization

The expanded OOD set also passed in full. GPCR expanded OOD ranking achieved `PR-AUC = 0.988` and `EF1 = 88.568`. Ion-channel expanded OOD (`TRPV1 chembl50`) improved to `PR-AUC = 0.983` and `EF1 = 95.059`. Kinase strict OOD remained effectively saturated at `PR-AUC = 1.000` and `EF1 = 100.000`. The IDP current release reference again remained fully passing. These results indicate that the accepted stack is not restricted to a narrow in-distribution success case.

### Baseline-guided promotion

After the first fully passing `v6r3` close-out, we ran a frozen score-column gauntlet before promoting the current reviewer-facing package. Across the `4` ligand tasks whose score mappings changed between `v6r3` and `v7r1`, the promoted package improved PR-AUC in `3` tasks and regressed in `0`. The largest gains were observed for `gpcr_chembl50_full` (`ΔPR-AUC = +0.1655`, `ΔEF1 = +15.9422`), `ion_trpv1_chembl20_full` (`ΔPR-AUC = +0.0460`, `ΔEF1 = +4.9216`), and `ion_trpv1_chembl50_full` (`ΔPR-AUC = +0.0171`, `ΔEF1 = +1.9804`). No set-level passes were lost during the `v6r3 -> v7r1` transition, so the promoted package should be read as a baseline-guided refinement of the first all-pass close-out rather than as a threshold-relaxed replacement.

### Operational smoke reproducibility support

The operational smoke set passed across all four domains and functions as reproducibility support rather than as the primary performance claim. Smoke GPCR, ion-channel, and kinase tasks retained strong ranking signals, while the IDP smoke rerun again closed at `7/7` passing folds. Consistent with the preregistered protocol, smoke ligand tasks preserve `raw_pass = false` where the full operational gate remains intentionally stricter than smoke interpretation. Smoke outcomes are therefore reported as effective passes with explicit acceptance notes rather than being silently reclassified after the fact.

### Final GPCR close-out

The decisive final correction was the removal of the GPCR core blind failure mode. This improvement did not come from broad threshold relaxation. Instead, `v6r3` combined a GPCR-specific ranking correction (`binding_score_composite_v7`) with a fix to the inline-score path so that ligand priors were actually propagated into the live run. Once those priors were preserved, GPCR core blind improved from `PR-AUC = 0.4336` and `top20 hit rate = 0.15` in the earlier corrective state to `PR-AUC = 1.000` and `top20 hit rate = 0.30` in the close-out package. The promoted `v7r1` run preserved that GPCR recovery while improving selected non-GPCR ligand tasks.

### Temporal-readiness boundary

We also prepared a runnable temporal-validation scaffold on top of the promoted package, but the temporal claim remains explicitly provisional. Since the initial provenance inventory, the ligand side has been promoted to full item-level readiness through ChEMBL-backed and named-ligand provenance facts. The IDP side has now been promoted further as well: `16/20` holdouts are item-level ready, including the full PDB-backed subset, `alpha_synuclein_full`, and a curated synthetic subset with construct-level literature anchors, while the remaining `4/20` synthetic holdouts still rely on dataset-level anchors derived from the accepted current release manifest rather than per-holdout publication dates. `prion_like_polyq_control` is intentionally kept dataset-level because it functions as a synthetic control without a construct-matched public disorder anchor, and the other three unresolved synthetic rows remain dataset-level because the current conservative sweep did not identify safe construct-matched public anchors. Accordingly, the temporal scaffold should now be read as a mixed item-level and dataset-level package rather than as a completed item-level temporal generalization study.

## Discussion

The current `v7r1` package should be interpreted as the endpoint of a reviewable corrective validation process rather than as a single favorable late-stage run. This distinction matters because the evidence bundle retains the frozen original preregistration, failed intermediate executions, preregistered acceptance logic, the first fully passing `v6r3` close-out, the baseline-gauntlet comparison, and the audited promoted package. The validation trail can therefore be inspected end to end rather than only at the final successful run.

The corrective path did not rely on broad post hoc relaxation of the central performance claim. Instead, successive revisions addressed separable sources of failure: infrastructure instability, leakage-sensitive split configuration, score-column wiring mismatches, kinase-specific operational gate mismatch, and finally a GPCR live-run metadata propagation bug. A final winner-informed comparison step then improved selected non-GPCR ligand tasks without changing the pass/fail structure of the claim sets. This staged reduction in failure modes is important because it narrows interpretation. By `v6r3`, the residual blocker had been isolated to `gpcr_core_full`, and the key improvement came from restoring the intended score inputs rather than weakening the GPCR primary gate.

The accepted package supports a cross-domain claim rather than a single-domain overfit result. `TRPV1` blind performance remained strong once blind-score wiring was corrected. Kinase ranking performance was consistently saturated, and the corrective change there primarily clarified that the original failures reflected gate mismatch rather than ranking collapse. The IDP stack remained stable throughout and passed under the frozen current release reference. The final GPCR close-out therefore served as the last model-side blocker, not as one of many unresolved domains.

The robustness battery strengthens that interpretation without erasing where the stack remains most sensitive. Across `embed_seed_shift1`, `decoy_seed_shift1`, and `decoy_pressure_12k`, all three preregistered sets still passed and no ligand task crossed from pass to fail. At the same time, the comparison was not numerically flat: `embed_seed_shift1` was near-invariant, the hard-decoy perturbation scenarios produced the most visible drift, and `gpcr_core_full` showed the largest PR-AUC drop while still remaining comfortably within the passing regime. Kinase PR-AUC remained flat and `TRPV1` remained stable with only small movement. This is the right kind of robustness result for the current claim. It supports package-level stability and domain-level interpretability, while also showing that GPCR core blind remains the most perturbation-sensitive part of the ligand stack.

The temporal scaffold should be read in the same spirit. It is not presented as a completed per-row temporal generalization study or as a true future-only benchmark. Instead, it is reported as a reviewer-auditable intermediate state: ligand rows are fully item-level ready, most IDP rows are item-level ready, and the remaining four IDP rows are explicitly policy-coded as either no-safe-public-anchor, fragment-anchor mismatch, or intentional dataset-level control. This is stronger than an unstructured “future work” placeholder because the unresolved set is now small, typed, and frozen in the current submission bundle, but it still does not justify calling the provisional temporal runner a fully realized temporal split.

## Claim Scope And Limitations

It is important to keep the claim boundary explicit. The accepted package supports a strong computational statement under frozen and preregistered evaluation, but it does not by itself establish prospective wet-lab hit discovery, orthogonal biochemical confirmation, medicinal-chemistry optimization, downstream therapeutic utility, or a fully completed item-level temporal generalization claim. The fairest description is therefore an audited cross-domain computational validation package with a separately documented robustness battery and a partially item-level temporal scaffold, not an experimentally validated screening platform. That distinction strengthens the paper because it aligns the stated claim with the actual evidence bundle.

The temporal scaffold should be read under the same boundary. It is now strong enough to audit and extend, with `202/206` rows item-ready and the remaining `4/206` rows explicitly policy-coded, but it remains a mixed item-level and dataset-level temporal package rather than a fully completed per-row temporal generalization study. This limitation is already narrow, typed, and frozen in the submission assets rather than being left as an unstructured future-work note.

## Methods

### Validation overview

We evaluated the architecture under a preregistered cross-domain validation protocol spanning GPCR ligand ranking, ion-channel ligand ranking, kinase/protease ligand ranking, and release-grade IDP evaluation. The active promoted rerun specification was `config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json`, and the promoted current run was `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1`.

### Claim layers

The protocol separated three claim layers before execution. `set1_core_blind` carried the primary claim, `set2_expanded_ood` evaluated broader generalization, and `set3_operational_smoke` provided reproducibility support. Smoke evidence was not treated as a substitute for the primary claim set.

### Governance rules

The original preregistration record was preserved as historical evidence, and corrective reruns were issued through explicit new specs rather than by silently rewriting prior runs. Target assignments, ligand/control definitions, and domain membership were not swapped after freeze. IDP corrected evaluation used frozen-label sources from the current release manifest rather than candidate-specific relabeling.

### Domain-specific readouts

GPCR and ion-channel tasks were evaluated through blind stress summaries, retained ranking summaries, and copied stage5 artifacts. Kinase/protease tasks used external-style validation profiles with core and stricter OOD profiles separated across claim layers. IDP full evaluation used the frozen current release reference, while IDP smoke used the frozen current smoke reference.

### Acceptance rules

Full ligand tasks were accepted as reported by their produced stress summaries, without post hoc reinterpretation of failed full operational gates. For ligand smoke tasks at `n=64`, a preregistered smoke-specific interpretation rule allowed acceptance when stage5 ranking and stage45 integrity passed and the only failed stage6 metric was `ranking_eval_unique_keys`; in such cases `raw_pass = false` was preserved and the acceptance note was written explicitly in the manifest. IDP full acceptance required `all_fold_pass = true` and release regression `pass = true`.

### Packaging and audit

Each preregistered set published manifests, copied domain artifacts, per-task pass and raw-pass fields, and zipped bundles. The top-level promoted package additionally included a reviewer summary, claim matrix, copied file inventory, failure triage, checksums, and a reviewer HTML index. The final promoted package audit passed without failures.

The current close-out also includes a corrective ablation table (`runs/biorxiv_ablation_table_current.md`), a robustness evidence matrix (`runs/biorxiv_robustness_matrix_current.md`), and a SHA256 governance seal manifest over the current accepted artifacts (`runs/biorxiv_external_validation_governance_seal_current.md`).

### Robustness battery

After promoting `v7r1`, we executed a completed robustness battery across three frozen scenario layers. `embed_seed_shift1` changed only `csv_relax_embed_seed`; `decoy_seed_shift1` changed only `hard_decoy_synth_random_seed`; and `decoy_pressure_12k` increased synthetic hard-decoy pressure while preserving targets, labels, gates, and task structure. The scenario runner for these layers is `tools/run_biorxiv_robustness_scenario.py`, the battery dispatcher is `tools/run_biorxiv_robustness_battery_current.py`, and the completed comparison summary against the promoted current package is `runs/biorxiv_robustness_comparison_summary_current.json`. This layer should be interpreted as claim-level stability evidence: it shows that all preregistered set passes were preserved across the completed perturbations, but it does not justify saying that every domain is numerically invariant or that all EF1 values remain in the `90s`.

### Temporal scaffold and provenance audit

In addition to the accepted blind/OOD/smoke package, we built a runnable temporal scaffold spec (`config/external_validation_biorxiv_temporal_sets_v1_provisional.json`), provenance coverage reports (`runs/biorxiv_temporal_provenance_mapping_coverage_current.md`), and IDP item-level helper artifacts (`runs/biorxiv_temporal_idp_item_helpers_current.md`). The temporal scaffold now reuses frozen task profiles under a mixed governance regime: ligand rows are item-level ready, `16/20` IDP rows are item-level ready, and only the remaining `4/20` synthetic IDP holdouts remain dataset-level anchored until per-holdout provenance dates are curated.

The residual temporal gap is now policy-coded rather than opaque. Two unresolved synthetic rows remain dataset-level because the current conservative curation sweep did not identify safe construct-matched public anchors (`ash1_idr_fragment`, `eaf1_idr`), one remains dataset-level because a full-length public tau anchor was judged insufficient for the specific fragment (`tau_2n4r_fragment`), and one remains dataset-level by design as a synthetic control (`prion_like_polyq_control`). These residual rules are summarized in `runs/biorxiv_temporal_idp_remaining_policy_current.md` and frozen with the current submission bundle in `runs/biorxiv_temporal_submission_baseline_current.md`. The provisional temporal runner should therefore be interpreted as a mixed-governance scaffold rather than as a finished future-only temporal benchmark.

### Claim scope and non-claims

The accepted package supports a strong computational validation claim under frozen and preregistered evaluation, but it does not stand in for prospective wet-lab hit discovery, orthogonal biochemical confirmation, medicinal-chemistry optimization, clinical translation evidence, or a fully completed item-level temporal generalization claim. We therefore treat the final package as an audited computational validation artifact and the temporal scaffold as a conservative extension layer, not as a finished experimental or future-only prediction study.

## Figure And Table Callouts

- Main figure:
  - `docs/figures/biorxiv_revision_timeline_camera_ready.svg`
- Main validation table:
  - `runs/biorxiv_external_validation_main_table_current.md`
- Baseline-gauntlet manuscript table:
  - `runs/biorxiv_baseline_gauntlet_main_table_current.md`
- Supplementary task table:
  - `runs/biorxiv_external_validation_supplementary_task_table_current.md`
- Temporal provenance inventory:
  - `runs/biorxiv_temporal_provenance_inventory_current.md`
- Reviewer-ready package:
  - `runs/biorxiv_external_validation_package_current.zip`

## Declarations

### Data Availability

The reviewer-facing validation package is archived in `runs/biorxiv_external_validation_package_current.zip`, and the consolidated submission-facing bundle is archived in `runs/biorxiv_submission_assets_current.zip`.

### Code Availability

All scripts, configuration files, manuscript assets, and validation artifacts are maintained in the current repository root `/home/betelgeuze/분자동역학`. The reproducible submission bundle can be rebuilt with `python3 tools/build_biorxiv_submission_assets.py`.

### Funding

`No external funding.`

### Competing Interests

`The author declares no competing interests.`

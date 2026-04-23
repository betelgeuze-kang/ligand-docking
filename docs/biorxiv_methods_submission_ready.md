# Submission-Ready Methods Draft

## Validation Overview

We evaluated the architecture under a preregistered cross-domain validation protocol spanning GPCR ligand ranking, ion-channel ligand ranking, kinase/protease ligand ranking, and release-grade intrinsically disordered protein (IDP) evaluation. The active promoted rerun specification is `config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json`, the promoted current run is `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1`, and the corresponding reviewer-ready package is `runs/biorxiv_external_validation_package_current.zip`.

## Preregistered Claim Layers

The protocol prospectively separated three claim layers before execution. `Core Blind Set` carried the primary architecture-level blind validation claim, `Expanded OOD Set` carried a secondary generalization claim under broader out-of-distribution pressure, and `Operational Smoke Set` served as reproducibility support under a frozen stack. Smoke evidence was therefore not treated as a substitute for the primary claim set.

## Governance And Freeze Rules

The original preregistration record was preserved as historical evidence, and corrective reruns were issued through explicit new specifications rather than by silently rewriting prior runs. Target assignments, ligand/control definitions, and domain membership were not swapped after freeze. IDP corrected evaluation used frozen-label sources from the current release manifest rather than candidate-specific relabeling. The accepted protocol and claim-governance rules are summarized in `docs/biorxiv_architecture_validation_protocol.md`.

## Domain-Specific Readouts

### GPCR

GPCR tasks were evaluated through blind stress summaries, copied ranking artifacts, and retained stage5 ranking outputs. The final accepted GPCR core close-out used `binding_score_composite_v7`.

### Ion Channel

Ion-channel tasks used the same stress-validation structure as GPCR tasks, with `TRPV1` blind and smoke outputs retained as direct artifacts.

### Kinase/Protease

Kinase/protease tasks used external-style validation profiles, with core and stricter OOD profiles separated across claim layers. Corrective reruns distinguished ranking quality from operational-gate mismatch rather than treating every failure as a ranking collapse.

### IDP

IDP full evaluation used the frozen current release reference, including the current release manifest, regression outputs, and report artifacts. IDP smoke evaluation used the frozen current smoke reference.

## Acceptance Rules

### Full Ligand Sets

Full ligand tasks were accepted as reported by their produced stress summaries, without post hoc reinterpretation of failed full operational gates.

### Ligand Smoke Set

At `n=64`, smoke ligand tasks were allowed a limited preregistered interpretation rule. When `stage5_ranking_eval.ok = true`, `stage45_eval_integrity.ok = true`, and the only failed stage6 metric was `ranking_eval_unique_keys`, the task could be accepted as a smoke pass while preserving `raw_pass = false`. Smoke-specific acceptance notes were written explicitly in the set manifest rather than silently overwriting raw task outcomes.

### IDP Full Set

IDP full acceptance required `all_fold_pass = true` and release regression `pass = true`.

## Corrective Revision Path

The current `v7r1` package was reached through a staged corrective and comparison-driven sequence rather than a single tuning loop: `v2` addressed infrastructure and split issues, `v3` corrected blind GPCR/TRPV1 score wiring, `v4` corrected kinase operational-gate mismatch, `v5` narrowed the residual GPCR blocker, `v6r1` exposed the GPCR live-run ligand-prior propagation bug, `v6r3` delivered the first fully passing close-out after fixing the inline-score prior path, and `v7r1` preserved all set passes while improving selected ligand tasks after a frozen baseline-gauntlet comparison. This revision history is preserved in `docs/biorxiv_protocol_revision_notes.md`.

## Packaging And Audit

Each preregistered set published manifests, copied domain artifacts, per-task `pass` and `raw_pass` fields, and zipped bundles. The top-level promoted package additionally included a reviewer summary, claim matrix, copied file inventory, failure triage, checksums, and a reviewer HTML index. The promoted package audit passed without failures in `runs/biorxiv_external_validation_audit_current.json`. Additional review-facing close-out artifacts include the corrective ablation table (`runs/biorxiv_ablation_table_current.md`), the robustness evidence matrix (`runs/biorxiv_robustness_matrix_current.md`), the robustness-battery comparison summary (`runs/biorxiv_robustness_comparison_summary_current.md`), and the SHA256 governance seal manifest (`runs/biorxiv_external_validation_governance_seal_current.md`).

## Robustness Battery

After promoting `v7r1`, we executed a completed robustness battery across three frozen scenario layers. `embed_seed_shift1` changed only `csv_relax_embed_seed`; `decoy_seed_shift1` changed only `hard_decoy_synth_random_seed`; and `decoy_pressure_12k` increased the synthetic hard-decoy total while keeping targets, labels, gates, and task structure fixed. The scenario runner for these layers is `tools/run_biorxiv_robustness_scenario.py`, the battery dispatcher is `tools/run_biorxiv_robustness_battery_current.py`, and the completed comparison summary against the promoted current package is `runs/biorxiv_robustness_comparison_summary_current.json`. This battery should be interpreted as claim-level stability evidence: it shows that all preregistered set passes were preserved across the completed perturbations, but it does not justify saying that every domain is numerically invariant or that all EF1 values remain in the `90s`.

## Temporal Provenance Policy

The temporal scaffold was kept intentionally conservative. Ligand rows were promoted to item-level readiness only when release- or publication-level provenance could be attached directly to the evaluated ligand entries. IDP rows were promoted to item-level readiness only when a construct-matched or near-construct public anchor could be attached without relying on weak family-level inference. As a result, the current temporal baseline contains `16/20` item-ready IDP rows and `4/20` dataset-ready IDP rows. The remaining dataset-ready rows are explicitly partitioned into three categories rather than being treated as an undifferentiated missing set: no safe public anchor found (`ash1_idr_fragment`, `eaf1_idr`), fragment anchor mismatch (`tau_2n4r_fragment`), and intentional dataset-level synthetic control (`prion_like_polyq_control`). These policy boundaries are recorded in `runs/biorxiv_temporal_idp_remaining_policy_current.md` and frozen in `runs/biorxiv_temporal_submission_baseline_current.md`. The runnable provisional temporal spec should therefore be read as a mixed-governance scaffold rather than as a completed future-only temporal benchmark.

## Claim Scope And Non-Claims

The accepted package is intended to support a computational validation claim under frozen and preregistered evaluation. It is not intended to stand in for prospective wet-lab hit discovery, orthogonal biochemical confirmation, medicinal-chemistry optimization, clinical translation evidence, or a fully completed item-level temporal generalization claim. The manuscript therefore treats the final package as an audited computational validation artifact and reports the temporal scaffold as a mixed item-level and dataset-level extension layer rather than as a completed experimental, future-only, or prospective-discovery study.

# Commercial Tool Accuracy Gap Assessment - 2026-05-06

## Executive Verdict

API, hosting, and product wrapper concerns are intentionally out of scope for this pass. Judged only on scientific accuracy and defensible validation evidence, the current architecture is not yet at the level of established tools such as OpenMM, Schrödinger Glide/FEP+, GALAXY/GalaxyWEB, or Syntekabio-like AI discovery platforms.

Best current estimate:

| Claim scope | Current level vs established tools | Gap |
|---|---:|---:|
| Restricted local-delivery analysis service on already gated families | 70-75% | 25-30 pts |
| Accuracy-parity claim against commercial/standard tools overall | 40-50% | 50-60 pts |
| Broad commercial drug-discovery platform | 35-45% | 55-65 pts |

The strongest local evidence is in restricted release gating, reproducibility/claim governance, selected OpenMM 2-bead T. cruzi PDE evidence, and curated local wetlab packet flow. The main blockers are not API related. They are fair benchmark parity, GPCR ranking generalization, broad all-atom/OpenMM-class physics validation, GALAXY-class structure/refinement metrics, and prospective wetlab translation evidence.

Current A0 scorecard output now exists at `runs/accuracy_parity_scorecard_current.json` and `runs/accuracy_parity_scorecard_current.md`. It currently reports `blocked_accuracy_parity` with `0` pass rows, `1` restricted-pass row, `4` blocked rows, and `0` missing rows. The A1 execution queue also exists at `runs/gpcr_a1_accuracy_repair_queue_current.json` and `runs/gpcr_a1_accuracy_repair_queue_current.md`; DRD2 full-forcefield local-min evidence is now completed and the top repair is `drd2_hard_decoy_slice_rebuild`. The DRD2 support packet at `runs/gpcr_drd2_atom_typed_backmapping_support_current.md` now uses the pseudo-allatom repair lane and PDB-backed atom count: coverage is `1.0`, pose preservation is measured (`p90=0.13995901566518218 A`), integrated OpenMM protein-ligand parameterization is ready, and full-forcefield restrained-receptor local-min survival passes (`fraction=1.0`, ligand RMSD `1.9297168899124832 A` at a `2.0 A` threshold). Hard-decoy rebuild is now allowed as diagnostics, but claim/scorer/guarded-100k promotion remains blocked.

## Comparison Basis

This is an engineering estimate from local artifacts plus public product/tool descriptions, not a licensed head-to-head benchmark. Exact commercial parity cannot be claimed until the same targets, structures, ligands, decoys, protocols, and metrics are run under frozen conditions.

Public comparison anchors:

- OpenMM: molecular simulation toolkit with flexible custom forces/integrators, high-performance GPU execution, several platforms, and common force-field workflows.
- Schrödinger: Glide for ligand-receptor docking, pose prediction, high-throughput virtual screening, explicit-water-aware Glide WS, and FEP+ for physics-based binding free energy prediction.
- GALAXY/GalaxyWEB: protein structure prediction/refinement, complex refinement, protein-ligand docking, GPCR-ligand docking, and structure-quality outputs around RMSD/GDT/MolProbity-style metrics.
- Syntekabio: AI/supercomputing discovery workflow with large chemical libraries, AI screening, docking, MD/fine-tuning, and packaged candidate/asset workflows.

## Axis-Level Assessment

| Axis | Current evidence | Tool-level expectation | Gap assessment |
|---|---|---|---|
| OpenMM-class physics/dynamics | `runs/accuracy_gate_local_delivery_preflight_current.json` passes 11 targets with neighbor Jaccard 1.0 and force parity checks. `runs/openmm_2bead_strict_tcruzi_pde_current_accuracy_external.json` passes one external OpenMM T. cruzi PDE reference with avg RMSD 0.059 A. Long-stability summary reports avg aligned RMSD 0.143 and energy drift ratio 0.000284. | Broad topology/force-field coverage, all-atom and solvent-ready dynamics, force/energy/trajectory distribution parity, reproducibility across CPU/GPU/HIP/CUDA/OpenCL-style settings, restart determinism, and long-horizon stability. | Narrow 2-bead/local release is credible. Broad OpenMM-class equivalence is not. Estimate 50-60% for the restricted path, 30-40% for broad all-atom MD parity. |
| Schrödinger-class docking/ranking | Local ligand gates exist, but GPCR broad claim is blocked. `gpcr_core_rank_diagnostics_current.json` reports claim_safe false. `gpcr_guarded_100k_rank_failure_diagnostics_current.json` reports PR-AUC 0.5187, CI-low 0.1486, top-k 0.25, worst positive global rank 18923 and within-target rank 5315. The original DRD2 diagnostic had 2/14 atom coverage; the pseudo-allatom support packet now has 14/14 coverage, PDB-backed atom count, pose p90 0.139959 A, integrated OpenMM parameterization, and full-forcefield local-min survival 1.0. Decoy-intrusion closure is still missing. | Pose RMSD benchmarks, enrichment benchmarks, robust decoy separation, target-portable constraints, water/desolvation handling, MM-GBSA/FEP-style rescoring, and no target-specific overfit. | This is the largest accuracy blocker. Narrow ADRB2/selected-family evidence should not be widened. Estimate 30-40% broad parity, 60-65% only for bounded local lanes already green. |
| GALAXY-class structure/refinement | `runs/structure_refinement_scorecard_current.json` now exists. It finds native references and pseudo-allatom lanes for 3/3 targets, but RMSD, TM-score, GDT, lDDT/MolProbity, and DockQ/interface metric availability is 0/3. | Protein model refinement should be judged by RMSD, TM-score, GDT-TS/GDT-HA, lDDT/MolProbity where relevant, and DockQ/interface RMSD for complexes. | Current architecture has useful local pose/refinement plumbing but lacks GALAXY-grade structure validation. Estimate 20-30% parity until frozen structure metrics pass. |
| Syntekabio-like AI discovery/wetlab translation | `commercialization_readiness_current.json` has core commercial lane score 82.5 and all-category expansion 68.9, but ligand scale-up remains blocked: 0/3 suites commercialization-ready. T. cruzi PDE hard gate is green, but `wetlab_tcruzi_pde_translation_quality_packet_current.json` has `translation_quality_ready=false`, focus score 68.1, and blocker `binding_energy_proxy_too_weak_for_translation`. | Large-library screening, stable hit-to-lead prioritization, cross-target prospective evidence, integrated docking/MD refinement, assay/PoC continuity, and reproducible candidate packages. | Internal workflow discipline is strong, but prospective translation and scale are not yet comparable. Estimate 35-45% parity. |
| Claim governance and leakage control | Claim policies are unusually strict: scorecard-only promotion is blocked, fake pass is forbidden, and threshold relaxation is disallowed in multiple current packets. | Commercial workflows need reproducible frozen runs, auditability, non-leaky splits, and clear claim boundaries. | This is a relative strength. Estimate 65-75% maturity, but governance cannot compensate for missing physics/ranking/structure benchmarks. |

## Main Shortfalls By Priority

### P0 - Fair Accuracy Parity Harness

There is no single source of truth that compares the architecture against OpenMM/Schrödinger/GALAXY/Syntekabio-like expectations across the same frozen target panels. Without this, the system can say "local gate passed" but cannot make a defensible "commercial-tool-level accuracy" claim.

Required output:

- `runs/accuracy_parity_scorecard_current.json`
- `runs/accuracy_parity_scorecard_current.md`
- `runs/gpcr_a1_accuracy_repair_queue_current.json`
- `runs/gpcr_a1_accuracy_repair_queue_current.md`
- `runs/gpcr_drd2_atom_typed_backmapping_support_current.json`
- `runs/gpcr_drd2_atom_typed_backmapping_support_current.md`
- scorecard rows for `physics_dynamics`, `ligand_ranking`, `pose_geometry`, `structure_refinement`, and `wetlab_translation`
- all rows must include source artifact, frozen input, metric, threshold, pass/fail, and claim boundary

### P1 - GPCR Ligand Ranking And Pose Repair

The current GPCR evidence is still claim-blocked. The specific failure is no longer just score weighting. It is pose/backmapping and hard-decoy design:

- PR-AUC 0.5187 but CI-low 0.1486, below a defensible claim threshold.
- top-k hit rate 0.25 is unstable.
- DRD2 positive is buried at global rank 18923 and target rank 5315 in the active diagnostic.
- DRD2 positive atom coverage is now 14/14 in the pseudo-allatom support packet, and full-forcefield restrained-receptor local-minimization survival is measured at 1.0, so hard-decoy rebuild diagnostics can proceed.
- shadow scoring can improve DRD2, but it is claim-locked and still leaves decoys above positives.

Next work should reconstruct overanchor/multipolar/valid-anchor hard-decoy slices before any guarded 100k rerun.

### P2 - OpenMM-Class Physics/Dynamics Parity

The one-target OpenMM 2-bead T. cruzi PDE lane is good evidence for a narrow release. It is not enough for OpenMM-class broad claims.

Minimum parity suite:

- force vector agreement under identical topology and coordinates
- potential-energy distribution agreement
- energy drift and timestep stability
- RMSD/Rg/SASA/RMSF trajectory distribution agreement
- restart determinism
- CPU/GPU precision reproducibility where applicable
- several protein sizes and ligand/protein system classes, not one target

### P3 - GALAXY-Class Structure/Refinement Scorecard

Pseudo all-atom lanes are operationally useful, and the A3 scorecard now proves the missing metric surface explicitly. A structure/refinement accuracy claim still needs model-quality metrics:

- RMSD
- TM-score
- GDT-TS or GDT-HA
- lDDT or MolProbity-style structural quality
- DockQ/interface RMSD for complexes
- protein-ligand pose RMSD for binding-mode claims

No GALAXY-level or broad protein-refinement language should be used until this exists.

### P4 - Wetlab Translation Closure

The T. cruzi PDE packet shows a hard-gate pass, but the stricter translation-quality packet blocks promotion:

- `translation_quality_ready=false`
- focus score 68.1
- blocker: `binding_energy_proxy_too_weak_for_translation`
- missing axes: backmapping consistency, local minimization survival, pose preservation RMSD, replicate pass fraction

This means the correct claim is "operator-reviewable and locally promising," not "commercial wetlab translation proven."

## Defensible Current Claim Language

Acceptable:

- "Restricted local-delivery analysis pipeline with green gates on selected families."
- "OpenMM-referenced 2-bead T. cruzi PDE evidence exists for a narrow path."
- "GPCR broad promotion is intentionally blocked pending pose/backmapping and hard-decoy repair."

Not acceptable yet:

- "Schrödinger-level docking accuracy."
- "OpenMM-equivalent molecular dynamics engine."
- "GALAXY-level protein structure/refinement accuracy."
- "Broad AI drug-discovery platform comparable to Syntekabio."
- "Commercial-tool-level accuracy across targets."

## Bottom Line

The architecture is not fundamentally off-track. It has a stronger claim-control culture than many early systems, and its restricted local delivery evidence is real. But compared with established tools, the accuracy layer is still about half-built. The next commercial milestone should be accuracy parity under frozen, fair, externally interpretable benchmarks, not API expansion.

## Sources

Local sources:

- `BENCHMARKS.md`
- `docs/local_delivery_p0_gate.md`
- `docs/accuracy_parity_priority_plan_2026-05-06.md`
- `runs/accuracy_gate_local_delivery_preflight_current.json`
- `runs/openmm_2bead_strict_tcruzi_pde_current_accuracy_external.json`
- `runs/openmm_2bead_strict_tcruzi_pde_current_long_stability_validation.json`
- `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`
- `runs/gpcr_drd2_pose_generation_repair_packet_current.json`
- `runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json`
- `runs/gpcr_drd2_atom_typed_backmapping_support_current.json`
- `runs/gpcr_drd2_local_minimization_survival_current.json`
- `runs/gpcr_drd2_pseudo_allatom_repair_current.json`
- `runs/structure_refinement_scorecard_current.json`
- `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json`
- `runs/commercialization_readiness_current.json`
- `runs/accuracy_parity_scorecard_current.json`
- `runs/accuracy_parity_scorecard_current.md`

External sources:

- OpenMM user guide: https://docs.openmm.org/latest/userguide/application/02_running_sims.html
- OpenMM GitHub overview: https://github.com/openmm/openmm
- Schrödinger Glide: https://www.schrodinger.com/platform/products/glide/
- Schrödinger docking and scoring white paper: https://www.schrodinger.com/life-science/learn/white-papers/docking-and-scoring/
- Schrödinger FEP+: https://www.schrodinger.com/platform/products/fep/
- GalaxyWEB: https://galaxy.seoklab.org/
- GalaxyWEB NAR paper: https://academic.oup.com/nar/article/40/W1/W294/1078340
- Syntekabio DeepMatcher: https://www.syntekabio.com/syn/en/deepmatcher
- Syntekabio Auto-Hit Discovery service page: https://www.syntekabio.com/en/service/saas/dr
- Syntekabio SM-ARS: https://www.syntekabio.com/syn/en/sm-ars

# Commercial Tool Accuracy Gap Assessment - 2026-05-06

## Executive Verdict

API, hosting, and product wrapper concerns are intentionally out of scope for this pass. Judged only on scientific accuracy and defensible validation evidence, the current architecture is not yet at the level of established tools such as OpenMM, Schrödinger Glide/FEP+, GALAXY/GalaxyWEB, or Syntekabio-like AI discovery platforms.

Best current estimate:

| Claim scope | Current level vs established tools | Gap |
|---|---:|---:|
| Restricted local-delivery analysis service on already gated families | 75-80% | 20-25 pts |
| Accuracy-parity claim against commercial/standard tools overall | 40-50% | 50-60 pts |
| Broad commercial drug-discovery platform | 35-45% | 55-65 pts |

The strongest local evidence is in restricted release gating, reproducibility/claim governance, selected OpenMM 2-bead T. cruzi PDE evidence, and curated local wetlab packet flow. The main blockers are not API related. They are fair benchmark parity, GPCR ranking generalization, broad all-atom/OpenMM-class physics validation, GALAXY-class structure/refinement metrics, and prospective wetlab translation evidence.

Current A0 scorecard output now exists at `runs/accuracy_parity_scorecard_current.json` and `runs/accuracy_parity_scorecard_current.md`. It currently reports `blocked_accuracy_parity` with `0` pass rows, `1` restricted-pass row, `4` blocked rows, and `0` missing rows. As of 2026-05-14, the wetlab row also consumes `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json`, so the PDE rescue-only packet is fail-closed for commercial promotion: `commercial_hard_gate_pass=false`, v2 score `54.7`, decision `commercial_review_only`, risk `high`, and translation focus hard status `fail`. The A1 execution queue also exists at `runs/gpcr_a1_accuracy_repair_queue_current.json` and `runs/gpcr_a1_accuracy_repair_queue_current.md`; DRD2 full-forcefield local-min evidence is completed, and `guarded_100k_claim_review_rerun` now clears PR-AUC, PR-AUC CI-low, and top20 hit-rate for `gpcr_family_balanced`. The queue is `a1_accuracy_repair_queue_cleared_claim_locked`; `runs/gpcr_a1_independent_repeat_packet_current.md` is `independent_repeat_ready_claim_locked` and validate-only is green, so the next step is the independent repeat run, not promotion. The DRD2 support packet at `runs/gpcr_drd2_atom_typed_backmapping_support_current.md` now uses the pseudo-allatom repair lane and PDB-backed atom count: coverage is `1.0`, pose preservation is measured (`p90=0.13995901566518218 A`), integrated OpenMM protein-ligand parameterization is ready, and full-forcefield restrained-receptor local-min survival passes (`fraction=1.0`, ligand RMSD `1.9297168899124832 A` at a `2.0 A` threshold).

2026-05-13 update: the ligand scale-up suite is no longer the top local-delivery blocker. `runs/ligand_scaleup_suite_status_current.json` reports `commercialization_ready_suite_count=3/3` and `pending_suite_ids=[]`. The 1M blind package passes all tracked ligand sets, with core PR-AUC values `gpcr_core_full=0.8958`, `ion_trpv1_chembl20_full=0.9585`, and `kinase_core_full=1.0000`; expanded OOD PR-AUC values are `gpcr_chembl50_full=0.8093`, `ion_trpv1_chembl50_full=0.9867`, and `kinase_strict_full=1.0000`. The 1M benchmark status is `claim_safe_size_shift_speed_diagnostic`: accuracy is claim-safe for the restricted scale-up package, equal-size speedpack A/B owns the throughput claim, and 1M speed remains diagnostic scale evidence.

2026-05-13 `/goal` update: tracked commercialization accounting is closed in `commercialization_status_report.md`, but this does not change the accuracy-parity verdict. `post_goal_accuracy_parity_active=true` keeps the broad commercial-tool parity work open as a separate lane, with top blockers from OpenMM-class target coverage, claim-locked ligand ranking, and pose/structure refinement promotion locks.

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
| Schrödinger-class docking/ranking | Local ligand gates and the 1M restricted scale-up package are green. `gpcr_core_full` now passes at 1M with `PR-AUC=0.8958` using `binding_score_composite_v7_residual_active`, and `gpcr_chembl50_full` passes without the target-specific residual at `PR-AUC=0.8093`. Older broad GPCR-family 100k lanes still contain reject evidence, so this should be read as bounded scale-up evidence rather than a GPCR-family/router claim. | Pose RMSD benchmarks, enrichment benchmarks, robust decoy separation, target-portable constraints, water/desolvation handling, MM-GBSA/FEP-style rescoring, and no target-specific overfit. | The restricted scale-up claim is materially stronger. Broad Schrödinger-class parity is still not established because target-portable GPCR family generalization and pose/free-energy validation remain incomplete. Estimate 45-55% broad parity, 70-75% for bounded local lanes already green. |
| GALAXY-class structure/refinement | `runs/structure_refinement_scorecard_current.json` now exists. It finds native references and pseudo-allatom lanes for 3/3 targets; CA-aligned RMSD and CA proxy rows are materialized for 3/3, and interface/DockQ is resolved as not-applicable provenance for the current non-complex targets. True TM-score, true GDT, and true lDDT/MolProbity remain 0/3. T. cruzi PDE is now evidence-bearing but poor on the CA RMSD proxy (`34.972216322061456 A`). | Protein model refinement should be judged by RMSD, TM-score, GDT-TS/GDT-HA, lDDT/MolProbity where relevant, and DockQ/interface RMSD for complexes. | Current architecture has useful local pose/refinement plumbing and cleaner metric accounting, but still lacks GALAXY-grade true structure metrics. Estimate 20-30% parity until frozen true metrics pass. |
| Syntekabio-like AI discovery/wetlab translation | `commercialization_readiness_current.json` has core commercial lane score 82.5 and all-category expansion 68.9. Ligand scale-up is green for the tracked restricted suite: 3/3 commercialization-ready and no pending suites. T. cruzi PDE is now fail-closed in the all-atom commercial review packet: `commercial_hard_gate_pass=false`, score `54.7`, `commercial_review_only`, translation focus hard status `fail`, shortlist tier `defer`, and next expensive lane `defer_expensive_lane`. | Large-library screening, stable hit-to-lead prioritization, cross-target prospective evidence, integrated docking/MD refinement, assay/PoC continuity, and reproducible candidate packages. | Internal workflow discipline and scale evidence are stronger, but prospective translation and broader family coverage are still not comparable. Estimate 40-50% parity. |
| Claim governance and leakage control | Claim policies are unusually strict: scorecard-only promotion is blocked, fake pass is forbidden, and threshold relaxation is disallowed in multiple current packets. | Commercial workflows need reproducible frozen runs, auditability, non-leaky splits, and clear claim boundaries. | This is a relative strength. Estimate 65-75% maturity, but governance cannot compensate for missing physics/ranking/structure benchmarks. |

## Main Shortfalls By Priority

### P0 - Fair Accuracy Parity Harness

There is no single source of truth that compares the architecture against OpenMM/Schrödinger/GALAXY/Syntekabio-like expectations across the same frozen target panels. Without this, the system can say "local gate passed" but cannot make a defensible "commercial-tool-level accuracy" claim.

Required output:

- `runs/accuracy_parity_scorecard_current.json`
- `runs/accuracy_parity_scorecard_current.md`
- `runs/gpcr_a1_accuracy_repair_queue_current.json`
- `runs/gpcr_a1_accuracy_repair_queue_current.md`
- `runs/gpcr_a1_independent_repeat_packet_current.json`
- `runs/gpcr_a1_independent_repeat_packet_current.md`
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

Next work should run an independent guarded 100k repeat for the cleared A1 repair, then use the overanchor/multipolar/valid-anchor hard-decoy slices as the first diagnostic surface if CI-low stability regresses.

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

The T. cruzi PDE rescue-only packet is manually reviewable, but the stricter all-atom commercial review packet now fails closed:

- `translation_quality_ready=false`
- translation focus score 68.1
- translation focus source status `borderline`
- translation focus hard status `fail`
- `commercial_hard_gate_pass=false`
- commercial v2 score `54.7`
- decision `commercial_review_only`
- risk bucket `high`
- shortlist tier `defer`
- recommended next expensive lane `defer_expensive_lane`
- blocker: `binding_energy_proxy_too_weak_for_translation`
- candidate-pool blocker: `candidate_pool_geometry_stability_blocked`
- current/archived/internal plus ChEMBL homolog PDEB1 and BindingDB similarity seed translation evidence probe scanned `29568` candidate score rows across `64` score files; `translation_energy_pass_count=16`, but this is still only `7` unique ligands after the 3-bead geometry/stability rescore, GPU ADRESS rescue, contact-aware GPU rescue, and BindingDB similarity-seed screen, and `translation_core_pass_unique_ligand_count=0` at the fixed `binding_energy_proxy <= -0.55`, `mean_min_distance_A <= 3.10`, and `stability_score >= 0.32` hard thresholds
- the external homolog PDEB1 seed screen contributes `48` source rows with `external_homolog_seed_energy_pass_count=6` and `external_homolog_seed_core_pass_count=0`; the follow-up 3-bead geometry/stability rescore contributes `6` rows with `external_homolog_geomstab_rescore_energy_pass_count=6` and `external_homolog_geomstab_rescore_core_pass_count=0`; the GPU ADRESS rescue attempt contributes `6` rows with `external_homolog_adress_rescue_energy_pass_count=2` and `external_homolog_adress_rescue_core_pass_count=0`; the contact-aware GPU rescue attempt contributes `6` rows with `external_homolog_contact_rescue_energy_pass_count=1`, best `binding_energy_proxy=-0.6439975863474837`, and `external_homolog_contact_rescue_core_pass_count=0`; the BindingDB similarity-seed GPU screen contributes `9` rows with `external_bindingdb_similarity_energy_pass_count=1`, best `binding_energy_proxy=-0.5995226166267678`, and `external_bindingdb_similarity_core_pass_count=0`; these rows are candidate-pool expansion evidence only, not direct T. cruzi PDE claim evidence
- best observed `binding_energy_proxy=-0.8569508383875186` from `tcruzi_pde_external_pdeb1_010_chembl4453005`, but that row has `mean_min_distance_A=3.800457296768824` and `stability_score=0.000645616608055`, so geometry/stability still fail; best core-like geometry/stability row still only reaches `binding_energy_proxy=-0.19183465875164069`
- missing axes: backmapping consistency, local minimization survival, pose preservation RMSD, replicate pass fraction
- `runs/wetlab_tcruzi_pde_metric_scale_gap_packet_current.md` now classifies this as `blocked_metric_scale_split`: selected pseudo-allatom review rows preserve geometry/stability (`4/4`) but are energy-weak (`0/4`), while external homolog/BindingDB expansion provides `16` energy-pass rows with `0` geometry-stability/core passes
- `runs/wetlab_tcruzi_pde_pose_backmapping_closure_queue_current.md` converts the split into a claim-locked execution queue with `7` unique energy-hit PDE seeds and required pose-preservation RMSD, backmapping consistency, local-minimization survival, and replicate-pass measurements
- `runs/wetlab_tcruzi_pde_ligand_atomization_gap_packet_current.md` blocks that queue at the next commercial-hard layer: `atomization_ready_count=0/7` because the current pseudo-backmapped ligands have `2` ligand atoms while RDKit/SMILES heavy-atom counts are `34-43`
- `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.md` creates RDKit all-atom coordinate drafts for `7/7` queued seeds and orients `6/7` to the two-point pseudo anchors, but parameterization and protein-ligand local minimization remain `0/7`
- current required closure: BindingDB similarity seed expansion also failed to close the full core gate, so the next step is all-atom-style pose preservation/backmapping evidence or broader/new PDE chemistry rather than claim promotion

This means the correct claim is "operator-reviewable and locally promising," not "commercial wetlab translation proven."

## Defensible Current Claim Language

Acceptable:

- "Restricted local-delivery analysis pipeline with green gates on selected families."
- "OpenMM-referenced 2-bead T. cruzi PDE evidence exists for a narrow path, while the all-atom rescue-only packet remains commercial-review-only."
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
- `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json`
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

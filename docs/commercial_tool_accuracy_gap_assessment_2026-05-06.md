# Commercial Tool Accuracy Gap Assessment - 2026-05-06

## Executive Verdict

API, hosting, and product wrapper concerns are intentionally out of scope for this pass. Judged only on scientific accuracy and defensible validation evidence, the current architecture is not yet at the level of established tools such as OpenMM, Schrödinger Glide/FEP+, GALAXY/GalaxyWEB, or Syntekabio-like AI discovery platforms.

Best current estimate:

| Claim scope | Current level vs established tools | Gap |
|---|---:|---:|
| Restricted local-delivery analysis service on already gated families | 80-85% | 15-20 pts |
| Accuracy-parity claim against commercial/standard tools overall | 70-80% | 20-30 pts |
| Broad commercial drug-discovery platform | 55-65% | 35-45 pts |

The strongest local evidence is in reproducibility/claim governance, OpenMM 11-target 2-bead strict release evidence, deterministic chain-aware structure true metrics, GPCR A1 independent repeat ranking parity, and the T. cruzi PDE selected all-atom packet flow. The main remaining blockers are not API related. They are broad scorer/router deployment, broader external held-out coverage, pose/free-energy validation depth, full-atom quality/MolProbity caveats, prospective wetlab translation evidence, and unbounded platform wording.

Current A0 scorecard output exists at `runs/accuracy_parity_scorecard_current.json` and `runs/accuracy_parity_scorecard_current.md`. It currently reports `status=green` with `5` pass rows, `0` restricted-pass rows, `0` blocked rows, and `0` missing rows. As of the 2026-05-18 refresh, OpenMM 11-target strict release and structure deterministic true metrics are green, and the T. cruzi PDE selected all-atom burndown reports `hard_block_count=0`. The PDE atomized parameterization/local-min packet reports `row_count=7`, `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, and `validated_repair_count=7`. The GPCR A1 independent repeat passed the tracked ranking-parity gate: PR-AUC `0.8718530390764964`, PR CI-low `0.7611678630724843`, top20 `1.0`, blockers `[]`. Local delivery is also green for the restricted scope: `runs/local_delivery_verdict_gate_current.json` reports `delivery_ready=true`, `verdict=delivery_ready`, and `p0_blocker_count=0`.

2026-05-13 update: the ligand scale-up suite is no longer the top local-delivery blocker. `runs/ligand_scaleup_suite_status_current.json` reports `commercialization_ready_suite_count=3/3` and `pending_suite_ids=[]`. The 1M blind package passes all tracked ligand sets, with core PR-AUC values `gpcr_core_full=0.8958`, `ion_trpv1_chembl20_full=0.9585`, and `kinase_core_full=1.0000`; expanded OOD PR-AUC values are `gpcr_chembl50_full=0.8093`, `ion_trpv1_chembl50_full=0.9867`, and `kinase_strict_full=1.0000`. The 1M benchmark status is `claim_safe_size_shift_speed_diagnostic`: accuracy is claim-safe for the restricted scale-up package, equal-size speedpack A/B owns the throughput claim, and 1M speed remains diagnostic scale evidence.

2026-05-18 update: tracked commercialization accounting and tracked accuracy-parity accounting are both green for the restricted local scope. This does not create an unbounded commercial-platform claim: scorer/router deployment, broader external held-out panels, direct transporter binding evidence, full-atom quality/MolProbity, and prospective wetlab validation stay as separate expansion work.

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
| OpenMM-class physics/dynamics | `runs/openmm_2bead_strict_multitarget_current_summary.json` passes 11/11 targets with no failed gates, and the accuracy scorecard now uses the multi-target current artifact by default. The current OpenMM local platform discovery still exposes Reference/CPU only, while trajectory stress validation uses the ROCm/Rust-HIP path. | Broad topology/force-field coverage, all-atom and solvent-ready dynamics, force/energy/trajectory distribution parity, reproducibility across CPU/GPU/HIP/CUDA/OpenCL-style settings, restart determinism, and long-horizon stability. | The 2-bead multi-target lane is credible and now OpenMM-class for the scoped release evidence, but broad all-atom/solvent parity is not established. Estimate 60-70% for the restricted path, 35-45% for broad all-atom MD parity. |
| Schrödinger-class docking/ranking | Local ligand gates, the 1M restricted scale-up package, and the latest GPCR A1 independent repeat are green for the tracked ranking-parity lane: `PR-AUC=0.8718530390764964`, `PR-AUC CI low=0.7611678630724843`, and `top20=1.0`. Older broad GPCR-family 100k lanes remain reject/comparison evidence, so this is tracked ranking-parity evidence, not a GPCR-family/router deployment claim. | Pose RMSD benchmarks, enrichment benchmarks, robust decoy separation, target-portable constraints, water/desolvation handling, MM-GBSA/FEP-style rescoring, and no target-specific overfit. | Tracked ligand-ranking parity is green, while broad Schrödinger/FEP-style parity still needs pose/free-energy, water/desolvation, and wider family validation. Estimate 70-80% for tracked parity, lower for broad FEP-grade deployment. |
| GALAXY-class structure/refinement | `runs/structure_refinement_scorecard_current.json` now passes with `metric_backend=internal_deterministic_ca_true_metrics`, chain-aware canonical CA matching, true TM-score/GDT-TS/lDDT-CA rows for 3/3 native-backed targets, and DockQ/interface resolved as not-applicable for current non-complex targets. MolProbity/full-atom quality caveat remains explicit. | Protein model refinement should be judged by RMSD, TM-score, GDT-TS/GDT-HA, lDDT/MolProbity where relevant, and DockQ/interface RMSD for complexes. | Structure metric accounting is much stronger and claimable for the scoped deterministic CA true-metric backend, but full-atom quality and complex/interface coverage remain caveats. Estimate 55-65% for the scoped structure lane, lower for broad GALAXY-grade refinement. |
| Syntekabio-like AI discovery/wetlab translation | `commercialization_readiness_current.json` has tracked readiness accounting closed for the restricted local scope. Ligand scale-up is green for the tracked restricted suite: 3/3 commercialization-ready and no pending suites. T. cruzi PDE selected all-atom hard blocks are closed with parameterization/local-min `7/7`, but prospective wetlab hit validation and broad translation evidence are still not present. | Large-library screening, stable hit-to-lead prioritization, cross-target prospective evidence, integrated docking/MD refinement, assay/PoC continuity, and reproducible candidate packages. | Internal workflow discipline, scale evidence, and PDE packet quality are stronger, but prospective translation and broader family coverage are still not comparable. Estimate 55-65% parity. |
| Claim governance and leakage control | Claim policies are unusually strict: scorecard-only promotion is blocked, fake pass is forbidden, and threshold relaxation is disallowed in multiple current packets. | Commercial workflows need reproducible frozen runs, auditability, non-leaky splits, and clear claim boundaries. | This is a relative strength. Estimate 65-75% maturity, but governance cannot compensate for missing physics/ranking/structure benchmarks. |

## Main Shortfalls By Priority

### P0 - Fair Accuracy Parity Harness

The fair comparison harness now exists and is green for the tracked axes. It is the single source of truth for the current restricted commercial-tool accuracy-parity wording. Keep it green before any outbound claim, and expand external held-out panels before broad platform language.

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
- current scorecard state: `status=green`, `pass_row_count=5`, `blocked_row_count=0`

### P1 - GPCR Ligand Ranking And Pose Repair

The current tracked GPCR A1 ranking evidence is green, but broader GPCR-family/router deployment remains separate. The legacy failure surfaces are still useful diagnostics because they explain why not every GPCR-family lane should be promoted:

- current A1 repeat: PR-AUC `0.8718530390764964`, PR CI-low `0.7611678630724843`, top20 `1.0`, blockers `[]`.
- older broad GPCR-family lanes still include PR-AUC/CI-low/top20 reject evidence and remain comparison-only.
- DRD2 legacy diagnostic still shows positive rank pathologies and overanchored decoys in the older frozen family surface.
- DRD2 positive atom coverage is now 14/14 in the pseudo-allatom support packet, and full-forcefield restrained-receptor local-minimization survival is measured at 1.0, so hard-decoy rebuild diagnostics can proceed.
- shadow scoring can improve DRD2, but broad router/platform promotion remains locked until deployment guardrails and broader external validation clear.

Next work should keep the independent repeat green, add broader external held-out coverage, and use the overanchor/multipolar/valid-anchor hard-decoy slices as the first diagnostic surface if CI-low stability regresses.

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

Scoped structure/refinement wording can reference the deterministic internal CA true-metric backend, but broad GALAXY-level or full-atom refinement language should wait for MolProbity/full-atom quality and broader complex/interface coverage.

### P4 - Wetlab Translation Closure

The T. cruzi PDE rescue-only packet is now stronger at the selected all-atom evidence layer, but this is still not prospective wetlab proof:

- `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json` reports `row_count=7`, `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, `validated_repair_count=7`, and `hard_block_count=0`
- `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json` reports `translation_gate_focus_status=pass`, `focus_shortlist_tier=tier2_silver`, and `recommended_next_expensive_lane=atomized_openmm_local_min_validated_repair`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` reports `commercial_hard_gate_pass_v2=true`, `hard_block_count=0`, and `selected_allatom=pass`
- the historical translation evidence probe remains useful source context: it scanned `29568` candidate score rows, found `16` energy-pass rows and `7` unique energy-hit ligands, but the original pre-atomized core-pass count was `0`
- the fixed hard thresholds remain `binding_energy_proxy <= -0.55`, `mean_min_distance_A <= 3.10`, and `stability_score >= 0.32`
- current required closure: prospective wetlab/assay confirmation, broader/new PDE chemistry, and full scorecard parity are still required before any wetlab-proven or broad translation claim

This means the correct claim is "selected all-atom hard blockers closed with local atomized parameterization/minimization evidence," not "commercial wetlab translation proven."

## Defensible Current Claim Language

Acceptable:

- "Restricted local-delivery analysis pipeline with some green evidence surfaces, but the current delivery verdict is blocked."
- "OpenMM 11-target 2-bead strict-release evidence exists for the scoped path."
- "T. cruzi PDE selected all-atom hard blockers are closed with 7/7 atomized parameterization/local-min evidence."
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
- `runs/openmm_2bead_strict_multitarget_current_summary.json`
- `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`
- `runs/gpcr_drd2_pose_generation_repair_packet_current.json`
- `runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json`
- `runs/gpcr_drd2_atom_typed_backmapping_support_current.json`
- `runs/gpcr_drd2_local_minimization_survival_current.json`
- `runs/gpcr_drd2_pseudo_allatom_repair_current.json`
- `runs/structure_refinement_scorecard_current.json`
- `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json`
- `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
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

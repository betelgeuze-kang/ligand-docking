# Accuracy Parity Priority Plan - 2026-05-06

## Goal

The next commercialization milestone is not API exposure. It is evidence that the architecture can reach commercial-tool-class accuracy under fair, frozen, reproducible benchmarks.

Comparable tool classes should be treated as benchmark roles, not marketing labels:

- OpenMM role: physics/dynamics reference behavior.
- Schrödinger role: ligand docking/ranking, pose geometry, enrichment, and calibration.
- GALAXY role: protein structure/refinement and complex/interface quality.
- AI-discovery platform role: end-to-end hit-prioritization stability, leakage control, and wetlab translation.

## Priority Order

### A0 - Build The Fair Comparison Harness

Why first:

- Without a frozen parity harness, any "commercial-tool-level" claim is ungrounded.
- Current local accuracy evidence is useful but too narrow: neighbor parity and restricted local-delivery pass do not establish broad accuracy parity.

Required output:

- `runs/accuracy_parity_scorecard_current.json`
- `runs/accuracy_parity_scorecard_current.md`
- rows split by `physics_dynamics`, `ligand_ranking`, `pose_geometry`, `structure_refinement`, `wetlab_translation`
- frozen input hashes, row identity hashes, baseline artifact hashes, and leakage audit status

Pass rule:

- every scorecard row must say whether it is `pass`, `fail`, `comparison_only`, or `not_available`
- unavailable external-tool results must not be inferred from local results

Current state:

- `runs/accuracy_parity_scorecard_current.md` is generated and still `blocked_accuracy_parity`.
- Row mix is now `0 pass / 1 restricted_pass / 4 blocked / 0 missing`; A3 is no longer absent, it is explicitly blocked on missing structure/refinement metrics.

### A1 - Fix Ligand Ranking Robustness

Why second:

- This is the strongest current mismatch against commercial docking/discovery stacks.
- GPCR scale-up remains blocked by CI-low/top20 stability, even though coverage, leakage, scoreability, and family-held-out checks are green.

Current blocker:

- `gpcr_core_family_balanced_rescore_v1`: `PR-AUC=0.5186945103743427`, `top20=0.25`, but `CI-low=0.1485815545422209 < 0.45`
- DRD2 remains buried at `global_rank=18923` / `target_rank=5315`
- v16/adaptive improves shadow ranks but remains blocked by OPRM1/HTR2A support and target-internal decoy separation
- DRD2 pseudo-allatom support now has `positive_backmapping_atom_coverage_ratio=1.0`, PDB-backed atom count, pose p90 `0.13995901566518218 A`, integrated OpenMM protein-ligand parameterization, and full-forcefield restrained-receptor local-min survival (`fraction=1.0`, ligand RMSD `1.9297168899124832 A` at a `2.0 A` threshold).
- The previous claim-grade full-forcefield local-minimization blocker is closed for the DRD2 positive: `runs/gpcr_drd2_full_forcefield_minimization_readiness_current.md` is `ready` and `runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.md` has `claim_grade_parameterization_ready=true`.
- `runs/gpcr_drd2_protein_amber14_parameterization_repair_current.md` keeps the raw 6cm4 blocker visible (`70` missing-heavy-atom residues, including `2` incomplete histidines) but the conservative ChimeraX same-residue side-chain rebuild plus chain-fragment/OXT repair produces an Amber14-ready receptor artifact with active missing-heavy count `0`.
- DRD2 selected-slice hard-decoy diagnostics are pairwise-green after cache schema repair, and hard-decoy rebuild is now allowed as the next diagnostic step; claim/scorer/guarded-100k promotion remains locked.

Next work:

- DRD2 overanchor/multipolar/valid-anchor hard-decoy slice rebuild now that local-min survival passes
- OPRM1 target-portable pose/anchor evidence
- HTR2A decoy-support discrimination
- conditional prior gating that does not use target identity
- full guarded review only after the shadow replay clears the frozen scorecard

Pass rule:

- `ranking_pr_auc_ci_low >= 0.45`
- `top20_hit_rate >= 0.20`
- no threshold relaxation, no target identity feature, no fake pass
- DRD2/HTR2A/OPRM1 positives must survive target-internal decoys, not only global aggregate scoring

### A2 - Establish OpenMM-Class Physics/Dynamics Parity

Why third:

- A molecular-dynamics architecture needs trusted physics behavior before broad claims.
- The current delivery gate is green, but it is restricted-scope evidence, not OpenMM-class equivalence.

Required metrics:

- force vector agreement
- energy drift and energy distribution agreement
- RMSD/Rg/SASA/RMSF distribution agreement
- timestep stability
- restart determinism
- neighbor-list and nonbonded parity under identical topology/forcefield assumptions

Current caution:

- all-atom/AdResS pathways still contain placeholder or random-neighbor logic and must stay out of production accuracy claims.

Pass rule:

- compare against OpenMM-compatible references on frozen targets
- preserve topology and forcefield identity
- report failures as physics failures, not as speed or implementation noise

### A3 - Add GALAXY-Class Structure/Refinement Scorecards

Why fourth:

- Protein modeling/refinement accuracy cannot be inferred from ligand-ranking metrics.

Required metrics:

- RMSD
- TM-score
- GDT-TS
- lDDT
- interface RMSD and DockQ for complexes
- per-family/target held-out split

Current caution:

- IDP wider promotion remains bounded and not broad structure-refinement proof.
- `runs/structure_refinement_scorecard_current.md` now exists, with native references and pseudo-allatom lanes for `3/3` targets but all required structure/refinement metric counts still `0/3`.
- `runs/structure_refinement_metric_queue_current.md` now opens `6` metric materialization rows: protein-alignment metrics and interface/DockQ provenance for each of `T. cruzi PDE`, `SARS-CoV-2 Mpro`, and `Cathepsin K`.
- `runs/structure_refinement_metric_materialization_current.md` computes partial CA-aligned RMSD/GDT/TM/lDDT proxy rows for SARS-CoV-2 Mpro and Cathepsin K (`16` candidate rows total), raising RMSD and CA-proxy materialization to `2/3` targets while keeping true TM-score/GDT/lDDT/DockQ at `0/3`.
- SARS-CoV-2 Mpro and Cathepsin K each have `8` backmapped candidate PDBs ready for frozen metric computation; T. cruzi PDE must first expose an `allatom_scores_csv` or equivalent candidate source.

Pass rule:

- a frozen protein/refinement scorecard must pass before using GALAXY-level or broad protein-modeling language.

### A4 - Tie Accuracy To Wetlab Translation

Why fifth:

- Wetlab value is the final commercial relevance layer, but it should confirm rather than mask ranking/physics gaps.

Current blockers:

- PDE translation quality is borderline with `binding_energy_proxy_too_weak_for_translation`
- transporter AQP1/GLUT1 negative evidence is still review-only/evidence-blocked
- CA2/PXR still need quantitative provenance and `replacement_reference_binding_kcal_mol` closure

Pass rule:

- keep the order `binding_energy_proxy -> pose RMSD -> backmapping -> local minimization survival`
- no delivery-ready expansion wording until direct target-specific evidence closes

## Deferred

API, hosted product, monitoring, deployment, and packaging remain important but are downstream of accuracy parity for this phase.

Do not let API readiness displace the current scientific work order:

1. fair parity harness
2. GPCR ligand-ranking robustness
3. OpenMM-class physics parity
4. GALAXY-class structure/refinement scorecard
5. wetlab translation closure

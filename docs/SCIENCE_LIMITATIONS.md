# Science Limitations And Claim Boundaries

Status: P1 product-safety and reviewer-readiness document  
Scope: ligand HTVS / backmapping / local delivery surfaces in this repository

## Purpose

This document gives reviewers, operators, and customer-facing integrators one
short place to understand what the current ligand docking stack can and cannot
claim. It is intentionally conservative. It does not replace generated evidence
bundles or benchmark packets; it defines the language and checks that prevent
proxy outputs from being over-promoted.

## Current Science Boundary

The current product path is a restricted ligand HTVS and backmapping scoring
surface. It is not a broad, general-purpose docking platform. It is not a wetlab
hit-validation engine. It does not claim Schrödinger, Vina, GNINA, FEP, or
experimental binding free-energy parity.

The current default path contains these limitations:

| Area | Current limitation | Required claim-safe handling |
| --- | --- | --- |
| Ligand geometry | CSV/SMILES inputs may be converted to simplified bead geometry; strict production runs must reject fallback beads. | Use `--production-strict-inputs`; inspect `ligand_geometry_source` and `fallback_beads_used`. |
| Protein dynamics | The fast trajectory path is protein-static / ligand-motion oriented unless a specific all-atom lane proves otherwise. | Reports must state `dynamics_scope` or the runner profile used. |
| Binding energy | Internal score columns ending in `_proxy` are heuristic or surrogate scores. | Customer-facing reports must expose `proxy_binding_energy_score`, not experimental ΔG or true MM/PBSA language. |
| Pocket source | Geometric or centroid pocket fallbacks are review aids, not production-grade binding-site evidence. | Production profiles require explicit pocket provenance. |
| Pose quality | Ranking metrics alone do not prove pose correctness. | Use pose-level reports with RMSD, clash, strain, H-bond geometry, and contact recovery fields. |
| Broad family scope | Restricted families are narrower than a general ligand-docking platform. | Scope expansion requires separate evidence receipts and claim gates. |

## Current Positive Claims

The repository may claim:

- A restricted local delivery framework for configured ligand HTVS/backmapping scoring lanes.
- Fail-closed intake, provenance, and claim-guard behavior.
- Proxy ranking and pose-review evidence when the relevant generated artifacts are present and validated.
- Operator-reviewable bundles and summary reports that separate computational readiness from experimental proof.

## Claims That Stay Blocked

The repository must not claim:

- Broad commercial docking parity.
- Experimental hit validation.
- Absolute binding free energy prediction.
- True MM/PBSA, FEP, or all-atom refinement unless a lane explicitly runs and validates those calculations.
- Unattended production execution beyond the configured restricted runner profile.
- Broad GPCR/transporter/PXR/IDP/general-platform promotion without the corresponding evidence receipts.

## P1 Reviewer Checklist

A reviewer should ask for these artifacts before reading a run as product-ready:

1. Queue provenance columns: `ligand_geometry_source`, `fallback_beads_used`, `pocket_source`, `native_structure_source`, `science_input_risk_level`.
2. API readiness block: `readiness.intake_valid`, `readiness.execution_authorized`, `readiness.science_inputs_strict`, `readiness.runner_profile_ready`, `readiness.blocking_reasons`.
3. Score contract: `claim.score_contract.customer_score_name=proxy_binding_energy_score` and `method_kind=heuristic_proxy`.
4. Pose-level report: `pose_rmsd_A`, `clash_count`, `ligand_strain_kcal_mol`, `hbond_geometry_score`, and `contact_recovery` present for any pose-quality claim.
5. CI evidence: clean unit/API/science smoke checks separate from self-hosted GPU/nightly checks.

## Safe Language

Use these phrases:

- "proxy docking score"
- "pose-level review metric"
- "restricted runner profile"
- "computational readiness evidence"
- "operator-gated local delivery"

Avoid these phrases unless separately proven by evidence receipts:

- "validated binder"
- "wetlab hit"
- "experimental ΔG"
- "true MM/PBSA result"
- "general docking platform"
- "commercial parity"

## How To Close A Science Claim

A science claim closes only when the relevant lane has:

1. strict input provenance,
2. reproducible command and environment record,
3. row-level metric evidence,
4. threshold policy,
5. generated report artifact,
6. claim boundary text,
7. CI or operator receipt linking the run to a git SHA.

Until all seven are present, the result remains review evidence, not a promoted
product claim.

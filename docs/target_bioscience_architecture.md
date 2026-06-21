# Target Bioscience Architecture

Status: target architecture for BioDiscovery commercial platform transition
North Star: integrated protein structure analysis/prediction, ligand docking, molecular dynamics, and free-energy workflows with honest evidence gates.

## Canonical Contracts

Create one versioned domain contract package and keep legacy `core/**` as compatibility adapters:

| Contract | Purpose |
|---|---|
| `Sequence` | Source, alphabet, modifications, chain boundaries, provenance. |
| `Polymer` | Protein/nucleic-acid/polymer entity with residues, atoms/beads, and mapping. |
| `Ligand` | SMILES/SDF/input source, protonation, tautomer/stereo enumeration, charge state, provenance. |
| `Complex` | Bound multi-entity system with chains, cofactors, metals, waters, ions, and interface metadata. |
| `Topology` | Exact atom, bond, charge, parameter, constraint, residue, and force-field source accounting. |
| `PoseEnsemble` | Pose candidates, clustering, score components, validity, uncertainty, abstention. |
| `SimulationSpec` | Integrator, timestep, ensemble, thermostat/barostat, PBC, electrostatics, seed, checkpoint policy. |
| `Trajectory` | Frames, energies, observables, provenance, compression, hash, analysis-ready indexes. |
| `PredictionConfidence` | pLDDT/PAE/PDE/ranking/confidence calibration, OOD abstention, model-card link. |
| `EvidenceBundle` | Signed row-level receipts, thresholds, artifact hashes, claim boundary, replay command. |

## Science Workflows

| Workflow | Target |
|---|---|
| structure prep/quality | PDB/mmCIF/SDF intake, residue/atom repair, clash/Ramachandran/geometry checks, provenance. |
| sequence-to-structure | optional MSA/template, tokenized protein/ligand/nucleic-acid/ion inputs, SE(3)/E(3) trunk, atom diffusion, recycling, multimer/interface learning, calibrated confidence. |
| pocket/pose | blind and pocket-guided search, flexible side chains, water/metal/cofactor/covalent policy, pose diffusion/search, clustering. |
| scoring/ranking | physics plus ML consensus, uncertainty, abstention, no customer-facing mutation unless guarded. |
| all-atom refine | exact topology, parameterization, constraints, local minimization, force and geometry diagnostics. |
| MD | bounded neighbor lists, PBC, PME-grade electrostatics, NVE/NVT/NPT, deterministic seed, checkpoint/restart. |
| free energy | ensemble MM/GBSA first; lambda windows/replica/BAR/MBAR only after overlap/convergence diagnostics. |
| analysis | interaction, trajectory, interface, confidence, and report UX with row-level evidence links. |

## Execution Architecture

| Layer | Target |
|---|---|
| API/SDK/CLI | Versioned public contracts, idempotent job creation, scoped execution tokens, typed errors. |
| workflow DAG | Prepare -> pocket -> pose ensemble -> score -> refine -> analyze -> signed report. |
| data plane | PostgreSQL metadata, object storage artifacts, model/data registry, signed manifests. |
| compute plane | durable queue, GPU scheduler, bounded resource quotas, retry/restart, deterministic seeds. |
| security | OIDC/RBAC, tenant isolation, audit logs, payload privacy, secrets never in artifacts. |
| observability | metrics, traces, queue health, GPU utilization, provenance and replay hashes. |
| release | clean-container GPU E2E, rollback, thresholded capability matrix, fail-closed gates. |

## Migration Rules

1. Move canonical implementation into product/engine packages; keep `core/**` as adapters.
2. Replace subprocess/CSV runner seams with typed services and DAG nodes.
3. Require row-level `EvidenceBundle` receipts before any scientific claim promotion.
4. Keep CASP17 active lane on internal torch/coarse-grain physics only.
5. Treat AI as residual/reranker until leakage-free splits, calibration, abstention, model cards, and rollback are proven.

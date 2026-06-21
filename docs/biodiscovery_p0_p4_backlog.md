# BioDiscovery P0-P4 Backlog

Status: current backlog summary
Source of truth: `config/product_capability_matrix.yaml`

| Priority | Work item | Owner | Risk | Key dependencies | Definition of done |
|---|---|---|---|---|---|
| P0 | Canonical contracts | product_architecture | R3 | typed inventory, topology provenance | Sequence/Polymer/Ligand/Complex/Topology/PoseEnsemble/SimulationSpec/Trajectory/PredictionConfidence/EvidenceBundle exist and legacy adapters isolate `core/**`. |
| P0 | Exact topology/provenance | physics_engine | R3 | contracts, topology validity rows | Placeholder/proxy topology stays fail-closed; atom/bond/charge/parameter/source accounting reaches signed bundles. |
| P0 | NxN guard | engine_runtime | R3 | neighbor bounds, runtime scaling receipts | Product-scale dense fallback blocked unless explicit bounded diagnostic mode is active. |
| P0 | CI truthfulness | product_quality | R2 | capability matrix, ai-verify | Matrix validator blocks high-risk overclaims and runs in product verification. |
| P1 | Docking vertical slice | docking_product | R3 | contracts, topology, pose ensemble, signed report | Local fixture PDB+SMILES -> prepare -> pocket/pose ensemble -> score/refine -> signed report. |
| P1 | Structure baseline honesty | structure_ml | R4 | blind split protocol, confidence calibration | Heuristic/internal baseline remains baseline-only; no parity language without blind evidence. |
| P2 | Production all-atom MD | md_engine | R4 | exact topology, PME/PBC, constraints, reference checks | NVE/NVT/NPT, checkpoint/restart, deterministic seed, trajectory analysis, force/reference/scaling checks pass. |
| P2 | Delta G/free energy | free_energy | R4 | all-atom MD, lambda windows, MBAR/BAR diagnostics | MM/GBSA and lambda-window evidence meets holdout, convergence, overlap, and uncertainty thresholds. |
| P3 | Foundation structure model | structure_ml | R4 | leakage-free splits, atom diffusion trunk, model card | Tokenization, pair/trunk/diffusion/recycling/multimer/confidence stack is independently validated with rollback. |
| P3 | AlphaFold parity claim | executive_claims | R4 | foundation model, independent validation | Parity language remains blocked until independent blind validation supports it. |
| P4 | Enterprise UX/governance | platform_product | R3 | OIDC/RBAC, tenant isolation, metrics/tracing | Versioned API/SDK/CLI, durable queue, GPU scheduler, object storage, registry, workflow DAG, retry/idempotency, and tenant tests pass. |
| P4 | Broad platform and wetlab claims | executive_claims, translational_validation | R4 | public holdouts, prospective evidence, legal review | Broad platform and wetlab-hit language remain blocked until row-level external evidence is accepted by the human owner. |

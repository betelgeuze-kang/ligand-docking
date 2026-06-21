# Product PM Architecture Current

Status: restricted Tier-alpha pilot
Audience: product, science, platform, and verification owners
Claim boundary: local molecular-structure analysis and ligand-docking readiness only; no AlphaFold parity, broad platform, calibrated Delta G/FEP, or wetlab-hit claim before independent validation.

## Current Position

The repository is best described as a restricted Tier-alpha pilot with strong local evidence accounting and partially implemented science surfaces. It has meaningful product-readiness machinery, but the scientific engine is not yet a general structure-prediction, docking, MD, or free-energy platform.

Life-science lanes considered for this local audit:

| Lane | Used for this goal | External data used |
|---|---|---|
| protein structure and mechanism | contract, topology, confidence, CASP boundary review | no |
| chemistry, ligands, and pharmacology | docking/pose/free-energy claim separation | no |
| MD and free energy | all-atom, ensemble, FEP blocker definition | no |
| clinical/translational/wetlab | wetlab-hit claim boundary only | no |

## Green Versus Valid

| Area | Accounting/product green candidate | Scientific-validity status |
|---|---|---|
| fail-closed evidence | Strong: many contracts emit blockers, fingerprints, and mutation flags. | Necessary but not sufficient for scientific claims. |
| validated runner/profile surface | Present in API/product runner and scripts. | Needs typed service/DAG decomposition and clean-container E2E receipts. |
| signed/traceable manifests | Present across product and delivery tooling. | Must be tied to row-level benchmark evidence, not summary-only reports. |
| ROCm/HIP/Rust | Real code exists in `rust_engine`. | Needs parity/scaling proofs before performance or numerical claims. |
| compact neighbor/physics | Present in engine/core lanes. | Must block dense all-pairs fallback and prove bounded scaling. |
| structure prediction | CASP/internal heuristic baseline only. | Not AlphaFold-like; parity language blocked. |
| docking | Restricted proxy/HTVS/refine scaffolds exist. | Needs PoseBusters/CASF/PDBbind-style holdout metrics and chemistry validity. |
| MD | Proxy/united or coarse-grain surfaces remain. | Needs exact topology, constraints, PBC, PME-grade electrostatics, ensembles, and reference checks. |
| Delta G/FEP | Scaffold/proxy language appears in plans. | Calibrated affinity/FEP claim blocked until convergence/overlap/holdout evidence. |
| enterprise product | API/deploy/runbook surfaces exist. | Needs PostgreSQL, durable queue, GPU scheduler, object storage, OIDC/RBAC, tenant isolation, retry/idempotency validation. |

## Current Architecture

| Layer | Current role | Main issue |
|---|---|---|
| `api/` | FastAPI product, CAMEO, CASP, cleanup, job endpoints. | `api/product.py` is too large and mixes endpoint, orchestration, and packet-building concerns. |
| `betelgeuze_product/` | Product contracts, capability/readiness, public benchmark, service boundary, operations. | Good fail-closed surface; needs canonical DAG/service boundary. |
| `betelgeuze_ai_md/contracts/` | Existing typed contract adapters. | Needs expansion into canonical BioDiscovery domain contracts. |
| `betelgeuze_engine/` | Emerging canonical engine for topology, physics terms, runners, residuals, validation. | Needs exact topology/provenance and numerical validation depth. |
| `core/` | Legacy physics/model modules. | Should become compatibility adapters while canonical code moves under product/engine packages. |
| `tools/` | Operational packet/report/gate generators. | Too broad and repetitive; consolidate into registries and typed builders. |
| `deploy/` | Product stack, K8s, rollout helpers. | Not yet enterprise-hosted platform proof. |

## Near-Term Product Judgment

The commercial posture should remain:

- allowed: restricted local pilot, operator-reviewed evidence bundles, scoped structure analysis/docking readiness, claim-boundary reports
- blocked: broad platform, AlphaFold parity, calibrated Delta G/FEP, wetlab hit, unattended external mutation, CASP external submission without human approval
- first P0 slice complete in this turn: local capability matrix and verifier enforcing those blocked claims

## P0-P4 Backlog Source

The dependency/DoD/risk/owner backlog is tracked in `config/product_capability_matrix.yaml` and summarized in `docs/biodiscovery_p0_p4_backlog.md`. The matrix is now checked by `scripts/verify_product_capability_matrix.py` and `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`.

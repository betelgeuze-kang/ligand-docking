# Tier Beta Vertical Slice Gap Audit

Status: current gap audit after restricted local vertical slice

## Closed In This Slice

- `dense_guard.py` was adopted as canonical package code and connected to Tier-beta product diagnostics.
- A typed Python service now executes a local PDB+SMILES vertical slice without subprocess or CSV stage handoff.
- Limited mmCIF `_atom_site` loop protein input now executes through the same typed service path and signed manifest flow.
- RDKit-backed SDF/MolBlock ligand intake now preserves exact atom elements, bonds, formal charges, chirality status, and source provenance in pose rows and signed manifests.
- API direct worker execution exists for `tier_beta_biodiscovery_direct`.
- A decomposed Tier-beta product router exists alongside the legacy `api/product.py` monolith.
- Legacy product docking and structure-analysis endpoints were extracted to `api/product_docking.py` while `api.product` keeps compatibility exports for older direct imports.
- Product capability surface endpoint was extracted to `api/product_capabilities.py` while `api.product.get_product_capabilities` remains as a compatibility import.
- Product architecture and architecture-validation endpoints were extracted to `api/product_architecture.py` while `api.product` keeps compatibility imports.
- Product service-boundary and API-contract endpoints were extracted to `api/product_service_contracts.py` while `api.product` keeps compatibility imports.
- Product operational-quality and security-deployment-contract endpoints were extracted to `api/product_operational.py` while `api.product` keeps compatibility imports.
- Product operations, commercial-independence, release-readiness, and job-orchestration-contract endpoints were extracted to `api/product_release_ops.py` while `api.product` keeps compatibility imports.
- Product license-decision, license-file-work-order, self-hosted-license-distribution-audit, and license-options endpoints were extracted to `api/product_license.py` while `api.product` keeps compatibility imports.
- Product external-metrics, public-benchmark, trajectory-SLA-contract, and rollout-execution-smoke-receipt endpoints were extracted to `api/product_benchmark.py` while `api.product` keeps compatibility imports.
- Product AI decision-graph, pose-sampling-readiness, AI-report-UX, and residual-model-registry endpoints were extracted to `api/product_ai_surface.py` while `api.product` keeps compatibility imports.
- Product CAMEO live-validation, official-result-fetch-preflight, and API-runner-profile-promotion operator receipt/staging-apply endpoints were extracted to `api/product_cameo_runner.py` while `api.product` keeps compatibility imports.
- Product production-AI checkpoint-readiness, GPU-worker dispatch/return, promotion-workbench, and registry-promotion operator receipt/priority endpoints were extracted to `api/product_production_ai.py` while `api.product` keeps compatibility imports.
- Product scope-breadth, scope-claim-guard, scope-evidence-priority, scope-evidence-intake-readiness, transporter-manual-review-intake, pxr-exact-review-intake, aqp1-operator-validation-candidate, and aqp1-direct-binding-procurement-packet endpoints were extracted to `api/product_scope.py` while `api.product` keeps compatibility imports.
- Product commercial-readiness operator-packet, operator-packet-freshness, execution-ladder, and handoff-bundle endpoints were extracted to `api/product_commercial_readiness.py` while `api.product` keeps compatibility imports.
- Product scope-breadth-evidence-receipt, full-commercial-blocker-evidence-matrix, engine-refinement-claim-evidence-receipt, engine-refinement-claim-evidence-priority, and goal-completion-audit endpoints were extracted to `api/product_evidence_goal.py` while `api.product` keeps compatibility imports.
- Stage-level typed input/output and machine-readable failure taxonomy exist in `betelgeuze_engine.biodiscovery.contracts`.
- Protein preparation/topology helpers are factored into `betelgeuze_engine.biodiscovery.protein_prep` and keep unsupported metal/cofactor plus placeholder topology fail-closed behavior in the canonical service.
- Ligand preparation/topology helpers are factored into `betelgeuze_engine.biodiscovery.ligand_prep` and preserve SDF/MolBlock provenance through the canonical service.
- Pose/pocket pure domain helpers are factored into `betelgeuze_engine.biodiscovery.pose` and wired through the canonical screening service.
- Scoring/refinement/stability helpers are factored into `betelgeuze_engine.biodiscovery.scoring` and keep cell-list neighbor, guarded forcefield, MM/GBSA proxy, and short stability diagnostics outside service orchestration.
- Signed manifest and claim-boundary helpers are factored into `betelgeuze_engine.biodiscovery.manifest`, preserving HMAC signature, replay hash, artifact hash, and blocked-claim metadata semantics.
- Existing HTVS/backmapping runner modules expose compatibility hooks through the shared typed Tier-beta runner adapter.
- Local fixture, tests, signed manifests, and machine-readable receipt exist.
- API worker and CLI compatibility paths can emit review-only EvidenceBundle artifacts with canonical fingerprints.
- Ligand salt/counterion inputs can score an unsupported-free parent fragment for diagnostics, but the result is explicitly non-product-safe and blocked for claim promotion.
- RDKit ChemicalFeatures donor/acceptor sites, dual-role atoms, unspecified tetrahedral/double-bond stereochemistry blockers, bounded projected tautomer states, and bounded RDKit SMARTS pH-range protomer candidates are recorded; projected protomer/tautomer/charge/salt-parent states remain non-product-safe unless separately validated.
- Docking gold metric evaluation now blocks partial reference/native RMSD coverage instead of passing on any finite RMSD row.
- Local PDBbind/CASF adapter readiness now depends on full gold metric readiness: affinity labels, decoys, chemistry-failure evidence, abstention evidence, measured builder runtime/peak-memory, row-level symmetry-aware reference RMSD coverage, and same-paired held-out refine Spearman improvement must all be present.
- Product image smoke verification preserves fail-closed receipt writing after the API container has started by combining cleanup and blocked-receipt EXIT handling.
- Release CI remote-green status is now machine-readable through `tools/product/build_release_ci_remote_green_receipt.py` and `runs/release_ci_remote_green_receipt_current.json`; the current read-only GitHub evidence passes Linux/ROCm runner checks but blocks on `main` required checks, weekly scheduled ROCm runtime evidence, failed-run artifact preservation evidence, and release-tag ROCm runtime evidence.

## Remaining Gaps

| Area | Gap | Current disposition |
|---|---|---|
| Exact chemistry | RDKit SMILES topology and single-record SDF/MolBlock intake preserve atoms, bonds, formal charges, ChemicalFeatures donor/acceptor sites, dual-role atoms, stereochemistry status, and source provenance through a separated ligand preparation/topology module. Salt/counterion parent-fragment and projected protomer/tautomer/charge diagnostics are explicitly claim-blocked. Multi-record SDF libraries, calibrated pKa-backed ionization-state enumeration, validated tautomer/protomer selection, and metal/cofactor parameterization are still not implemented. | Restricted local only; advanced chemistry preparation remains P1 and customer affinity claims stay blocked. |
| Protein preparation | PDB/mmCIF input resolution, parsing, and topology validation are separated into a protein preparation module, but parser coverage is intentionally small and rejects cofactors/metals instead of parameterizing them. | Fail closed for unsupported metal/cofactor. |
| Protein mmCIF | Minimal `_atom_site` loop parsing supports local vertical-slice fixtures and model 1 coordinates, but full mmCIF category coverage, assemblies, altlocs, insertion codes, and biological-unit expansion are not implemented. | Restricted local only; unsupported complexity must remain fail-closed or explicitly audited. |
| Pose accuracy | Pose ensemble generation, pocket placement, RMSD, clash, conformer-diversity diagnostics, and chemistry-validity row helpers are now separated from service orchestration. The vertical-slice pose search now includes deterministic SO(3) rotation sampling, pocket translation-grid exploration, coarse-score beam search, and a six-parameter rigid-body finite-difference local minimizer over translation plus rotation. The local PDBbind/CASF adapter computes symmetry-aware heavy-atom RMSD in the receptor frame and blocks incomplete reference/evidence coverage, but no public holdout RMSD or enrichment benchmark is claimed; partial RMSD coverage, missing affinity labels, missing decoys, missing chemistry/abstention evidence, missing measured resource metrics, or absent held-out refine improvement block benchmark promotion. | Claim blocked until row-level public holdout evidence exists. |
| Refinement | Top-K refine now calls a separated scoring module for guarded forcefield plus internal MM/GBSA proxy, not production all-atom/OpenMM/FEP. | Calibrated affinity/FEP remains blocked. |
| EvidenceBundle | API and CLI paths emit review-only EvidenceBundle provenance, but validation flags intentionally retain delivery/topology/interaction gaps until stronger science artifacts exist. | EvidenceBundle is provenance/review evidence, not customer scientific validation. |
| Manifest signing | Engine result manifest construction is separated from service orchestration and still emits HMAC signature, content hash, deterministic replay hash, and blocked-claim metadata. | Local signing only; enterprise KMS/key rotation remains P2. |
| Stability simulation | Optional short stability now runs through a separated scoring/stability module and records constraints/PBC/thermostat/energy-drift/restart diagnostics, but remains a local smoke rather than validated MD. | MD science claims remain blocked. |
| API decomposition | Product routes are split across focused routers; legacy `api/product.py` is now a compatibility facade that re-exports handlers for older direct imports. | Maintain compatibility imports while future product surfaces are added to focused routers. |
| Runner migration | Existing HTVS/backmapping runners now expose canonical-service hooks through `tier_beta_runner_compat` and a versioned typed adapter request, but their legacy CSV/subprocess orchestration remains for older non-Tier-beta profiles. | Canonical Tier-beta implementation lives under `betelgeuze_engine/**`; broader legacy runner rewrite remains P1/P2. |
| Release CI | Remote runner inventory now shows one online self-hosted Linux/ROCm runner. The local remote-green receipt builder records `external_state_mutated:false` and currently blocks because `main` branch protection is disabled, required checks are not configured, weekly scheduled runtime evidence has not appeared, failed-run artifacts were not observed on the audited remote run, and no release-tag runtime run has been observed. | External GitHub branch protection/check configuration and release/schedule evidence are still required before P0-2 can close. |
| Enterprise platform | No PostgreSQL/durable queue/object storage/GPU scheduler/OIDC tenant proof was added. | Broad platform claim remains blocked. |

## Claim Boundary

This slice supports only: restricted local BioDiscovery vertical-slice computation and provenance review. It does not support broad platform, AlphaFold parity, calibrated Delta G/FEP, wetlab hit, or external validation claims.

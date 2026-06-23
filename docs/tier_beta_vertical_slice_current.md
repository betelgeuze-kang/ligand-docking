# Tier Beta Vertical Slice Current

Status: restricted local Tier-beta BioDiscovery vertical slice
Scope: local PDB/mmCIF-style protein input plus SMILES/SDF-style ligand input, no external data lookup or external mutation

## Implemented Surface

- Canonical service: `betelgeuze_engine.biodiscovery.TierBetaScreening`
- Canonical protein preparation/topology helpers: `betelgeuze_engine.biodiscovery.protein_prep`
- Canonical ligand preparation/topology helpers: `betelgeuze_engine.biodiscovery.ligand_prep`
- Canonical pose/pocket domain helpers: `betelgeuze_engine.biodiscovery.pose`
- Canonical scoring/refinement/stability helpers: `betelgeuze_engine.biodiscovery.scoring`
- Canonical signed manifest/claim-boundary helpers: `betelgeuze_engine.biodiscovery.manifest`
- Product application service: `betelgeuze_product.tier_beta_vertical_slice`
- API direct worker path: `runner_profile_id=tier_beta_biodiscovery_direct`
- Decomposed routers: `api/product_tier_beta.py` under `/product/tier-beta/*`, `api/product_docking.py` for legacy `/product/docking/*` plus `/product/structure/analyze`, `api/product_capabilities.py` for `/product/capabilities`, `api/product_architecture.py` for `/product/architecture*`, `api/product_service_contracts.py` for `/product/service-boundary` plus `/product/api-contract`, `api/product_operational.py` for `/product/operational-quality` plus `/product/security-deployment-contract`, `api/product_release_ops.py` for `/product/operations`, `/product/commercial-independence`, `/product/release-readiness`, and `/product/job-orchestration-contract`, `api/product_license.py` for `/product/license-decision`, `/product/license-file-work-order`, `/product/self-hosted-license-distribution-audit`, and `/product/license-options`, `api/product_benchmark.py` for `/product/external-metrics`, `/product/public-benchmark`, `/product/trajectory-sla-contract`, and `/product/rollout-execution-smoke-receipt`, `api/product_ai_surface.py` for `/product/ai-decision-graph`, `/product/pose-sampling-readiness`, `/product/ai-report-ux`, and `/product/residual-model-registry`, `api/product_cameo_runner.py` for `/product/cameo-live-validation`, `/product/cameo-official-result-fetch-preflight`, `/product/api-runner-profile-promotion-operator-receipt`, and `/product/api-runner-profile-promotion-operator-staging-apply`, `api/product_production_ai.py` for `/product/production-ai-checkpoint-readiness`, `/product/production-ai-gpu-worker-dispatch-manifest`, `/product/production-ai-gpu-worker-dispatch-bundle`, `/product/production-ai-gpu-worker-execution-runbook`, `/product/production-ai-gpu-return-intake`, `/product/production-ai-promotion-workbench`, `/product/production-ai-registry-promotion-operator-receipt`, and `/product/production-ai-registry-promotion-priority`, `api/product_scope.py` for `/product/scope-breadth-contract`, `/product/scope-claim-guard`, `/product/scope-evidence-priority`, `/product/scope-evidence-intake-readiness`, `/product/transporter-manual-review-intake`, `/product/pxr-exact-review-intake`, `/product/aqp1-operator-validation-candidate`, and `/product/aqp1-direct-binding-procurement-packet`, `api/product_commercial_readiness.py` for `/product/commercial-readiness-operator-packet`, `/product/commercial-readiness-operator-packet-freshness`, `/product/commercial-readiness-execution-ladder`, and `/product/commercial-readiness-handoff-bundle`, and `api/product_evidence_goal.py` for `/product/scope-breadth-evidence-receipt`, `/product/full-commercial-blocker-evidence-matrix`, `/product/engine-refinement-claim-evidence-receipt`, `/product/engine-refinement-claim-evidence-priority`, and `/product/goal-completion-audit`
- CLI compatibility wrapper: `tools/run_tier_beta_vertical_slice.py` with signed result manifest and optional EvidenceBundle output
- Existing runner compatibility hooks: `run_tier_beta_vertical_slice_compat(...)` in `htvs_pipeline.py` and `backmapping_scoring.py`, both delegating through the shared typed adapter `betelgeuze_engine.product.runners.tier_beta_runner_compat`
- Local fixtures: `tests/fixtures/tier_beta/mini_protein.pdb`, `tests/fixtures/tier_beta/mini_protein.cif`, `tests/fixtures/tier_beta/benzene.smi`, and `tests/fixtures/tier_beta/ethanol.sdf`
- Local receipt: `.betelgeuze/tier_beta_vertical_slice_receipt_current.json` (4-step stability smoke, signed manifest, and EvidenceBundle fingerprint included)

## Workflow

The direct service runs a typed Python workflow without internal CSV handoff:

PDB or limited mmCIF atom-site-loop protein input + SMILES or SDF/MolBlock ligand input -> protein/ligand preparation -> topology validation -> pocket resolution -> pose ensemble -> scoring/ranking -> top-K refinement proxy -> optional short stability simulation -> signed result manifest.

API worker and CLI compatibility paths both emit signed result-manifest provenance; the API worker always attaches an EvidenceBundle, and the CLI can emit the same review-only EvidenceBundle via `--evidence-bundle-json`. Signed manifests also include a deterministic `replay_hash` over the calculation payload excluding volatile timestamp/signature fields.

Each stage emits a `StageRecord` with schema version, status, failure code, and diagnostics. The request/response surfaces are represented by `TierBetaScreeningInput` and `TierBetaScreeningOutput` in `betelgeuze_engine.biodiscovery.contracts`.

Protein input resolution, PDB/mmCIF parsing, unsupported metal/cofactor blocking, and placeholder topology validation are factored into `betelgeuze_engine.biodiscovery.protein_prep`. Ligand input resolution, SDF/MolBlock provenance capture, RDKit-backed ligand topology validation, and row-level topology payload construction are factored into `betelgeuze_engine.biodiscovery.ligand_prep`. Pose conformer generation, pocket placement, pose RMSD, clash counting, chemistry-validity row summaries, and virtual protein beads are factored into `betelgeuze_engine.biodiscovery.pose`. Cell-list neighbor scoring, guarded forcefield evaluation, MM/GBSA proxy scoring, and short stability diagnostics are factored into `betelgeuze_engine.biodiscovery.scoring`. HMAC signing, replay/content hashes, blocked-claim metadata, and claim-boundary construction are factored into `betelgeuze_engine.biodiscovery.manifest` so the canonical service orchestration no longer owns those pure domain helpers inline.

## Safety Boundaries

- Dense diagnostic allocation is capped by `betelgeuze_engine.physics.dense_guard.ensure_small_dense_diagnostic`.
- Product scoring uses `CellListNeighborProvider` and `ProductForceField(..., product_neighbor_required=True)`.
- Reference full-pairs / NxN product paths fail closed.
- Neighbor overflow fails closed.
- Placeholder or missing protein sequence fails closed.
- Unsupported metals/cofactors in protein input fail closed.
- Invalid ligand topology and unassigned chirality fail closed.
- Unsupported ligand metal/counterion states are not promoted to product-safe success; fragment-parent salt scoring remains claim-blocked and records the projection boundary.
- Unsigned engine/API result manifests are treated as blocked.

## Scientific Contract

Each pose row records pose rank, score components, uncertainty, abstention, topology fidelity, ligand atom/bond/charge/chirality/protonation/tautomer provenance, neighbor diagnostics, and claim boundary. SMILES input is parsed through RDKit-backed topology validation; SDF/MolBlock input is parsed directly with RDKit and preserves exact atom elements, bonds, formal charges, RDKit ChemicalFeatures donor/acceptor sites including dual-role atoms, chirality/stereochemistry status, and input source provenance in both pose rows and the signed manifest.

Pose rows also record local ensemble RMSD metrics, clash count, chemistry validity, conformer-diversity diagnostics, retained conformer indices, and the ranking metric used for the restricted local ordering. Protonation remains a restricted input/formal-charge policy at pH 7.4 without pKa enumeration, and projected tautomer/charge/salt-parent states are diagnostic-only unless separately validated. Stability diagnostics record constraints/PBC/thermostat posture, energy drift, and restart reproducibility fields for the short local smoke.

The implementation performs real local calculations but still blocks:

- calibrated affinity claims
- FEP parity claims
- wetlab-hit claims
- broad platform claims
- AlphaFold parity claims

`claim_metadata.claim_safe` therefore remains `false` for customer science claims even when the restricted local computation completes successfully.

## Verification Coverage

Focused tests cover:

- service-level PDB+SMILES success path
- service-level mmCIF+SMILES success path
- service-level PDB+SDF/MolBlock success path with topology provenance
- invalid ligand, unassigned chirality, placeholder protein, unsupported metal/cofactor negative paths
- invalid SDF ligand fail-closed without fallback to SMILES
- API submit -> worker -> result direct E2E
- API placeholder-topology submit -> worker -> failed signed manifest direct E2E
- `/product/tier-beta/docking/jobs` router submit -> inline worker -> result direct E2E
- `/product/tier-beta/docking/jobs` placeholder-topology submit -> inline worker -> failed signed manifest direct E2E
- `/product/capabilities` route ownership through the decomposed product capability router
- `/product/architecture` and `/product/architecture-validation` route ownership through the decomposed product architecture router
- `/product/service-boundary` and `/product/api-contract` route ownership through the decomposed service-contract router
- engine manifest signature and API artifact hash verification
- unsigned engine manifest fail-closed regression
- deterministic replay hash and pose-ranking replay
- row-level RMSD/clash/chemistry/ranking metrics
- ligand salt/counterion fragment-parent projection remains non-product-safe even when the parent fragment is scored
- unspecified tetrahedral or double-bond ligand stereochemistry fails closed
- bounded projected tautomer states remain non-product-safe unless validated separately
- docking gold metrics fail closed when reference/native pose RMSD coverage, affinity labels, decoys, runtime/memory, or held-out refine-improvement evidence are incomplete
- canonical protein preparation/topology helper extraction is wired through the screening service
- canonical ligand preparation/topology helper extraction is wired through the screening service
- canonical pose/pocket domain helper extraction is wired through the screening service
- canonical scoring/refinement/stability helper extraction is wired through the screening service
- canonical signed manifest helper extraction is wired through the screening service
- stability constraints/PBC/thermostat/energy-drift/restart diagnostics
- CLI compatibility
- CLI EvidenceBundle output and fingerprint validation
- canonical Tier-beta service/application/API/runner adapter/CLI paths do not use subprocess, CSV, pandas, or tempfile handoff
- dense/reference-neighbor bypass regression
- neighbor overflow fail-closed regression before signed result emission
- existing HTVS/backmapping compatibility hooks call the canonical service
- typed Tier-beta runner adapter payload normalization

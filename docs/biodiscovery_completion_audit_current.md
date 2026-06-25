# BioDiscovery Completion Audit Current

Status: current objective audit
Scope: local-only BioDiscovery commercial-platform transition goal
Boundary: no external data, no external mutation, no broad platform/AlphaFold parity/wetlab-hit/calibrated Delta G claim promotion

## Requirement Audit

| Requirement | Current evidence | Verdict |
|---|---|---|
| Inventory tracked `.py,.rs,.hip,.c,.cpp,.h,.js,.ts,.sh,.yml,.yaml,.toml` files with `git ls-files`. | `docs/code_architecture_inventory_current_files.tsv` contains 5,654 scoped tracked files plus the inventory method in `docs/code_architecture_inventory_current.md`. | complete |
| Classify files into `core/adapter/runner/API/train/benchmark/test/deploy/generated`. | TSV `bucket` column covers the required buckets for every scoped tracked file. | complete |
| Record responsibility, caller, duplicate/dead code, monolith, external dependency, test/product path. | TSV columns: `responsibility`, `caller_surface`, `duplicate_dead_code_risk`, `monolith_risk`, `external_dependency_risk`, `product_path`, `tested_path`, `risk_flags`. | complete |
| Do not inspect forbidden secret/runtime/generated-heavy content. | Audit docs state exclusions; inventory TSV is file-name based. No `runs/**` content, secret environment content, large CASP/generated data, or binaries were used as evidence. | complete |
| Treat current state as restricted Tier-alpha pilot. | `docs/product_pm_architecture_current.md` states restricted Tier-alpha pilot and separates allowed/blocked claims. | complete |
| Separate accounting green from scientific validity. | `docs/product_pm_architecture_current.md`, `docs/scientific_benchmark_contract.md`, and `config/product_capability_matrix.yaml` split `accounting_green` from `scientific_validity_green`; verifier blocks conflation without row-level evidence. | complete |
| Define target contracts. | `docs/target_bioscience_architecture.md` covers `Sequence`, `Polymer`, `Ligand`, `Complex`, `Topology`, `PoseEnsemble`, `SimulationSpec`, `Trajectory`, `PredictionConfidence`, `EvidenceBundle`. | complete |
| Define science architecture. | `docs/target_bioscience_architecture.md` covers structure prep/quality, sequence-to-structure, pocket, pose, scoring/ranking, all-atom refine, MD, free energy, interaction/trajectory analysis. | complete |
| Define execution architecture. | `docs/target_bioscience_architecture.md` covers versioned API/SDK/CLI, PostgreSQL, durable queue, GPU scheduler, object storage, registry, DAG, OIDC/RBAC, tenant isolation, provenance, metrics/tracing, retry/idempotency. | complete |
| Keep `core/**` as compatibility-adapter target and decompose subprocess/CSV runners into typed service/DAG target. | `docs/target_bioscience_architecture.md` migration rules and `docs/code_architecture_inventory_current.md` findings record this target state. | complete |
| Define structure-prediction, docking, MD, Delta G, and AI development lanes with honest blockers. | `docs/product_pm_architecture_current.md`, `docs/target_bioscience_architecture.md`, and `config/product_capability_matrix.yaml` define these lanes and blocked claim states. | complete |
| Define benchmark/promotion contract with row-level evidence and fail-closed thresholds. | `docs/scientific_benchmark_contract.md` specifies benchmark shape, metrics, claim states, and immediate gate. | complete |
| Create `config/product_capability_matrix.yaml`. | Matrix exists with P0-P4 rows, owners, risk, dependencies, DoD, claim states, and fail-closed flags. | complete |
| Create P0-P4 backlog with dependency/DoD/risk/owner. | `docs/biodiscovery_p0_p4_backlog.md` summarizes the matrix; YAML remains source of truth. | complete |
| Implement first P0 slice without external data. | `betelgeuze_product/capability_matrix.py` and `scripts/verify_product_capability_matrix.py` implement CI-truthfulness overclaim guard from local YAML only. | complete |
| Keep broad platform, AlphaFold parity, wetlab-hit, calibrated Delta G/FEP claims blocked until evidence. | Matrix high-risk rows are blocked; verifier checks row states and policy flags; tests mutate each high-risk row. | complete |
| Add focused tests. | `tests/unit/test_product_capability_matrix.py` covers current pass, all high-risk overclaims, missing metadata, policy drift, unsafe flags, and missing high-risk rows. | complete |
| Run required verification. | Latest checks: focused pytest passed; `scripts/verify_product_capability_matrix.py --quiet` passed; `./scripts/ai-verify.sh` passed; `git diff --check` passed. | complete |
| Do not stage, commit, push, deploy, submit, delete, or mutate external state. | Worktree only has local uncommitted changes. No staging/commit/push/deploy/submission commands were run. | complete |

## Residual Non-Completion For The Broader Product

These are intentionally blocked product/science capabilities, not blockers for this local transition-planning objective:

- Broad platform claim remains blocked.
- AlphaFold-parity language remains blocked.
- Calibrated Delta G/FEP claim remains blocked.
- Wetlab-hit claim remains blocked.
- Product-mode verification still reports pre-existing release source-of-truth/refresh blockers outside the requested `./scripts/ai-verify.sh` smoke gate.

## Tier-Beta Vertical Slice Update

Current restricted local Tier-beta implementation evidence:

- `betelgeuze_engine/physics/dense_guard.py` is adopted as canonical dense diagnostic guard code, not excluded.
- `betelgeuze_engine/biodiscovery/` implements typed local PDB/mmCIF-style protein plus SMILES/SDF-style ligand screening.
- SDF/MolBlock ligand intake is parsed through RDKit and carries atom, bond, formal-charge, chirality, and source provenance into pose rows and signed manifests.
- `api/product_tier_beta.py` and `betelgeuze_product/tier_beta_vertical_slice.py` provide the decomposed API/application service path.
- `tools/run_tier_beta_vertical_slice.py` provides CLI compatibility.
- `betelgeuze_engine.biodiscovery.contracts` provides versioned stage records and machine-readable failure codes.
- API worker and CLI compatibility paths emit signed manifests plus review-only EvidenceBundle provenance with canonical fingerprints.
- `htvs_pipeline.py` and `backmapping_scoring.py` expose `run_tier_beta_vertical_slice_compat(...)` hooks to the canonical service.
- Pose rows record RMSD-to-top1/top5-centroid, clash count, chemistry validity, ranking metric, and neighbor diagnostics.
- Stability smoke records constraints/PBC/thermostat/energy-drift/restart diagnostics.
- `.betelgeuze/tier_beta_vertical_slice_receipt_current.json` records the local fixture result, 4-step stability smoke, and signed manifest hashes.

This update does not promote broad platform, AlphaFold parity, calibrated affinity/FEP, or wetlab-hit claims.

## Acceptance

The requested local objective is satisfied by the files above and the focused verification results. The commercial platform itself remains a staged roadmap with P0-P4 blockers tracked in `config/product_capability_matrix.yaml`.

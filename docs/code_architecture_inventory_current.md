# Code Architecture Inventory Current

Status: current local audit snapshot
Scope: tracked source/config files with `.py`, `.rs`, `.hip`, `.c`, `.cpp`, `.h`, `.js`, `.ts`, `.sh`, `.yml`, `.yaml`, `.toml`
Method: `git ls-files` inventory plus representative reads of product/API/contracts/topology/verification surfaces
Exclusions: no secret environment file content, no `runs/**` content, no large CASP/generated data, no binary inspection, no external web/data lookup

Companion per-file inventory: `docs/code_architecture_inventory_current_files.tsv`

The TSV contains all 5,654 scoped tracked files with `path`, `bucket`, `responsibility`, `caller_surface`, `duplicate_dead_code_risk`, `monolith_risk`, `external_dependency_risk`, `product_path`, `tested_path`, and `risk_flags`. It is generated from file names only; source contents were read only for the representative files summarized below.

## Inventory Counts

| View | Count |
|---|---:|
| tracked files in scoped extensions | 5,654 |
| Python | 5,610 |
| shell | 17 |
| YAML/YML | 17 |
| JavaScript | 4 |
| Rust | 3 |
| TOML | 2 |
| HIP | 1 |
| non-`tools`/`tests`/CASP tracked product source/config subset | 273 |

Top-level distribution:

| Area | Count | Notes |
|---|---:|---|
| `tools/` | 3,813 | Dominant runner/accounting/generator surface; high duplication and generated-like risk. |
| `tests/` | 1,568 | Broad unit coverage, mostly receipt/gate oriented. |
| `betelgeuze_engine/` | 45 | Canonicalizing physics/topology/product runner package. |
| `core/` | 34 | Legacy/compatibility physics and model modules; should shrink toward adapters. |
| `betelgeuze_product/` | 34 | Product contracts, execution preflight, capability/readiness surfaces. |
| `betelgeuze_cameo/` | 24 | Competition/live validation support; external mutation must stay approval-gated. |
| `api/` | 19 | FastAPI product/CAMEO/CASP/cleanup/job surfaces. |
| `train/` | 15 | Training/data runtime inputs; not product-claim ready by itself. |
| `deploy/`, `.github/`, `monitoring/` | 27 | Container/Kubernetes/workflow/alerting surfaces. |

## Bucket Classification

| Bucket | Primary files/dirs | Responsibility | Caller/product path | Risk notes |
|---|---|---|---|---|
| `core` | `betelgeuze_engine/**`, `core/**`, `runtime/**`, `rust_engine/**` | Physics, topology, interaction terms, residual guards, legacy kernels. | Product runners, benchmarks, selected tools. | `core/**` still mixes canonical and compatibility roles; dense/NxN and proxy physics need explicit fail-closed guards. |
| `adapter` | `betelgeuze_ai_md/contracts/**`, `betelgeuze_product/**`, `betelgeuze_engine/topology/**` | Typed product contracts, topology bridge, capability/readiness adapters. | API endpoints, scripts, tests. | Contract coverage exists but target canonical objects are not yet complete as one cohesive domain model. |
| `runner` | `tools/**`, `scripts/**`, `betelgeuze_engine/product/runners/**`, `run_*.py` | Gate builders, receipts, HTVS/backmapping/top-K flows, orchestration utilities. | CLI/operator paths and product evidence artifacts. | Largest duplication/dead-code risk; many tools are accounting/report builders rather than canonical services. |
| `API` | `api/product.py`, `api/main.py`, `api/validated_runner.py`, `api/worker.py`, `api/docking_dispatch.py` | HTTP product surface, job dispatch, worker integration. | Product routes under `/product`. | `api/product.py` is a monolith (>10k lines) and should be decomposed into typed service modules. |
| `train` | `train/**`, `train_router.py`, `theory/**` | Training, residual/model experimentation, theory branches. | Mostly offline/experimental. | Requires leakage-free split, model cards, confidence calibration, and rollback before product claims. |
| `benchmark` | `benchmark/**`, `betelgeuze_engine/benchmark/**`, `betelgeuze_engine/validation/**` | Accuracy/performance/force checks and public-scorecard helpers. | Product quality and science frontier gates. | Evidence often proves accounting readiness; scientific validity needs row-level public holdout receipts. |
| `test` | `tests/**` | Unit and gate regression coverage. | CI/local verification. | Broad but receipt-heavy; scientific numerical kernels need deeper invariant/reference tests. |
| `deploy` | `deploy/**`, `.github/workflows/**`, `monitoring/**`, `config/*.yaml` | Product container, K8s, workflows, alerts, config. | Product smoke/deploy readiness. | Hosted/tenant/OIDC/RBAC/durable queue are not complete enterprise platform claims. |
| `generated` | `tools/accounting/**`, many `tools/product/build_*` | Generated or template-like packet builders. | Operator evidence generation. | Strong candidate for registry-driven consolidation and dead-code review. |

## High-Signal Current Findings

| Finding | Evidence | Product meaning |
|---|---|---|
| Restricted product accounting is mature. | `betelgeuze_product/capability_surface.py`, `architecture.py`, `readiness.py`, `scripts/check_independent_product_readiness.py` keep `execution_enabled=False`, external mutation false, broad platform false. | Good Tier-alpha pilot posture; not general scientific validity. |
| API product surface exists but is monolithic. | `api/product.py` exposes many `/product/*` endpoints and is over 10k lines. | Decompose into API router + typed service/DAG modules before enterprise scaling. |
| Topology is moving toward sequence-mapped fail-closed validity. | `betelgeuze_engine/topology/factory.py`, `betelgeuze_ai_md/contracts/topology_adapter.py`. | Good P0 direction, but exact all-atom bond/charge/parameter provenance is still a blocker. |
| Product runner paths exist. | `betelgeuze_engine/product/runners/backmapping_scoring.py`, `htvs_pipeline.py`, `topk_delivery.py`. | Useful vertical-slice substrate; needs typed services replacing subprocess/CSV orchestration. |
| Rust/HIP presence is real but small. | `rust_engine/src/lib.rs`, `rust_engine/src/nonbonded_kernel.hip`. | Promising acceleration lane; product claim depends on parity/scaling receipts. |
| Claim guards are explicit. | README and independent readiness scripts block broad GPCR/platform/wetlab/parity claims. | Accounting green and scientific validity are intentionally separated. |

## P0 Candidate Selected

Implemented in this slice: `config/product_capability_matrix.yaml` plus `scripts/verify_product_capability_matrix.py`.

Reason: it is external-data-free, small, CI-friendly, and directly enforces the highest-risk product transition boundary: no broad platform, AlphaFold parity, calibrated Delta G/FEP, or wetlab-hit claim without row-level independent evidence.

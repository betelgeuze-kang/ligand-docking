# Ligand Docking and Molecular Dynamics Delivery Engine

[한국어 README](README.ko.md)

This repository contains two deliberately separated surfaces:

1. **Independent Engine v2** — versioned molecular contracts, bounded sparse
   geometry, CPU reference AI/physics composition primitives, strict checkpoint
   handling, bounded PDB/SDF ingestion, docking-search scaffolds, and a complete
   benchmark failure-row ledger.
2. **Legacy/product delivery stack** — local validated-runner workflows, evidence
   gates, API, wetlab packets, CASP/CAMEO preparation, and restricted delivery
   tooling.

The V2 short-range geometry path has a **conditional bounded-degree `O(N)`
algorithmic contract** when density, cutoff, neighbor/cell capacity, model width,
and candidate budgets remain fixed. This is not evidence of measured end-to-end
`O(N)` scaling for the entire repository or for long-range physics.

## Engine v2 Current Status

Current implementation stage:

```text
v2_ag_minimization_validation_nonce_reservation
```

Implemented and GitHub-hosted CPU tested:

- canonical all-atom state, validation stages, and SHA-256 identities;
- bounded sparse radius geometry and periodic image-shift gradients;
- scalar-energy AI reference model with exact coordinate gradients;
- matrix-free projection, torsion, temporal, and physics-gate primitives;
- fail-closed CPU orchestration and strict runtime/checkpoint fingerprints;
- independent `betelgeuze-engine-v2` wheel for Python 3.10–3.12;
- bounded single-model PDB and single-molecule SDF V2000 parsers;
- independent physics-term registry contracts;
- bounded deterministic CPU `float64` reference minimization with retained
  failure rows and exact checkpoint/restart identity, without scientific or
  product promotion;
- bounded component-energy central-difference force diagnostics and
  non-periodic configurational virials, with every perturbation retained and
  periodic virials fail-closed;
- a separate versioned reference-forcefield extension with ordered-star
  harmonic out-of-plane improper energy/forces and bounded deterministic
  symmetric degree-relaxed equal-weight distance-constraint projection, plus
  projected Armijo minimization with tangent-force convergence and exact
  checkpoint/restart; it is not mass weighted, scientifically validated, or
  product enabled;
- bounded non-periodic CPU `float64` polar Generalized Born transfer energy and
  exact forces using caller-supplied fixed effective Born radii, plus a combined
  v2 evaluator and optional constrained-minimization integration with exact
  solvation-parameter-bound checkpoint/restart; radius estimation, nonpolar
  solvation, salt/ions, periodic solvent, independent validation, and product
  promotion remain unavailable;
- a frozen, execution-disabled CPU minimization validation protocol with 14
  ordered unsolvated, constrained, fixed-Born constrained, checkpoint, and
  fail-closed cases; 10 predefined metrics, all-case failure accounting, exact
  implementation-source identities, and independent-reference requirements are
  bound before results; a separate exact materializer converts all 11 fixtures
  and 14 cases to deterministic CPU float64 v1/v2/fixed-Born runtime inputs,
  checkpoint-pause plans, and failure injections without evaluating physics or
  collecting results; a separately source-bound standard-library reference now
  independently implements constraint/tangent-force projection, fixed-Born,
  bounded backtracking, fail-closed identities, and exact checkpoint/restart,
  while test-only comparisons remain implementation checks rather than
  validation results; a frozen HMAC-SHA256 independent-review attestation
  contract now requires author/reviewer identity separation, complete ordered
  checks and limitation acknowledgements, an out-of-band trusted reviewer key,
  and bounded freshness; separate frozen CPU-only, network-disabled execution-
  environment and failure-inclusive result-receipt contracts bind the exact
  14-case/10-metric order and both operational/independent input identities,
  but no attestation, trusted reviewer key, authorization receipt,
  environment/result receipt, runner, result, or scientific promotion exists;
  a separate single-run HMAC-SHA256 authorization contract now binds a verified
  nonexpired review, pairwise-distinct operator, exact code/runner/dependencies,
  both receipt contracts, 24-hour maximum validity, revocation inputs, and a
  one-time nonce, but bundles no operator key, receipt, or nonce reservation;
  a local POSIX reservation primitive now re-verifies the raw signed review and
  authorization chain before consuming the nonce exactly once as a canonical
  mode-0600 record beneath a caller-provisioned mode-0700 root using `O_EXCL`,
  file `fsync`, and directory `fsync`; it has no release/delete API and bundles
  no production root, key, signed artifact, reservation, or execution;
- a frozen CPU reference energy/force contract-validation protocol with exact
  synthetic case identities, predefined tolerances, retained failure rows, and
  a closed execution/parameter-fitting authorization gate, plus exact fixture
  materialization and a source-bound standard-library-only analytic oracle that
  collect no validation result, plus a frozen signed independent-review
  attestation contract that requires author/reviewer separation and an
  out-of-band trusted reviewer key, and a separate single-run authorization
  receipt contract with operator separation, 24-hour expiry, revocation inputs,
  and one-time nonce semantics, plus frozen CPU execution-environment and
  failure-inclusive result-receipt schemas for all 27 cases and 59 variants,
  and a local POSIX `O_EXCL`/`fsync` one-time nonce-reservation primitive that
  re-verifies both raw signed artifacts before durable consumption, followed by
  a run-start primitive that re-verifies the full chain, observes the live
  CPU-only deterministic process, verifies a short-lived operator-signed
  network-isolation attestation, and atomically persists a secret-free
  environment receipt, followed by a bounded CPU float64 runner that re-reads
  and re-verifies that receipt and its exact code, source, dependency, and
  artifact bindings—including a read-only Git clean-checkout proof for the
  observed `HEAD` and frozen reference-
  evaluator source—atomically consumes a one-time runner-start marker, and
  retains every result or failure for the exact 27-case/59-variant matrix in
  memory under a POSIX-interrupted 120-second materialization/evaluator/oracle
  budget, followed by a failure-inclusive
  result writer that re-verifies the raw signed chain, live environment receipt,
  runner-start marker, and exact observation before atomically persisting one
  canonical private mode-0600 receipt. Its reader requires an out-of-band exact
  receipt hash plus external revocation/supersession inputs; no receipt signature
  or same-UID replacement resistance is claimed. The exact module command accepts
  only a bounded canonical JSON request without trust keys on standard input;
  reviewer/operator anchors come only from an externally provisioned, fixed-path,
  root-owned mode-0600 trust store that the repository does not bundle. It keeps
  trust material out of stdin, argv, and responses and performs environment
  receipt creation, the run, and result finalization in the same verified process.
  It requires that trust store plus a clean
  source checkout with Git metadata and fails closed when invoked only from an
  installed wheel.
  No trusted key, production receipt,
  reservation or artifact root, production nonce reservation, production
  environment receipt, runner start/result receipt, authorized production
  execution, independent result review, or scientific acceptance is bundled;
- deterministic bounded torsion/rigid docking proposal and search scaffolds;
- benchmark manifests with exactly one ordered success/failure row per case.

These surfaces are **not** calibrated docking, MD, free-energy, GPU, or customer
product capabilities. Every current V2 capability remains `claim_safe=false` and
`customer_execution_enabled=false`.

Start with:

- `docs/engine_v2_status.md`
- `docs/engine_v2_public_api.md`
- `config/independent_engine_v2_capabilities.yaml`
- `docs/entrypoints.md`

## Repository Contents

| Area | Purpose |
| --- | --- |
| `betelgeuze_engine_v2/` | Independent V2 contracts, molecular state, sparse geometry, AI/math primitives, strict ingest, physics registry, docking and benchmark scaffolds. |
| `packaging/engine-v2/` | Isolated `betelgeuze-engine-v2` distribution metadata. |
| `core/`, `betelgeuze_engine/` | Legacy physics/runtime and compatibility surfaces. They are not silently imported by the V2 wheel. |
| `api/`, `betelgeuze_product/` | Validated-runner product/API and delivery orchestration. |
| `tools/` | Gates, manifests, bundle builders, benchmark/accounting tools, and operational commands. |
| `tests/` | Unit and integration contracts for V2, legacy runtime, API, evidence, and delivery gates. |
| `config/` | Capability policy, target presets, thresholds, runtime profiles, and gate configuration. |
| `docs/` | Architecture, claim boundaries, reviewer entrypoints, delivery runbooks, wetlab material, and roadmaps. |
| `casp17/` | CASP17 local operator/review scaffolding and status documents. |

## Independent Engine v2 Quick Start

Build the isolated wheel from a clean clone:

```bash
python3 -m venv .venv-v2
source .venv-v2/bin/activate
python -m pip install --upgrade pip
python -m pip install "build>=1.2,<2" numpy==1.26.4
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python tools/build_engine_v2_wheel.py --output-dir dist-engine-v2
python -m pip install --no-deps dist-engine-v2/*.whl
python -m pip check
```

Inspect the machine-readable status:

```bash
python - <<'PY'
from betelgeuze_engine_v2.capabilities import capability_snapshot
import json
print(json.dumps(capability_snapshot(), indent=2, sort_keys=True))
PY
```

The root API is versioned by `ENGINE_API_VERSION`. V2-G ingest, docking,
benchmark, registry, and runtime submodules are provisional before distribution
version `1.0.0`; see `docs/engine_v2_public_api.md`.

## Monorepo Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run the canonical focused V2 suite:

```bash
python -m pytest -q \
  tests/unit/test_engine_v2_contracts_molecular.py \
  tests/unit/test_engine_v2_sparse_geometry_features.py \
  tests/unit/test_engine_v2_ai_core.py \
  tests/unit/test_engine_v2_periodic_energy.py \
  tests/unit/test_engine_v2_orchestrator_contract.py \
  tests/unit/test_engine_v2_runtime_checkpoint_contracts.py \
  tests/unit/test_engine_v2_packaging_guards.py \
  tests/unit/test_engine_v2_bounded_scaffolds.py \
  tests/unit/test_engine_v2_post_merge_state.py
```

`.github/workflows/ci-engine-v2-main.yml` repeats this contract on relevant pull
requests and every V2-related push to `main` using Python 3.10, 3.11, and 3.12.

## Product API (`/simulate`)

The HTTP product surface is **validated-runner ligand HTVS and backmapping
scoring only**. Generic molecular-dynamics simulation and Engine v2 customer
execution are intentionally unsupported.

```bash
pip install -r requirements-api.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```bash
curl -s -X POST http://127.0.0.1:8000/simulate \
  -H 'Content-Type: application/json' \
  -d '{"target_name":"ExampleTarget","runner_profile_id":"backmapping_scoring.example"}'
```

Requests without an approved `runner_profile_id` fail closed.

## Local Evidence and Delivery

Generated or sensitive local artifacts are intentionally excluded, including
`data/`, `runs/`, trajectories, checkpoints, local bundles, logs, and caches.
A clean clone contains source, tests, schemas, lightweight figures, and templates;
it does not prove local evidence gates or scientific performance.

For restricted delivery review, start with:

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_claim_policy.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/broad_claim_unlock_roadmap.md`

Local evidence validators are expected to fail closed until the required
artifacts are regenerated or supplied as a reviewed bundle.

## CASP17 and Other Operational Lanes

Detailed, time-sensitive CASP17 status is maintained in:

- `casp17/WORKBENCH.md`
- `casp17/CASP17_CURRENT_STATUS_REPORT.md`
- `casp17/CASP17_WIN_TIER_GOAL.md`

These are local preparation and operator-review surfaces. They do not establish
a submission, leaderboard, or win-tier claim.

## Claim Boundary

Currently acceptable statements:

- V2-G bounded CPU reference contracts and scaffolds are implemented and tested.
- The independent wheel installs in a clean environment for Python 3.10–3.12.
- Strict ingest records source hashes and does not silently infer chemistry.
- Docking and benchmark ledgers preserve failed candidates/cases instead of
  dropping them.
- Restricted local-delivery claims remain governed by their separate evidence
  gates and reviewed local artifacts.

Not acceptable without additional evidence:

- calibrated docking accuracy or broad virtual-screening performance;
- validated force-field, MD, MM/GBSA, FEP, or binding free-energy claims;
- CUDA/ROCm/HIP parity or acceleration claims;
- wetlab-proven hit claims;
- automatic scorer/router/platform promotion;
- broad commercial drug-discovery platform claims.

Implementation, scientific validation, public benchmark evidence, and product
qualification are separate stages. A green source-level test does not collapse
those stages.

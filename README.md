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
v2_q_cpu_reference_validation_nonce_reservation
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
  re-verifies both raw signed artifacts before durable consumption. No trusted
  key, production receipt, reservation root, production nonce reservation,
  environment receipt, runner, result writer, or authorized execution is present;
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

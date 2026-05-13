# Ligand Docking and Molecular Dynamics Delivery Engine

[한국어 README](README.ko.md)

This repository contains a local-delivery molecular dynamics and ligand validation stack. The project is built around a physics-first `O(N)` execution path, bounded AI residual correction, reproducible gates, and delivery artifacts that can be reviewed without exposing local runtime data.

The GitHub repository is intended to contain source code, configuration, tests, documentation, schemas, and delivery templates. Generated molecular dynamics data and heavy local artifacts are intentionally excluded.

## Repository Contents

| Area | Purpose |
| --- | --- |
| `core/` | Physics-first MD engine primitives, integrator logic, topology helpers, AI residual routing, spatial kernels, and GPU/runtime support. |
| `rust_engine/` | Rust/HIP acceleration scaffolding and native build surface. Build outputs are ignored. |
| `tools/` | Operational command-line tools for gates, manifests, delivery bundles, wetlab packets, evidence ledgers, benchmark summaries, and commercialization checks. |
| `tests/` | Unit and integration coverage for engine behavior, delivery gates, validation artifacts, packet builders, and regression guards. |
| `config/` | Target policies, calibration inputs, scorecards, acceptance thresholds, runtime presets, and gate configuration. |
| `docs/` | Architecture notes, validation plans, local-delivery runbooks, wetlab handoff material, publication drafts, and target-family roadmaps. |
| `docs/wetlab_packets/` | Lightweight partner-facing wetlab packet templates and CSV controls. |
| `benchmark/` | Accuracy and performance benchmark entry points. |
| `train/` | Residual model training pipeline entry points. |
| `api/`, `viewer/`, `deploy/`, `monitoring/` | Local service, visualization, deployment, and operational scaffolding. |
| `requirements*.txt` | Split dependency surfaces for runtime, development, API, training, deployment, and optional extras. |

## What Is Intentionally Not Tracked

The repository excludes generated or sensitive local artifacts through `.gitignore`, including:

- `data/`, `runs/`, `output/`, `logs/`, `models/`, `archives/`, `tmp/`, and `runtime/cache/`
- `.env`, `.env.*`, local agent metadata, virtual environments, Python caches, and test caches
- compiled/native outputs such as `*.so`, `*.dll`, `*.o`, Rust `target/`, and downloaded tool bundles
- large model or array artifacts such as `*.h5`, `*.npz`, `*.pt`, `*.pth`, `*.onnx`, `*.tar.gz`, and `*.tar.zst`

This keeps GitHub focused on reproducible implementation and documentation while leaving heavy MD trajectories, generated datasets, local model checkpoints, and delivery outputs on the local machine.

## Core Principles

1. Keep the default computational path `O(N)`.
2. Do not trade scientific accuracy for speed.
3. Use AI only as a bounded residual corrector over the physics core.
4. Fail closed when provenance, wetlab evidence, queue status, or delivery gates are incomplete.
5. Keep generated evidence reproducible, fingerprinted, and separated from source code.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run a focused delivery-gate test slice:

```bash
python3 -m pytest -q \
  tests/unit/test_build_local_delivery_verdict_gate.py \
  tests/unit/test_validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py \
  tests/unit/test_run_wetlab_tcruzi_pde_allatom_rescue.py
```

Run the local delivery verdict gate:

```bash
python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py
python3 tools/build_local_delivery_verdict_gate.py
```

The verdict gate is designed to fail closed until required P0 evidence, wetlab state, and delivery readiness conditions are satisfied.

## Main Workflows

| Workflow | Entry Points |
| --- | --- |
| Local delivery preflight | `tools/run_local_delivery_preflight.py`, `tools/build_local_delivery_bundle.py`, `tools/validate_local_delivery_bundle.py` |
| P0 delivery verdict | `tools/build_local_delivery_verdict_gate.py`, `docs/local_delivery_p0_gate.md`, `docs/local_delivery_verdict_template.md` |
| PDE rescue provenance | `tools/run_wetlab_tcruzi_pde_allatom_rescue.py`, `tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py` |
| Accuracy and regression gates | `tools/validate_accuracy_gate.py`, `tools/check_strict_release_regression.py`, `benchmark/accuracy_bench.py` |
| Nightly/local operations | `tools/run_nightly_screening_batch.py`, `tools/run_nightly_ops.sh` |
| Commercial readiness | `tools/build_commercialization_readiness_report.py`, `tools/build_ligand_scaleup_suite_status.py`, local-delivery docs, and generated verdict artifacts |

## Local Delivery Documentation

Start with these documents when reviewing delivery readiness:

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_manifest_template.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/local_delivery_verdict_template.md`
- `docs/local_delivery_engine_provenance.md`
- `docs/local_delivery_claim_policy.md`
- `docs/post_green_improvement_plan.md`

## Development Loop

```bash
git status
python3 -m pytest -q <relevant tests>
git add <changed source/docs/tests>
git commit -m "Describe the change"
git push
```

Before pushing, confirm that generated MD data, checkpoints, logs, and local delivery outputs are still ignored and not staged.

## Current Validation Snapshot

Updated 2026-05-13 KST.

- Restricted delivery verdict: `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, `verdict=delivery_ready`, `p0_blocker_count=0`, `hard_blocker_count=0`, `accuracy_gate_pass=true`, and `commercialization_queue_clear=true`.
- Claim scope remains restricted to `kinase,gpcr,ion_channel`; transporter, CA2/PXR, broader IDP promotion, broad platform readiness, and unattended decision-making remain outside the delivery claim.
- Ligand scale-up suite status is green for the tracked commercialization suite: `commercialization_ready_suite_count=3/3` and `pending_suite_ids=[]`.
- The 1M pilot package passes all three blind sets. Core full-task PR-AUC values are `gpcr_core_full=0.8958`, `ion_trpv1_chembl20_full=0.9585`, `kinase_core_full=1.0000`; expanded OOD PR-AUC values are `gpcr_chembl50_full=0.8093`, `ion_trpv1_chembl50_full=0.9867`, `kinase_strict_full=1.0000`.
- 1M guardrail interpretation is `claim_safe_size_shift_speed_diagnostic`: quality guardrails are claim-safe, while equal-size speedpack A/B owns the throughput claim and 1M speed is retained as diagnostic scale evidence.
- Latest focused validation slice covers commercialization status reporting, AQP1 negative evidence gap matrix/request packet, transporter external evidence crosscheck, transporter negative candidate harvest/curation queue, negative-evidence closure, platform gap taxonomy, local verdict, and ligand scale-up regression tests -> `110 passed`.

## Current Repository State

The pushed GitHub content includes the implementation, tests, configuration, and documentation needed to reproduce the local-delivery workflows. Runtime data remains local by design. If a partner or reviewer needs an evidence package, generate a local delivery bundle and share the resulting reviewed artifacts rather than committing raw trajectory or model output files.

Current delivery status is green for the restricted local-delivery scope: the verdict gate reports `summary.delivery_ready=true` and the commercialization queue is clear. Build the restricted local-delivery bundle and rerun `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` before sharing any delivery-ready package.

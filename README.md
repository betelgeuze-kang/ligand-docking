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

Updated 2026-05-15 KST.

![Actual MD Dynamics Viewer snapshot for T. cruzi PDE](docs/figures/webviewer_tcruzi_pde_actual_2026-05-15.png)

![Actual T. cruzi PDE 3V94 chain B molecular structure render](docs/figures/tcruzi_pde_3v94_chainB_structure_actual_2026-05-15.png)

The first image is an actual browser capture of `viewer/index.html` loaded with `surface-label=tcruzi_pde_allatom_review_packet`. The second image is a deterministic PyMOL render from the protein and trajectory files used in the local analysis: `runs/tcruzi_pde_strict_external_openmm/tcruzi_pde_3v94_chain_B.pdb` and `runs/tcruzi_pde_strict_external_openmm/tcruzi_pde_chain_B_openmm_ca_md.npy`. The tables below remain the source of truth for exact claim boundaries.

Runtime artifacts under `runs/` are local and intentionally ignored by Git. The table below names the local artifact to inspect, the current headline number, and the safe interpretation for GitHub readers.

| Lane | Current status | Key local artifact | Data to read first | Interpretation |
| --- | --- | --- | --- | --- |
| Restricted local delivery | Green | `runs/local_delivery_verdict_gate_current.json` | `delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0` | Delivery-ready only for the scoped local claim. |
| Delivery claim boundary | Restricted | `docs/local_delivery_claim_policy.md` | `kinase,gpcr,ion_channel` | Transporter, CA2/PXR, broader IDP, broad all-atom, broad platform, and unattended decision-making remain outside the claim. |
| Accuracy parity | Blocked | `runs/accuracy_parity_scorecard_current.json` | `status=blocked_accuracy_parity` | Commercial-tool parity is not claimed; API/productization remains secondary to A0/A1 scientific parity closure. |
| Family refresh reproducibility | Green | `runs/family_expansion_refresh_current.json` | `overall_ok=true`, `step_count=137`, `failed_count=0` | Current packet chain is reproducible locally. |
| Ligand scale-up suite | Green for tracked suite | `runs/ligand_scaleup_suite_status_current.json` | `commercialization_ready_suite_count=3`, `pending_suite_ids=[]` | Useful restricted-scale evidence, not broad commercial discovery parity. |
| T. cruzi PDE translation | Blocked | `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json` | `candidate_pool_row_count=29568`, `energy_pass=16`, `core_pass=0` | Wetlab/all-atom promotion is blocked. |
| T. cruzi PDE next blocker | Blocked | `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json` | `atomized_ligand_draft=7/7`, `parameterization=0/7`, `local_minimization=0/7` | Coordinate drafts exist; commercial pose/local-min evidence does not. |

## T. cruzi PDE Evidence Trail

The current PDE path is deliberately fail-closed. It separates candidate expansion, metric diagnosis, atomization, and commercial-promotion evidence so that strong-looking energy rows cannot be promoted without geometry, stability, atomization, parameterization, and local minimization support.

| Step | Local artifact | Current data | How to read it |
| --- | --- | --- | --- |
| Translation evidence scan | `runs/wetlab_tcruzi_pde_translation_evidence_probe_current.json` | `29568` candidate score rows, `16` energy-pass rows, `7` unique energy-hit ligands, `0` core-pass ligands | Energy evidence exists, but no row closes energy + distance + stability together. |
| Translation quality gate | `runs/wetlab_tcruzi_pde_translation_quality_packet_current.json` | `claim_promotion_allowed=false`, `candidate_pool_geometry_stability_blocked=true` | Broad wetlab/all-atom promotion remains blocked. |
| Metric-scale diagnosis | `runs/wetlab_tcruzi_pde_metric_scale_gap_packet_current.json` | selected pseudo-allatom review rows preserve geometry/stability `4/4` but energy `0/4`; external homolog/BindingDB rows provide energy `16` but geometry-stability/core `0` | The blocker is a metric-scale and pose-preservation split, not just a shortage of screened compounds. |
| Pose/backmapping closure queue | `runs/wetlab_tcruzi_pde_pose_backmapping_closure_queue_current.json` | `7` unique energy-hit PDE seeds queued | Next measurements are pose-preservation RMSD, backmapping consistency, local-minimization survival, and replicate-pass fraction. |
| Ligand atomization check | `runs/wetlab_tcruzi_pde_ligand_atomization_gap_packet_current.json` | `atomization_ready_count=0/7`; current pseudo-backmaps have `2` ligand atoms vs `34-43` expected heavy atoms | Existing pseudo-backmaps must not be treated as all-atom ligand pose evidence. |
| Atomized ligand draft | `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json` | RDKit all-atom drafts `7/7`; pseudo-anchor orientation `6/7`; parameterization `0/7`; protein-ligand local minimization `0/7` | Coordinate draft substep is done; parameterization and local minimization are the next commercial blockers. |

Fixed PDE hard thresholds remain:

| Metric | Pass threshold |
| --- | ---: |
| `binding_energy_proxy` | `<= -0.55` |
| `mean_min_distance_A` | `<= 3.10 A` |
| `stability_score` | `>= 0.32` |

## Reading Local Result Data

Use these commands locally after regenerating artifacts. They avoid dumping large trajectory payloads and focus on summary fields.

```bash
python3 - <<'PY'
import json
for path in [
    "runs/local_delivery_verdict_gate_current.json",
    "runs/accuracy_parity_scorecard_current.json",
    "runs/wetlab_tcruzi_pde_translation_quality_packet_current.json",
    "runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json",
]:
    data = json.load(open(path, encoding="utf-8"))
    print("\\n##", path)
    for key, value in (data.get("summary", {}) or {}).items():
        if key in {
            "status",
            "delivery_ready",
            "verdict",
            "candidate_pool_row_count",
            "candidate_pool_energy_pass_count",
            "candidate_pool_core_pass_count",
            "atomization_draft_ready_count",
            "parameterization_ready_count",
            "protein_local_minimization_ready_count",
            "claim_promotion_allowed",
            "next_required_step",
        }:
            print(f"{key}: {value}")
PY
```

## Claim Boundary

Acceptable current wording:

- Restricted local-delivery analysis pipeline with green gates on selected families.
- T. cruzi PDE has local evidence packets and RDKit atomized ligand drafts for review.
- T. cruzi PDE commercial wetlab/all-atom promotion is blocked pending parameterization, protein-ligand local minimization, pose preservation, backmapping consistency, and replicate evidence.

Not acceptable yet:

- Broad commercial drug-discovery platform parity.
- OpenMM/Schrodinger/GALAXY-class broad equivalence.
- Wetlab-proven T. cruzi PDE hit claim.
- Direct binding kcal claims from AQP1 functional surrogate rows.

## Current Repository State

The pushed GitHub content includes the implementation, tests, configuration, and documentation needed to reproduce the local-delivery workflows. Runtime data remains local by design. If a partner or reviewer needs an evidence package, generate a local delivery bundle and share the resulting reviewed artifacts rather than committing raw trajectory or model output files.

Current delivery status is green for the restricted local-delivery scope: the verdict gate reports `summary.delivery_ready=true` and the commercialization queue is clear. Build the restricted local-delivery bundle and rerun `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` before sharing any delivery-ready package.

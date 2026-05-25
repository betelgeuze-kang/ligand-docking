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

## CASP17 Internal Physics Lane

The repository now includes a CASP17 participation workstream that stays inside the local molecular-dynamics/coarse-grain physics stack. It does not use AlphaFold, ColabFold, ESMFold, OmegaFold, public/template structures, current-target native lookups, or other-team models for the active lane.

Current local status as of 2026-05-25 KST:

- 16/16 current selected CASP17 protein targets have local FASTA materialization and internal TS artifacts.
- The local submission floor is green: TS import, format, geometry, confidence, scorecard, shape sanity, and submission gate pass for the current selected target surface.
- Review-quality visual artifacts are green: local internal-canvas viewer smoke 16/16, PyMOL/studio/surface/confidence/QC render coverage 16/16, molecular showcase images 16/16, and image-quality smoke 272/272.
- The operational win-tier threshold packet now tracks 27 rows across submission, visual review, local all-atom/sidechain QC, no-leak historical monomer/complex native accuracy, refinement ablation, model selection, and confidence calibration.
- Highest proven local level remains `review_quality`. Competitive/win-tier readiness is intentionally fail-closed until no-leak historical/native benchmark rows, refinement-ablation evidence, and model-selection/confidence calibration are populated.

Primary current documents and artifacts:

- `docs/casp17_participation_gate_2026-05-21.md`
- `runs/casp17_readiness_dashboard_current.json`
- `runs/casp17_win_tier_threshold_packet_current.json`
- `runs/casp17_publication_figure_packet_current.json`

Generated CASP17 render/data mirrors under `runs/` and `casp17/` remain local artifacts and should not be committed as raw generated data.

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

Updated 2026-05-19 KST. Artifact snapshot: 2026-05-18 KST.

![Actual MD Dynamics Viewer snapshot for T. cruzi PDE](docs/figures/webviewer_tcruzi_pde_actual_2026-05-15.png)

![Actual T. cruzi PDE 3V94 chain B molecular structure render](docs/figures/tcruzi_pde_3v94_chainB_structure_actual_2026-05-15.png)

The first image is an actual browser capture of `viewer/index.html` loaded with `surface-label=tcruzi_pde_allatom_review_packet`, framed for README presentation. The second image is an AlphaFold-style deterministic PyMOL render from the protein and trajectory files used in the local analysis: `runs/tcruzi_pde_strict_external_openmm/tcruzi_pde_3v94_chain_B.pdb` and `runs/tcruzi_pde_strict_external_openmm/tcruzi_pde_chain_B_openmm_ca_md.npy`. The tables below remain the source of truth for exact claim boundaries.

After the local T. cruzi PDE OpenMM artifacts named in the manifest are present, regenerate both README figures with `python3 tools/render_readme_molecular_figures.py`. Use `--skip-browser` or `--skip-pymol` only when refreshing the manifest around already verified assets. The current manifest is written to `docs/figures/readme_molecular_figures_manifest_current.json`.

Runtime artifacts under `runs/` are local and intentionally ignored by Git. The table below names the local artifact to inspect, the current headline number, and the safe interpretation for GitHub readers.

| Lane | Current status | Key local artifact | Data to read first | Interpretation |
| --- | --- | --- | --- | --- |
| Restricted local delivery | Green | `runs/local_delivery_verdict_gate_current.json` | `delivery_ready=true`, `verdict=delivery_ready`, `p0_blocker_count=0` | Queue and verdict are synchronized green for the restricted local scope. |
| Commercialization gap/readiness accounting | Closed for tracked local scope | `runs/commercialization_readiness_current.json`, `runs/commercialization_gap_burndown_current.json` | `tracked_readiness_accounting_closed=true`, `tracked_gap_accounting_closed=true`, `blocked_count=0`, `parked_or_review_only_blocked_count=2` | Active tracked blockers are zero; two legacy blocked-bucket rows remain parked/review-only audit entries, not delivery blockers. |
| Delivery claim boundary | Restricted | `docs/local_delivery_claim_policy.md` | `kinase,gpcr,ion_channel` | Transporter, CA2/PXR, broader IDP, broad all-atom, broad platform, and unattended decision-making remain outside the claim. |
| Accuracy parity | Green for tracked axes | `runs/accuracy_parity_scorecard_current.json` | `status=green`, `pass=5`, `blocked=0` | GPCR ranking, pose geometry, OpenMM, structure, and wetlab translation now pass the tracked scorecard gate. Router/platform deployment claims remain separate. |
| Family refresh reproducibility | Green | `runs/family_expansion_refresh_current.json` | `overall_ok=true`, `step_count=137`, `failed_count=0` | Current packet chain is reproducible locally. |
| Ligand scale-up suite | Green for tracked suite | `runs/ligand_scaleup_suite_status_current.json` | `commercialization_ready_suite_count=3`, `pending_suite_ids=[]` | Useful restricted-scale evidence, not broad commercial discovery parity. |
| T. cruzi PDE selected all-atom | Green | `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` | `hard_block_count=0`, `selected_allatom=pass` | The atomized local-min overlay closed the six selected all-atom hard blocks. |
| PDE atomized ligand local-min | Green | `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json` | `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, `validated_repair_count=7` | All 7 atomized ligands have parameterization plus protein-ligand local minimization evidence. |
| OpenMM/structure parity evidence | Green | `runs/openmm_2bead_strict_multitarget_current_summary.json`, `runs/structure_refinement_scorecard_current.json` | OpenMM targets `11`, structure true-metric backend `internal_deterministic_ca_true_metrics` | Both axes pass the current scorecard. |
| GPCR A1 independent repeat | Green for tracked ranking evidence | `runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json` | PR-AUC `0.8719`, PR CI-low `0.7612`, top20 `1.00`, blockers `[]` | The 2026-05-18 independent repeat plus out-of-fold crossfit replay passes the ranking gate. Scorer deployment/router promotion remains a separate locked claim. |

## T. cruzi PDE Evidence Trail

The current PDE selected all-atom path has no remaining hard block, and the tracked accuracy scorecard is green. Broad wetlab/platform claims still stay separate until prospective wetlab evidence and broader platform guardrails are available. Candidate expansion, metric diagnosis, atomization, parameterization, and local minimization evidence remain separated so no single strong-looking energy row can be over-promoted.

| Step | Local artifact | Current data | How to read it |
| --- | --- | --- | --- |
| Translation evidence scan | `runs/wetlab_tcruzi_pde_translation_evidence_probe_current.json` | `29568` candidate score rows, `16` energy-pass rows, `7` unique energy-hit ligands, `0` core-pass ligands | The original energy/geometry split remains recorded as source evidence. |
| Atomized ligand draft | `runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.json` | RDKit all-atom drafts `7/7`; pseudo-anchor orientation `6/7` | Coordinate draft substep is complete. |
| Parameterization/local minimization | `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json` | `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, `validated_repair_count=7`, `hard_block_count=0` | All 7 ligands now have parameterization and protein-ligand local minimization evidence. |
| All-atom review overlay | `runs/wetlab_tcruzi_pde_allatom_review_packet_current.json` | `translation_gate_focus_status=pass`, `focus_shortlist_tier=tier2_silver`, `recommended_next_expensive_lane=atomized_openmm_local_min_validated_repair` | Validated atomized rows feed the all-atom review overlay. |
| Selected all-atom burndown | `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` | `commercial_hard_gate_pass_v2=true`, `hard_block_count=0` | The previous six hard blocks are closed. |

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
    "runs/commercialization_readiness_current.json",
    "runs/commercialization_gap_burndown_current.json",
    "runs/accuracy_parity_scorecard_current.json",
    "runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json",
    "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
    "runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json",
]:
    data = json.load(open(path, encoding="utf-8"))
    print("\\n##", path)
    for key, value in (data.get("summary", {}) or {}).items():
        if key in {
            "status",
            "delivery_ready",
            "verdict",
            "parameterization_ready_count",
            "protein_local_minimization_ready_count",
            "validated_repair_count",
            "hard_block_count",
            "tracked_readiness_accounting_closed",
            "tracked_gap_accounting_closed",
            "raw_blocked_bucket_count",
            "parked_or_review_only_blocked_count",
            "ranking_pr_auc",
            "ranking_pr_auc_ci_low",
            "ranking_topk_hit_rate",
            "blockers",
            "claim_promotion_allowed",
            "next_required_step",
        }:
            print(f"{key}: {value}")
PY
```

## Claim Boundary

Acceptable current wording:

- The restricted local-delivery verdict and local engine queue are synchronized green for the current local scope.
- T. cruzi PDE has 7/7 atomized ligand parameterization and protein-ligand local minimization evidence.
- T. cruzi PDE selected all-atom gate is closed with zero hard blocks.
- OpenMM 11-target and structure deterministic true-metric scorecards are current green evidence.
- GPCR A1 tracked ranking evidence is green on the 2026-05-18 independent repeat plus out-of-fold crossfit replay: PR-AUC `0.8719`, CI-low `0.7612`, top20 `1.00`.
- The tracked commercial-tool accuracy parity scorecard is currently `status=green`, `pass=5/5`.

Not acceptable yet:

- Unbounded broad commercial drug-discovery platform deployment claims.
- Automatic scorer/router/platform promotion claims.
- Wetlab-proven T. cruzi PDE hit claim.
- Direct binding kcal claims from AQP1 functional surrogate rows.

## Current Repository State

The pushed GitHub content includes the implementation, tests, configuration, and documentation needed to reproduce the local-delivery workflows. Runtime data remains local by design. If a partner or reviewer needs an evidence package, generate a local delivery bundle and share the resulting reviewed artifacts rather than committing raw trajectory or model output files.

Current delivery status is green for the restricted local-delivery scope. The verdict gate reports `delivery_ready=true`, `verdict=delivery_ready`, and `p0_blocker_count=0`, and it agrees with the commercialization queue. Before sharing a delivery-ready package, rebuild the restricted local-delivery bundle and rerun `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` to verify the bundle fingerprint.

# Local Delivery Engine Provenance

## Purpose

Local delivery is a provenance and control layer around the existing in-repo ligand HTVS engine. It records what ran, with which frozen inputs, on which machine, and how to rerun it. It does not introduce a new engine.
It is necessary for reproducibility, but it is not enough by itself to justify any score-uplift or architecture-accuracy claim.

## Existing Engine Surfaces

The engine already lives in the repo at:

- `tools/run_ligand_htvs_pipeline.py` - top-level HTVS orchestration, locks, stage summaries, smoke/full execution, and closeout writes.
- `tools/generate_ligand_trajectory_engine.py` - trajectory generation and rollout runner built on the core MD engine.
- `core/integrator.py` - Langevin integration and timestep control.
- `core/forcefield.py` - force calculation, neighbor-list handling, and Rust HIP / PyTorch fallback.
- `core/topology.py` - topology and bead-layout helpers.
- `rust_engine/src/lib.rs` - Rust HIP bridge for nonbonded kernels, neighbor-list kernels, and direct ligand rollout.
- `config/ligand_htvs_*.json` - scope-specific profiles, presets, and delivery configs.
- `runs/ligand_htvs_*` artifacts - lock files, summaries, status reports, smoke outputs, and stage-specific run records.

## What The Local-Delivery Layer Adds

The local-delivery layer does not replace the engine. It adds the wrapper records needed for a guarded handoff:

- engine provenance
- dependency lock
- environment manifest
- queue and report refresh
- delivery bundle and checksums

Expected provenance artifacts for that layer are:

- `runs/local_delivery_engine_provenance_current.json`
- `runs/local_delivery_engine_provenance_current.md`

The bundle builder copies the same record to:

- `environment/engine_provenance.json`
- `environment/engine_provenance.md`

## What The Provenance Record Should Capture

Keep the record short and operator-friendly. It should name:

- the source repo commit and workspace state
- the exact engine entrypoint or profile used
- the config file or config set
- the runtime backend used by the engine path
- the dependency lock and environment manifest that accompanied the run
- the queue and report artifacts produced from the run
- the exact rerun command or bundle command
- the checksumed bundle paths, if a bundle was assembled

## Guardrails

- Do not describe this as a new molecular engine.
- Do not imply broad SaaS or hosted production readiness.
- Do not claim unattended decision-making.
- Do not widen scope beyond `kinase`, `ion_channel`, and `gpcr`.
- Do not use provenance alone as evidence for a family score uplift.
- Pair any family-specific scoring claim with the held-out family scorecard, hard-decoy stability, calibration, and geometry/contact gate described in `docs/family_scorecard_calibration_plan.md`.
- Keep transporter wording review-only, staged, or not yet claim-safe until evidence closure is real.

See also `docs/local_delivery_runbook.md`, `docs/family_scorecard_calibration_plan.md`, `docs/local_delivery_bundle_schema.md`, `docs/local_delivery_manifest_template.md`, `docs/local_delivery_dependency_freeze.md`, and `docs/local_delivery_environment_baseline.md`.

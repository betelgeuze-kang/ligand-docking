# TASK — PoseBusters internal diagnostic ranking evaluation

## Goal

Measure one frozen, uncalibrated internal four-term diagnostic score on the
existing failure-inclusive PoseBusters `split_role=test` pose pools without
using test labels for fitting or score-policy selection.

## Scope

- Add a reusable CPU `float64` scorer with explicit UFF cross-vdW, PDBQT
  partial-charge Coulomb, RDKit UFF source-atom strain, and overlap terms.
- Bind the exact preparation, generated-pose, scaffold-identity, test
  partition, source, runtime, and dependency identities.
- Retain all 308 cases, every upstream/scorer failure, term decompositions,
  all-case and target-family metrics, confidence intervals, and claim
  blockers.
- Materialize and exactly verify one private production receipt.
- Do not fit, calibrate, promote a force-field/docking claim, or change the
  existing reference-force-field scorer contract.

## Likely files

- `betelgeuze_engine_v2/docking/pdbqt_uff_diagnostic_scoring.py`
- `betelgeuze_engine_v2/benchmark/public_posebusters_internal_diagnostic_ranking_evaluation.py`
- package exports, CLI/CI wiring, roadmap/status docs, and focused tests

## Verification

- Focused scorer and benchmark contract tests
- Exact production receipt reconstruction
- Focused Engine v2 regressions, formatting/lint/compile/package guards
- `./scripts/ai-verify.sh` when available

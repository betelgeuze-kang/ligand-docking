# TASK — Public pose-ranking calibration training view

## Goal

Derive a fit-safe success-only training view from an admitted,
failure-inclusive PDBbind fit partition without losing any excluded-row
evidence or opening validation/test leakage.

## Scope

- Require a passing public calibration-partition intake receipt.
- Include every successful fit row unchanged and exclude only explicit failure
  rows under one frozen status-only rule.
- Retain one canonical disposition for every source row and bind source/view
  payload, identity, case, row, label, and failure denominators.
- Recompute training-view↔CASF-validation pose-level leakage.
- Embed the exact training partition in a mode-0600 no-overwrite receipt and
  provide a guarded bridge to deterministic fit-only calibration.
- Add CLI, exports, package/CI wiring, docs, and focused tests.

## Non-goals

- Do not use validation labels for selection or fitting.
- Do not accept a test partition, tune hyperparameters, execute a benchmark,
  promote a scorer, or fabricate production data/receipts.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_pose_ranking_calibration_training_view.py`
- benchmark exports, package CLI/CI, evidence docs, focused tests

## Verification

- Exact row-accounting, omission/tamper, leakage, fit-bridge, and write tests
- Focused calibration/provenance/package regressions and deterministic wheel

## Risk Level

R2

# TASK — Public pose-ranking calibration partition intake

## Goal

Exact-bind caller-provided PDBbind fit and CASF validation score partitions to
a passing three-way public corpus intake before any fitting or test access.

## Scope

- Securely parse canonical, failure-inclusive `PoseRankingCalibrationPartition`
  files for only the frozen fit and validation roles.
- Require a verified, passing public corpus receipt and exact fit/validation
  manifest identities.
- Recompute public-manifest bindings and pose-level fit/validation leakage.
- Retain term schemas, case/row/label/failure denominators, trainability
  dispositions, file identities, and a mode-0600 no-overwrite receipt.
- Add materialize/verify CLI, exports, package/CI wiring, docs, and tests.

## Non-goals

- Do not download or fabricate PDBbind/CASF data, scores, labels, or receipts.
- Do not fit weights, use validation labels for fitting, read test labels,
  execute PoseBusters evaluation, or promote a science/product claim.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_pose_ranking_calibration_partition_intake.py`
- benchmark exports, package CLI/CI, evidence docs, focused tests

## Verification

- Canonical-reader, role/label, binding, leakage, tamper, and no-overwrite tests
- Focused calibration/provenance/package regressions, Ruff, compile, YAML
- Deterministic wheel and outside-checkout CLI verification

## Risk Level

R2

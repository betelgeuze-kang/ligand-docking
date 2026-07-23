# TASK — Public pose-ranking corpus intake

## Goal

Create an installable, claim-closed intake that exact-binds caller-provided
PDBbind-v2020 fit, CASF-2016 validation, and PoseBusters-308 test manifests
before any scorer fitting or test-label access.

## Scope

- Securely parse canonical split-manifest and three pairwise sequence-identity
  receipt files.
- Freeze dataset roles, protocol/preparation identity, sequence-similarity,
  temporal, receptor, ligand, scaffold, and target-sequence leakage policies.
- Recompute fit→validation and fit→test audits and independently audit
  validation↔test exact overlaps.
- Retain all readiness blockers, counts, input/file identities, and a canonical
  mode-0600 no-overwrite receipt.
- Add materialize/verify CLI, exports, package/CI wiring, docs, and tests.

## Non-goals

- Do not download, bundle, fabricate, or accept PDBbind/CASF data or terms.
- Do not generate calibration partitions, fit weights, consume test labels,
  execute a benchmark, or open a science/product claim.

## Likely files

- `betelgeuze_engine_v2/benchmark/public_pose_ranking_corpus_intake.py`
- benchmark exports, package CLI/CI, status/API/roadmap docs, focused tests

## Verification

- Secure-reader, role, overlap, temporal, sequence, tamper, and no-overwrite tests
- Focused provenance/package regressions, Ruff, compile, YAML, architecture
- Deterministic wheel and outside-checkout CLI verification

## Risk Level

R2

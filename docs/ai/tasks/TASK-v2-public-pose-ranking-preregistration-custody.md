# TASK — Public pose-ranking preregistration custody

## Goal

Require independently signed candidate-manifest registration and a later,
separately signed CASF validation release before the installable fit/validation
workflow can execute.

## Scope

- Bind the exact candidate manifest, training-view receipt commitment,
  PDBbind training identity, CASF partition/file commitments, leakage audit,
  selection policy, and fit/validation source identity before release.
- Keep registration output label-blind: expose validation commitments, not
  validation rows, labels, class counts, or metrics.
- Require an Ed25519 registrar signature from an identity distinct from the
  training operator, evaluation operator, and validation custodian.
- Require a later Ed25519 release signature from the preregistered validation
  custodian, with distinct nonce and exact file/payload commitments.
- Verify out-of-band public-key anchors, validity windows, role separation,
  revocation, supersession, canonical bytes, and secret-free signing requests.
- Derive a mode-0600 no-overwrite execution-admission receipt and require it in
  the installable fit/validation materialize/verify path.
- Retain all test, independent rerun/review, chemistry, scientific-validation,
  product, and confidence-calibration claim blockers.

## Non-goals

- Do not accept private keys in any CLI, request, receipt, config, or state.
- Do not embed or fabricate PDBbind/CASF rows, labels, credentials, licenses,
  signatures, trust anchors, production receipts, or timestamps.
- Do not treat a signature as proof of dataset quality, reviewer independence
  beyond the declared identities, test performance, or scientific validity.

## Likely Files

- `betelgeuze_engine_v2/benchmark/public_pose_ranking_fit_validation_custody.py`
- `betelgeuze_engine_v2/benchmark/public_pose_ranking_fit_validation_selection.py`
- benchmark exports, package CLI/CI, focused tests, and evidence docs

## Verification

- Exact registration/release/admission reconstruction and role/time ordering.
- Detached-signature, trust-anchor, revocation, supersession, cross-wire,
  nonce-reuse, private-material, label-field, canonical-file, and tamper tests.
- Fit/validation file execution rejected without current valid custody.
- No PoseBusters test score partition accepted.
- Focused calibration/custody/package tests, Ruff, architecture, deterministic
  wheel, and installed-CLI checks.

## Risk Level

R3

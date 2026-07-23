# TASK — PoseBusters external-engine ranking evaluation

## Goal

Turn the frozen Vina/GNINA/Smina PoseBusters test partitions into an actual,
failure-inclusive external-reference ranking result without fitting or tuning a
score on test labels.

## Scope

- Bind the exact 308-case, three-engine test-partition receipt.
- Freeze each engine's pre-existing source sort policy: Vina total energy,
  GNINA CNN pose score, and Smina minimized affinity.
- Require the frozen policy to reproduce the source pose ordering before
  evaluating labels.
- Report all-case and scored-case Top-1/Top-5, execution coverage, source-bound
  physical-validity metrics, pose-level average-precision PR-AUC, and
  deterministic case-cluster intervals.
- Report observed-sequence proxy, exact Pfam-set, and multi-label Pfam metrics
  with explicit missing-annotation buckets and denominators.
- Preserve every failed case and all claim/leakage/reproduction blockers.
- Materialize and exactly verify one canonical production receipt.

## Non-goals

- Do not fit, calibrate, or select a score policy using PoseBusters labels.
- Do not treat external-engine results as validation of the internal scorer.
- Do not hide the 290/291 failed-case rows behind scored-case metrics.
- Do not claim complete family coverage, independent rerun, scientific review,
  or product qualification.

## Verification

- Focused tests for score direction, tie handling, all-case denominators,
  PR-AUC bootstrap, family scopes, failure preservation, exact verification,
  and policy/source-order mismatch.
- Production receipt reconstruction, focused regression, architecture,
  deterministic wheel, and installed-wheel verification.

## Risk Level

R2

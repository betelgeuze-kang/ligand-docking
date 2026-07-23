# TASK — PoseBusters failure-inclusive ranking test partitions

## Goal

Materialize exact, engine-specific `split_role=test` calibration partitions for
the frozen 308-case PoseBusters Vina, GNINA, and Smina evidence without fitting
or using test labels for training.

## Scope

- Bind the pose-ranking intake, pose/scaffold identity, observed-sequence
  cluster, and RCSB/Pfam receipts by exact receipt and file identities.
- Retain every successful pose and one explicit failure row for every
  non-evaluated case.
- Use observed-sequence clusters only as complete leakage-control proxy strata;
  retain incomplete Pfam annotations as a separate biological annotation.
- Validate all-case, proxy-cluster, and Pfam metric denominators and confidence
  intervals while retaining their exact source roots.
- Add canonical materialize/verify APIs, CLI packaging, tests, and bounded
  documentation.

## Non-goals

- Do not fit or promote a calibrated scorer.
- Do not represent observed-sequence clusters as biological target families.
- Do not claim fit-to-test leakage control, independent rerun, scientific
  validation, or public benchmark readiness.

## Verification

- Focused unit tests for exact binding, failure identity semantics, all-case
  coverage, metric validation, secure receipt handling, and tamper rejection.
- Engine v2 architecture guard, focused Ruff, package/release tests, canonical
  production receipt verification, and deterministic wheel byte equality.

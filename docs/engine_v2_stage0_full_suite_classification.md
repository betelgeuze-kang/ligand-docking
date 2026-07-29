# Engine V2 Stage 0 full-suite classification

## Reproduction snapshot

The PR #211 worktree full suite was reproduced locally on 2026-07-29 without
executing the 298-case holdout:

```text
6574 passed
215 failed
3 errors
10 skipped
2 xfailed
```

The exact PR #211 review head (`3935a1fa`) was also reproduced in a detached
worktree: `6570 passed`, `215 failed`, `3 errors`, `10 skipped`, `2 xfailed`.
Its 218 nonpassing row multiset is identical to the current reproduction. Both
runs differ from the PR description (`6564 passed`, `216 failed`, `3 errors`).
No JUnit evidence for the declared 216th failure is available, so it must not
be invented, silently classified, or treated as authoritative.

Local receipts are retained under `.betelgeuze/stage0/`:

- JUnit SHA-256:
  `4e5518a33b619fe1c1589b18ca46af6eab07d35e16b44071736c2b5f736c8741`
- row-level classification receipt content SHA-256:
  `d283ed6f11ca1d9b768fa3e586ee693f14aaf401df316a308513811465de2371`
- classification self-receipt SHA-256:
  `a32afb2ea6e6689b50e66e5d450595c646d4f7b91c3b43bd7bb2580c74441704`
- exact-head JUnit SHA-256:
  `d18969c593978fa8fb8f89a2faab56026b27ddcd1ba97993003bd98334841d87`
- exact-head classification file SHA-256:
  `5d62fbea3841bf20550c626c6dd50ac43375dea7069c514a6338f77bc1a27ea1`
- reconciliation receipt file SHA-256:
  `90597c411ea567d76cb1ccba99d031f661e8ec3dbf15453d3b32c35f10b8b58f`
- reconciliation self-receipt SHA-256:
  `eef6c8008ade41bfaf0d271f9da9c2598cac370d6d1849544a987c8a7e337eca`

The reconciliation receipt records `unresolved_declared_failure_count: 1`,
`declared_aggregate_reproduced: false`, and equal historical/current row
multisets. Stage 0 requires an independent reviewer to accept the disposition
`declared_pr_aggregate_unreproducible_and_non_authoritative`; until then this is
a blocker, not a count correction.

## Provisional deterministic classification

| Category | Outcomes | Interpretation |
| --- | ---: | --- |
| `actual_regression` | 49 | Assertion or contract failures requiring an owner decision; never silently accepted. |
| `fixture_dependent` | 10 | Repository fixture or upstream artifact missing outside a product-specific lane. |
| `host_capability_missing` | 12 | Seven inotify-watch failures plus five unavailable Rust HIP backend outcomes. |
| `local_evidence_required` | 11 | Ten native-structure validation fixtures plus one local CASP sequence fixture. |
| `legacy_deterministic` | 10 | Four known legacy contract families whose assertions differ from current behavior. |
| `product_fixture_dependent` | 126 | Product, wet-lab, transporter, or evidence-chain tests coupled to mutable `runs/` artifacts. |

All 218 nonpassing outcomes have a row with class, test name, outcome kind,
classification rule, and failure-message SHA-256. Raw failure text is not copied
into the classification receipt.

This automatic classification and count reconciliation are not final
acceptance. In particular, the 49
conservative `actual_regression` rows need owner review, and the official
Engine-required, legacy-deterministic, product-fixture, and local-evidence suite
boundaries must be frozen before Stage 0 can pass. The recommended boundary is
`official_tiered_suites`; broad pytest is not currently green.

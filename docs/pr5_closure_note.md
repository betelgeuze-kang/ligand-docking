# PR #5 Closure Rationale

PR #5 ("[codex] Secure customer docking inputs and production dispatch") contained
three sections of work. All three have been fully or partially superseded by
subsequent merged PRs (#7 through #12). This document records which sections
landed, which remain deferred, and why.

---

## Section 1: Encrypted Private Payload Store -- FULLY SUPERSEDED

- **PR #7** landed the stdlib-only encrypted private payload at-rest store and
  fixed the dispatcher outbox event.
- **PR #11** completed the end-to-end wiring of the encrypted payload store into
  the submit and materialization paths.

Together these two PRs deliver the full scope of Section 1. No further work is
needed here.

## Section 2: Restricted-Production HTVS Profile -- DEFERRED

This section introduces a restricted-production High-Throughput Virtual Screening
(HTVS) profile that requires a self-hosted ROCm GPU runner for validation. It
cannot be landed from the web-based CI environment because:

- Runtime GPU evidence is needed to confirm correct device dispatch.
- The self-hosted ROCm runner is not yet available in CI.

A future PR will address this once GPU evidence can be produced on the appropriate
hardware.

## Section 3: Transactional Dispatch + Atomic Persistence -- PARTIALLY SUPERSEDED / DEFERRED

- The **outbox event fix** portion of this section landed in **PR #7**.
- The broader transactional rework (atomic persistence guarantees beyond the
  outbox) requires runtime evidence that is not reproducible in the current CI
  environment and is deferred alongside Section 2.

---

## Summary

| Section | Status | Landed In |
|---------|--------|-----------|
| 1 - Encrypted payload store | Fully superseded | PR #7, PR #11 |
| 2 - HTVS production profile | Deferred (needs GPU runner) | -- |
| 3 - Transactional dispatch | Partially superseded / deferred | PR #7 (outbox fix) |

PR #5 should be closed once this document merges, as all actionable items have
either landed or been explicitly deferred with rationale.

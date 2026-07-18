# TASK-ID: v2-minimization-validation-coordinate-trace

## Goal

Bind complete ordered binary64 coordinate traces for every evaluated 14-case minimization step into the canonical result receipt and independent result-review dispositions.

## Scope

- Retain exact raw and evaluated/projected coordinates for every operational and independent-oracle evaluation, including rejected and fail-closed rows.
- Normalize each trace with exact source, length, contiguous evaluation/iteration/trial identity, per-step identity digest, and whole-trace canonical SHA-256.
- Carry the traces through runner observation and result receipt validation without permitting omission, reordering, cross-wiring, non-finite values, digest drift, or count/energy-ledger disagreement.
- Add ordered per-trace and per-step review dispositions derived from the exact receipt; caller-supplied contradictory dispositions must fail closed.
- Update frozen minimization evidence contracts, capability/docs/CI state, while retaining production, two-host, external-implementation, scientific, fitting, and product gates as closed.

## Likely Files

- `betelgeuze_engine_v2/physics/reference_minimization.py`
- `betelgeuze_engine_v2/physics/reference_constrained_minimization.py`
- `betelgeuze_engine_v2/physics/reference_minimization_independent_oracle.py`
- minimization validation protocol/artifact/receipt/runner/writer/result-review modules
- focused minimization, runner, writer, result-review, capability, and post-merge tests
- Engine v2 status, public API, capability, roadmap, changelog, and CI workflow records

## Verification

- Focused core minimization/oracle and complete minimization-validation contract-chain tests.
- Explicit valid trace, missing step, reordered step, coordinate tamper, step-identity tamper, trace-digest tamper, source cross-wire, count mismatch, energy-ledger mismatch, and review-disposition contradiction tests.
- Ruff, YAML/capability snapshot checks, `git diff --check`, and `./scripts/ai-verify.sh` when present.

## Non-goals

- Do not fabricate or claim a production run, second CPU host, external implementation result, independent human approval, S1 applicability, fitting authorization, or product/scientific promotion.

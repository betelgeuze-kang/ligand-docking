# TASK-ID: v2-minimization-validation-result-review

## Goal

Freeze and implement a fail-closed Ed25519 independent result-review attestation contract for the 14-case minimization validation receipt.

## Scope

- Add a provisional `reference_minimization_validation_result_review` module.
- Bind the exact result receipt/hash, protocol, runner/writer contracts, source/dependency/environment identities, all 14 case outcomes, every retained metric, exact runtime/oracle/result hashes, per-case count budgets, metric-consistent energy-ledger evidence, and review dispositions.
- Require raw signed pre-execution review and authorization artifacts, reverify their Ed25519 trust chains, and derive the implementation-author, scientific-reviewer, and authorization-operator roles before enforcing four-way separation from the result reviewer.
- Verify canonical JSON byte transport, signature, trusted key/identity, external expected receipt hash, required current revocation/supersession inputs including result-review supersession, complete ordered review checks, failure dispositions, and claim limitations.
- Export the provisional symbols and wire focused CI/capability/docs state.
- Keep `independent_result_review_missing` until a real production receipt and externally signed review exist.

## Non-goals

- No production execution, key, trust store, receipt, reviewer approval, two-host evidence, parameter applicability, S1-S4 work, fitting authorization, or scientific/product claim.
- No result receipt schema rewrite, persistence/delete/release API, CLI, external fetch, or external solver run.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/physics/reference_minimization_validation_result_review.py`
- minimization review/authorization/result-writer modules and `physics/__init__.py`
- capabilities YAML/Python, Engine v2 status/public API, focused CI workflows
- `tests/unit/test_engine_v2_reference_minimization_validation_result_review.py`

## Verification

- Focused result-review, writer, review, authorization, capability, packaging, and post-merge tests.
- `git diff --check` and `./scripts/ai-verify.sh` when available.

## Stop Conditions

- Stop if the slice requires fabricating a production artifact/reviewer decision, weakening frozen identity checks, or changing S0 metric thresholds.
- Follow `AGENTS.md`; do not read `.env` files or mutate external state.

## Risk Level

R3

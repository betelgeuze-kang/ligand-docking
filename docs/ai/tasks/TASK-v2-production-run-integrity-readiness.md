# TASK-ID: v2-production-run-integrity-readiness

## Goal

Make both synthetic validation entrypoints capable of issuing truthful, reproducible production-class receipts without weakening the pre-import trust boundary.

## Scope

- Replace the false `-I` plus `PYTHONHASHSEED` evidence with a source-bound, controlled re-exec boundary that proves the actual interpreter hash seed while retaining stdlib-only startup, no site/PYTHONPATH injection, exact argv, and source-only imports.
- Add 27/59 dependency executable/distribution/stdlib byte observation and revalidation at bootstrap, parent, and fixed worker boundaries, matching or exceeding the 14-case chain.
- Make the 27/59 root-owned checkout declaration match enforced owner/mode/path policy.
- Add a signed evidence class and custody identity across review, authorization, environment, observation, result, and response schemas so test-only artifacts remain closed while a fully verified production run records `production_validation_results_collected=true` without opening scientific/fitting/product claims.
- Remove unconditional test-only/production-missing blockers only when the production evidence class and complete external chain verify.
- Add the missing 27/59 independent post-result review with full case/variant/metric/failure dispositions and role-separated signature verification.

## Non-goals

- No keys, trust stores, dependency installation, production execution, second-host/external result, S0 acceptance, S1 work, fitting, or product/scientific promotion.

## Likely Files Or Search Targets

- Both validation bootstrap, dependency identity, authorization, receipt, run-start, runner, writer, and result-review chains
- New 27/59 result-review module, focused tests, capability/status/roadmap/CI records

## Verification

- Repeated fresh-process hash determinism, environment/path injection, direct-stage bypass, source/dependency/checkout cross-wire, evidence-class downgrade, test/production confusion, metric/failure omission, signature/role/revocation/supersession tests.
- Both complete validation chains, Ruff, capability/YAML equality, architecture guard, and `git diff --check`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop before setting any scientific, fitting, S0/S1, or product claim from receipt collection alone.

## Risk Level

R4

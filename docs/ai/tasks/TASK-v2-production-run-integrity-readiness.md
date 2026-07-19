# TASK-ID: v2-production-run-integrity-readiness

## Goal

Make both synthetic validation entrypoints capable of issuing truthful, reproducible production-class receipts without weakening the pre-import trust boundary.

## Scope

- Replace the false `-I` plus `PYTHONHASHSEED` evidence with a source-bound, controlled re-exec boundary that proves the actual interpreter hash seed while retaining stdlib-only startup, no site/PYTHONPATH injection, exact argv, and source-only imports.
- Add 27/59 dependency executable/distribution/stdlib byte observation and revalidation at bootstrap, parent, and fixed worker boundaries, matching or exceeding the 14-case chain.
- Bind a durable per-file dependency manifest plus the actually mapped native DSO closure, reject unrecorded importable payloads, and retain worker pre/post identity evidence.
- Put dependency/source preflight under one carried cooperative deadline before any nonce or runner-start marker is consumed, then close directory/RECORD traversal gaps before describing it as a hard end-to-end wall bound.
- Make the 27/59 checkout declaration truthful, then require an externally provisioned root-owned read-only source snapshot before any production-class execution.
- Add a signed evidence class and custody identity across review, authorization, environment, observation, result, and response schemas so test-only artifacts remain closed while a fully verified production run records `production_validation_results_collected=true` without opening scientific/fitting/product claims.
- Remove unconditional test-only/production-missing blockers only when the production evidence class and complete external chain verify.
- Add the missing 27/59 independent post-result review with full case/variant/metric/failure dispositions and role-separated signature verification.

## Current Progress

- Both stdlib-only bootstraps now fail closed on root execution and unless the complete Engine v2 package tree is under a canonical root-owned, group/other-nonwritable, symlink-free source snapshot; user-owned files, hardlinks, and bytecode caches are rejected before package import. They independently rehash the signed raw Git commit and recursive tree objects with Git SHA-1 object framing, then compare the exact tracked `betelgeuze_engine_v2` path set and every regular file's mode, blob OID, SHA-256, and size with the live root-owned read-only tree. The canonical source manifest is passed as the sixth bootstrap-state element.
- Source and dependency preflight now carry monotonic deadlines and aggregate entry/file/byte budgets. Directory walks use bounded `scandir`, wheel `RECORD` rows are streamed directly, and payloads are size-capped before reads; normalized install-scheme confinement, active-import/RECORD binding, namespace closure, and bytecode rejection remain enforced. These are bounded preflight traversals, not kernel-enforced end-to-end lifetime isolation.
- Both lanes now generate canonical full per-file source and dependency manifests while preserving the signed commit and six aggregate dependency digests. Run-start persists `<nonce>.source-tree.json` and `<nonce>.dependencies.json` with mode 0600, `O_EXCL`, `O_NOFOLLOW`, and file/directory fsync. Runner and result finalization require exact persisted/live equality and bind the source-manifest digest through environment, runner-start, observation, and result identities; minimization result-review validation and its Ed25519 signature also bind that digest.
- The active energy-force base chain uses v2 identities with a v3 runner/result writer. The minimization base chain uses v3 identities with a v5 runner and v4 result writer/result review. Current hashes are recomputed through their upstream dependency DAG. A read-only registry verifies 23 superseded contract documents by canonical projection hash. It intentionally does not claim compatibility with superseded signed attestations, receipts, or run records.
- Both fixed workers now emit exact request-bound `pre -> payload -> post/completion` lifecycle evidence. The supervisor retains all 27/59 or 14 rows only after exact frame/order/aggregate validation, binds both native snapshots to the actual child PID, and streams stdout under a hard byte cap with process-group termination and reap. `/proc/self/maps` is fixed to the calling PID view; anonymous, deleted, memfd, writable-executable, duplicate-special, and untrusted file-backed executable mappings fail closed.
- `validation_runtime_integrity_contract.py` records those implemented controls while explicitly keeping kernel vDSO content identity, procfs superblock authentication, authorized native allowlisting, execution-lifetime closure, and persisted observation-to-request identity binding false.
- Still open: externally provisioned root-owned source/dependency runtime, kernel-backed source/Git-metadata immutability and custody, pre-bootstrap stdlib closure, signed native allowlisting and full load/execute/unload lifetime closure, vDSO/kernel identity, observation-to-worker-request identity binding, signed evidence class/custody, the energy-force Ed25519/post-result-review chain, actual 27/59 and 14-case production runs, two-host reproduction, trajectory/external comparison, and human independent-review approval. All production, scientific, fitting, S0/S1, and product claims remain false.

## Non-goals

- No keys, trust stores, dependency installation, production execution, second-host/external result, S0 acceptance, S1 work, fitting, or product/scientific promotion.

## Likely Files Or Search Targets

- Both validation bootstrap, dependency identity, authorization, receipt, run-start, runner, writer, and result-review chains
- New 27/59 result-review module, focused tests, capability/status/roadmap/CI records

## Verification

- Repeated fresh-process hash determinism, environment/path injection, direct-stage bypass, source/dependency/checkout cross-wire, evidence-class downgrade, test/production confusion, metric/failure omission, signature/role/revocation/supersession tests.
- Both complete validation chains, runtime-integrity companion contract, Ruff, capability/YAML equality, architecture guard, and `git diff --check`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop before setting any scientific, fitting, S0/S1, or product claim from receipt collection alone.

## Risk Level

R4

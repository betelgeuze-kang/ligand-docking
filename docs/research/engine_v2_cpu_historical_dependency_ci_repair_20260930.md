# Historical CPU dependency CI repair — 2026-09-30

The historical CPU protocol and its environment/result receipts now retain the H5
dependency reviewed at their own freeze. The latest H5 review remains separate.
This restores historical metadata seals and does not authorize current physics
under the historical execution protocol.

## Observed failure and change

At parent commit `712a664531f7449bc3900e8905d6b79c2931457d`, the
[dedicated CPU job](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/36718692534/job/109897956487)
failed 109 tests after 197 passes. Three post-merge Python jobs each reached 352
passes before the CPU protocol failed. Their original GitHub job logs were fetched
again into durable storage and are authenticated by the download receipt.

The historical CPU H5 dependency is
`63c3ae48ed755a360afd4c9ed77a8553f75da4ab793e287d89a8a68b76ea7ac8`;
the latest review is
`725171ad350f22d471b0a2cfdcd8c94f56cfbb795af3f585d3d655c365e7da0b`.
Three metadata builders imported the latest global constant and silently changed
historical projections. They now use one explicit historical CPU dependency for
protocol construction, receipt generation and receipt verification. Existing
protocol/receipt seals, signature/nonce guards, exact execution dependencies,
arithmetic and scientific thresholds remain unchanged.

Tests bind both distinct values, verify that a later H5 change cannot rebind the
historical documents, and reject mutation of the historical dependency. The
test-only source view pins the three exact new source hashes and rejects further
byte changes. Its original 187-path inventory, historical fixture and protocol
seals remain unchanged; current manifest SHA-256 is
`81f82e4f3f4f0fd367e1139a5a8a92dae83059b104000f8bfaa9c6793612e4ef`.

## Durable validation

**354 passed, zero failures/errors/skips**, 367.481 seconds. Scope is all 23
dedicated CPU workflow test modules plus the global historical source-view module.
All pinned engine, test, configuration and frozen SRO source hashes remain
identical before/after validation. The historical-source CLI, six-file Ruff and
`git diff --check` also pass. Full repository lint is not claimed.

Earlier temporary runs showed 351 passes/three sandbox trust failures and 354
host passes. The sandbox projected root-owned git, openssl and `/dev/null` as uid
65534; unchanged guards rejected that environment. Their temporary raw artifacts
became inaccessible after a turn transition. Those observations are retained only
as an explicitly marked tool-output projection, not reconstructed receipts and
not acceptance evidence. The new run writes raw logs, JUnit, command results and
before/after source pins directly to durable storage, with host uid 0 confirmed.

Archive: `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-cpu-dependency-durable-validation-20260930-p1d65w64`.
Manifest SHA-256: `9d6e795148079b9c9156fa062e6a0fa87dde9fb633cda8e2e1059158900b63bc`.
It authenticates 37 payloads (1601635
bytes), including the newly fetched original CI logs, both raw and gzip forms with
verified decompression, source snapshots and patch. Original files remain. No
molecular input bodies were copied; relocated execution is not established.

Evidence: [`engine_v2_cpu_historical_dependency_ci_repair_20260930_v1.json`](../evidence/engine_v2_cpu_historical_dependency_ci_repair_20260930_v1.json).

Local synthetic contract validation is separate from hosted CI on the future
commit. No target scorer, force evaluator, optimizer or OpenMM computation was
added. The frozen terminal SRO campaign remains two completed, one failed and one
unstarted case, recovery 0/4. Fresh-128 remains protected and unrun. Affinity,
learning benefit, HIP parity and service readiness remain **NOT_QUALIFIED**.
The five-goal objective remains active.

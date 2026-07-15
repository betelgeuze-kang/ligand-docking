# Repository recovery and Engine v2 roadmap — 2026-07

Status: active recovery record

Observed at: 2026-07-15
Starting `main`: `de83e282d4e69b0e5233ea3306ca2ab929fc823e`

This is the living decision record for recovering the open pull-request stack. It records code ownership and merge order; it is not scientific evidence and does not promote any product or execution claim.

## Repository surfaces and claim boundary

The independent Engine v2 surface (`betelgeuze_engine_v2/`, `packaging/engine-v2/`) remains separate from the legacy/product delivery surface (`api/`, `core/`, `betelgeuze_engine/`, `betelgeuze_product/`, `deploy/`). Source-level tests establish bounded contract behavior only.

The following remain false unless separate reviewed evidence changes them:

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`
- GPU parity, commercial readiness, and public benchmark validation are not established

## Open PR graph at recovery start

All listed PRs were open and draft at the observation point. `behind/ahead` is relative to the starting `main`.

| PR | Base → head | Behind/ahead | Observed state | Unique ownership | Decision |
|---|---|---:|---|---|---|
| #38 | `main` → `codex/source-of-truth-benchmark-gpcr-pocketmd` | 142/137 | conflicting; cancelled checks | historical benchmark/product donor | Do not bulk merge; extract remaining unique material, then supersede. |
| #40 | `main` → `codex/pr38-source-of-truth-refresh` | 141/1 | clean; no checks | one refresh delta, not an ancestor of #38 | Audit against current main; replace or supersede. |
| #41 | `main` → `codex/p0-product-safety-closure` | 141/63 | conflicting | mixed product-safety donor | Do not bulk merge; bounded extraction only. |
| #42 | `main` → `agent/api-operational-hardening` | 141/14 | conflicting | API operations donor | Compare after H4; extract only still-unique operations changes. |
| #43 | `main` → `agent/phase0-3-docking-hardening` | 141/2 | conflicting | mixed API security, proxy naming, legacy physics, FEP/solvent/MM-GBSA | Never bulk merge; split by ownership or supersede. |
| #60 | `codex/h1-input-identity` → `codex/h2-docking-semantics` | 0/1 | mergeable but failing `api-worker-contract` | H2 docking score, pose validity, failure semantics | Rebase base metadata to `main`, repair semantics and canonical CI, merge with merge commit. |
| #61 | `codex/h2-docking-semantics` → `codex/h3-benchmark-contracts` | 49/31 | conflicting; ancestry diverged | H3 benchmark manifest/report contracts | Rebuild from unique H3 files on merged H2; replacement PR preferred. |
| #62 | `main` → `codex/h4-api-security-hardening` | 15/12 | mergeable but failing API lanes | pure-ASGI payload/security hardening | Restack after P0, repair streamed limit semantics, require four green lanes. |
| #63 | old H3 → `codex/h5-reference-physics` | 49/36 | unstable | five H5 reference-physics commits | Restack unique H5 commits onto new H3; merge commit. |
| #64 | old H5 → `codex/h6-release-rc` | 49/48 | unstable | H6 release candidate, packaging, static analysis | Restack onto new H5; split static analysis from release matrix. |
| #65 | old H3 → `codex/extract-external-baseline-receipts` | 49/35 | unstable | four H7 offline external-baseline receipt commits | Restack as an independent leaf on new H3. |
| #66 | `agent/independent-engine-v2-refactor` → `codex/v2-1-canonical-ingest` | 141/12 | unstable; focused CPU failure | mixed ingest, mmCIF, peptide, alkane, SPICE, and CI donor | Do not bulk merge; create extraction matrix and bounded child PRs. |

Parent relationships observed at recovery start:

```text
main ── H2 (#60)
          └─ old/diverged H3 (#61)
               ├─ H5 (#63) ── H6 (#64)
               └─ H7 (#65)

main ── H4 (#62)                 (API-only leaf after P0)
old donor parent ── #66          (must be decomposed)
```

## Recovery ownership and merge plan

| Order | Slice | Owned change | Base/update rule | Merge rule |
|---:|---|---|---|---|
| 1 | P0 CI isolation | Untrusted PR runner boundary, secure checkout, runner-temp artifacts, policy tests, Actions Dependabot | Fresh starting `main` | Merge only after hosted checks; before all API/product PRs. |
| 2 | H2 #60 | Search identity binds actual symmetry mappings; explicit not-evaluated validity; H2 canonical CI ownership | Latest main after P0; retain a backup branch | Merge commit; all focused and canonical tests green. |
| 3 | H3 replacement | Benchmark manifest, runner, evidence, report, and benchmark-only CI deltas | Fresh branch on merged H2; no blind 31-commit rebase | Merge commit; Python 3.10–3.12 and wheel checks green. |
| 4 | H5 #63 | Bounded reference-physics contracts only | Restack unique five commits onto new H3 | Merge commit. |
| 5 | H6 #64 | `0.2.0rc1` release/package/static-analysis scope | Restack onto merged H5 | Merge after static-analysis and release matrix are green. |
| 6 | H7 #65 | Offline external baseline work orders and reviewed receipts | Restack as leaf on merged H3 | Leaf merge after exact coverage/integrity tests. |

H4 #62 may proceed after P0 in parallel with H2/H3 because it is API-only. Immediately before merge it must be updated to the latest main and have `ci-api-h4-hosted`, `product-api-worker`, `ci-mobile-lite`, and `product-image-smoke` green.

## Validation matrix

| Slice | Local required validation | Remote required lanes |
|---|---|---|
| P0 | `tests/unit/test_github_workflow_trust_boundaries.py`; parse every workflow YAML | Hosted workflow-policy/API compile and hosted image build-graph check; no PR-reachable self-hosted job |
| H2 | bounded scaffolds, input identity, docking semantics, post-merge state; architecture check; compileall | Canonical Engine v2 matrix and all affected hosted checks |
| H3 | H1/H2/H3 ownership tests; full canonical Engine v2 suite; wheel smoke on 3.10–3.12 | Benchmark lane and canonical matrix |
| H4 | H4 security, mobile, job-store/security/deploy regressions; `py_compile`; `api.main` import | Four named API/product lanes |
| H5 | Reference energy/force, finite difference, invariance, cutoff, fail-closed parameters | Canonical matrix on new H3 ancestry |
| H6 | Ruff/Pyright; release tests; reproducible wheels; SBOM; clean install | Static-analysis job plus 3.10–3.12 release matrix |
| H7 | Receipt identity, confinement, exact row coverage, failure retention, no claim promotion | Canonical/benchmark leaf checks |
| #66 children | Focused contract tests per extraction bucket, including 3.10–3.12 determinism where applicable | One focused workflow per ownership bucket |

## Additional observed blockers

- A persistent repository-level self-hosted ROCm runner existed on this public, personal-account repository, and historical pull-request workloads were confirmed on it. The runner registration was removed on 2026-07-15; repository runner inventory was then verified empty.
- Fork workflow approval was tightened from first-time contributors to all external contributors on 2026-07-15. This is defense in depth, not a substitute for runner isolation.
- Trusted self-hosted jobs also fail closed unless repository variable `TRUSTED_SELF_HOSTED_CI_ENABLED` is explicitly `true`. The variable is not enabled during recovery.
- The former runner host must be treated as untrusted. Re-registration is blocked pending clean rebuild/reimage, review and rotation of host-accessible credentials, and an execution design that does not expose a persistent repository runner to public PR workflows.
- PR-only and trusted self-hosted workflows are now separate files, with exact semantic policy tests. Those tests detect repository regressions but do not replace the external runner-access boundary.
- #61 no longer has clean H2 ancestry; #63/#64/#65 depend on that old H3 line.
- #66 is 141 commits behind the starting main and combines unrelated ownership buckets.
- Existing product preflight tests and status builders encode the old unsafe `clean:false`/pre-checkout recovery behavior and must be updated with P0 instead of being preserved as comments or compatibility tokens.
- No promotion flag may be changed as a shortcut for a failing test or missing runtime receipt.

## P0 containment and local validation snapshot

Observed after remediation on 2026-07-15:

- Repository self-hosted runner inventory: `0`
- Fork workflow approval policy: `all_external_contributors`
- Repository variable `TRUSTED_SELF_HOSTED_CI_ENABLED`: absent, so trusted jobs fail closed
- Workflow trust-boundary and related receipt/preflight regressions: `92 passed`
- Hosted dependency-light API/mobile profile: `72 passed, 4 skipped`; skips are the intentionally excluded PyTorch, RDKit, OpenMM, and HDF5 optional-runtime boundaries
- `docker buildx build --check --file Dockerfile.product .`: passed with no warnings
- Workflow YAML parsing, Python compilation, and `git diff --check`: passed
- A broader AI evidence-bundle CLI test that expects a missing local runtime-gate artifact remains a pre-existing baseline failure and reproduces unchanged on the starting `origin/main`; it is outside P0 acceptance

## Donor replacement and supersession ledger

| Donor | Replacement status | Remaining action |
|---|---|---|
| #38 | pending matrix | Identify current-main unique benchmark/product deltas. |
| #40 | pending comparison | Confirm whether its single delta is already represented or create one bounded replacement. |
| #41 | pending extraction | Split product-safety contracts; do not inherit stale ancestry. |
| #42 | pending post-H4 comparison | Preserve only operations changes not covered by H4/current main. |
| #43 | pending multi-bucket matrix | Separate API, naming, legacy physics, and advanced-method material. |
| #66 | extraction matrix required | Create at least the first current-main child PR, then close donor after all retained children are linked. |

## Actual merge order

This table is append-only. Planned order is not recorded as completed work.

| Actual order | PR | Merge SHA | Method | Evidence |
|---:|---|---|---|---|
| — | none as of 2026-07-15 | — | — | Recovery in progress. |

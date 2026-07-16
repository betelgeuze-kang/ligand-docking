# Repository recovery and Engine v2 roadmap — 2026-07

Status: core recovery and donor cleanup complete; future feature work is independent

Observed at: 2026-07-15
Starting `main`: `de83e282d4e69b0e5233ea3306ca2ab929fc823e`
Core-recovery endpoint `main`: `3f9ede19bb158a02eb3d06e0ed42dea6952db680`
Donor-cleanup evidence endpoint `main`: `2c0eddb107dde5dbdddf206ea24b6fefc78d7d18`

This is the living decision record for recovering the open pull-request stack. It records code ownership and merge order; it is not scientific evidence and does not promote any product or execution claim.

## Repository surfaces and claim boundary

The independent Engine v2 surface (`betelgeuze_engine_v2/`, `packaging/engine-v2/`) remains separate from the legacy/product delivery surface (`api/`, `core/`, `betelgeuze_engine/`, `betelgeuze_product/`, `deploy/`). Source-level tests establish bounded contract behavior only.

The following remain false unless separate reviewed evidence changes them:

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`
- `scientific_validation=false`
- `public_benchmark_validation=false`
- `gpu_parity=false`
- `customer_execution=false`
- `commercial_readiness=false`

Future evidence stages and promotion rules are recorded separately in the
[Engine v2 scientific evidence roadmap](engine-v2-scientific-evidence-roadmap.md).

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

H4 #62 was eligible to proceed after P0 in parallel with H2/H3 because it was API-only. It was deliberately merged last, after the first bounded #66 child, so its final restack and four required hosted checks covered the then-current `main`. The numbered recovery slices above are now merged.

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

## Observed blockers and resolution state

- A persistent repository-level self-hosted ROCm runner existed on this public, personal-account repository, and historical pull-request workloads were confirmed on it. The runner registration was removed on 2026-07-15; repository runner inventory was then verified empty.
- Fork workflow approval was tightened from first-time contributors to all external contributors on 2026-07-15. This is defense in depth, not a substitute for runner isolation.
- Trusted self-hosted jobs also fail closed unless repository variable `TRUSTED_SELF_HOSTED_CI_ENABLED` is explicitly `true`. The variable is not enabled during recovery.
- The former runner host must be treated as untrusted. Re-registration is blocked pending clean rebuild/reimage, review and rotation of host-accessible credentials, and an execution design that does not expose a persistent repository runner to public PR workflows.
- PR-only and trusted self-hosted workflows are now separate files, with exact semantic policy tests. Those tests detect repository regressions but do not replace the external runner-access boundary.
- The #61 ancestry break was resolved by reconstructing and merging replacement #72; #63/#64/#65 were then restacked and merged on the repaired line.
- At closure, #66 was 249 commits behind then-current `main` and 12 donor commits ahead, and still combined unrelated ownership buckets.
- The unsafe `clean:false`/pre-checkout recovery assumptions in product preflight tests and status builders were removed with P0 instead of being preserved as compatibility tokens.
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
| #38 | closed and superseded without merge | Current benchmark/GPCR/PocketMD owners were retained; stale generated-current work orders, machine-bound recovery paths, contradictory claim-grade proxy output, and mixed cockpit/API code were explicitly discarded. |
| #40 | closed and superseded without merge | It contained only an obsolete task scaffold and no implementation delta; current release source-of-truth code and freshness contracts were merged through #62. |
| #41 | closed and superseded without merge | Scientific-input provenance/enforcement/materialization was replaced by #77–#79; no stale promotion state was inherited. |
| #42 | closed and superseded without merge | Current H4 operations and artifact handling superseded the stale API branch. |
| #43 | closed and superseded without merge | #96 retained neighbor/pocket working-set correctness and #97 retained claim-honest legacy proxy semantics; all old API/security/dependency/Tier-beta material was discarded. |
| #49 | closed and superseded | Engine v2 scope was decomposed into merged #50–#54, #56, and #57; no donor branch merge remains. |
| #61 | closed and superseded | Replacement #72 was reconstructed on merged H2 and merged cleanly. No donor branch merge remains. |
| #66 | closed and superseded without merge; six bounded children merged | #73, #89, #90, #91, #94, and #95 are merged. All other donor families are discarded as donor patches. Any future `_struct_conn`, topology, preparation, format, physics, or evidence work must start independently from current `main`. |

## Open PR snapshot after donor cleanup

Observed after `main@2c0eddb` on 2026-07-16: no open pull requests remained.

PR #66 was closed without merge after its six accepted children were linked.
Closing the donor does not promote its unextracted content: selected
`_struct_conn`, polymer topology, peptide preparation, PDB/SDF/SMILES, alkane
physics, and SPICE evidence remain unaccepted donor material. If pursued, each
must be designed and reviewed as a new current-main change with its own tests
and claim boundary.

## Governance follow-up resolution

These items were kept out of the ancestry/security recovery and later handled
as separate reviewable PRs:

- #76 added `SECURITY.md`, `CONTRIBUTING.md`, and `.github/CODEOWNERS`.
- #84 removed tracked local harness state and added the repository hygiene gate.
- #68, #69, #71, #85, #86, #88, and #92 upgraded and immutably pinned Actions
  while preserving hosted/untrusted and qualified/self-hosted separation.

## Post-recovery donor extraction results

| PR | Merge SHA | Donor | Retained bounded scope |
|---|---|---|---|
| #89 | `eeed0433` | #66 | mmCIF identity and polymer-sequence projection |
| #90 | `57f61a64` | #66 | zero-occupancy source declarations |
| #91 | `41f78162` | #66 | alternate-location source declarations |
| #94 | `7dc4e5de` | #66 | nonpoly component/entity/asym/instance identity carrier |
| #95 | `e570cd70` | #66 | selected component atom and optional bond source declarations |
| #97 | `7f7c07ab` | #43 | claim-honest legacy scientific proxy semantics |
| #96 | `7dc025ed` | #43 | neighbor-cache geometry and bounded pocket working sets |

## H4 final acceptance snapshot

- PR #62 head `3016ebea96a05742266e7fd722b0596626098a92` was merged as `3f9ede19bb158a02eb3d06e0ed42dea6952db680` only after all four required hosted API/product checks passed.
- The final 16-file H4 unit regression set reported `310 passed`; the exact hosted command groups were reproduced locally before push.
- An independent final security/evidence re-audit reported `140 passed` and no P0/P1 issue or push blocker.
- The merged implementation binds validated execution to a short-lived hash-pinned runtime receipt and signed purpose evidence, confines access to the database-selected winning attempt and signed artifact bundle, keeps standard deployment routes fail closed, and leaves public/customer execution disabled.
- Remaining P2 trust boundaries include same-UID pathname/TOCTOU exposure, an unsigned local docking ledger, receipt-expiry/re-evaluation hardening, and mutable image/container hardening. These are residual engineering risks, not evidence of scientific or product qualification.

## Actual merge order

This append-only table records the exact completed core-recovery merge order.

| Actual order | PR | Merge SHA | Method | Evidence |
|---:|---|---|---|---|
| 1 | #67 | `a3a585d5eb94f19b2e8e715ac4914a2d3b4e1f30` | merge commit | Hosted PR isolation, workflow-policy tests, empty repository runner inventory, and fail-closed trusted lanes. |
| 2 | #60 | `298c8223e15e353b8562ae6a0369e031f31cdfdc` | merge commit | H2 symmetry-mapping identity, not-evaluated pose semantics, and canonical CI ownership. |
| 3 | #72 | `bf73e0acf13b41496b4c3592ea027c61b028ce72` | merge commit | Clean H3 replacement on merged H2; #61 closed as superseded. |
| 4 | #63 | `8097b516d112e33abd64887e8ad4cb6f6ce6799c` | merge commit | Restacked H5 bounded reference-physics contracts with promotion flags unchanged. |
| 5 | #64 | `1657b6a1039ba75799cf167a609eefc49faa75fd` | merge commit | Restacked H6 release candidate with separate static-analysis and release-matrix checks. |
| 6 | #65 | `13af55c8f9251bc465d144b90d263efa5f5d01ea` | merge commit | Independent H7 offline external-baseline receipt leaf. |
| 7 | #73 | `6ae6d1140c52402a3d375d74b4c34d3a3b7e9ddb` | merge commit | First bounded #66 child: CIF syntax only; donor was later closed after the bounded audit. |
| 8 | #62 | `3f9ede19bb158a02eb3d06e0ed42dea6952db680` | merge commit | Final H4 API security restack; four required hosted lanes green and final security re-audit clear of P0/P1. |

# Storage Retention And Cleanup Policy

Last reviewed: 2026-06-14 KST

This repository is now large enough that cleanup must be treated as a product
operation, not as an ad hoc file move. The rule is simple: keep the minimal
auditable evidence needed to reproduce product/readiness claims, document that
evidence, then clean only non-authoritative or regenerable payloads after an
operator-approved plan.

## Current Pressure

The root filesystem was observed at 100% use during the 2026-06-14 goal run.
After removing regenerable user caches outside the repository, `df` reported
about 37 GiB available. The repository itself still measured about 64 GiB, with
the largest active areas:

| path | observed size | posture |
| --- | ---: | --- |
| `runs/` | 35 GiB | keep only current source-of-truth ledgers and required evidence; review historical/bulk payloads |
| `data/` | 12 GiB | keep datasets required by current gates or manifest them before any offload |
| `models/` | 6.0 GiB | keep promoted/checkpoint evidence by manifest; review stale training intermediates |
| `.git/` | 5.6 GiB | do not rewrite history without a separate explicit approval |
| `casp17/` | 4.0 GiB | keep final target/object/viewer/manifest evidence; review historical experiment payloads |
| `tools/` | 2.3 GiB | code stays in git; generated caches/build products are cleanup candidates |

Do not use `/tmp` as a parking lot for repository data. `/tmp` is only scratch
space for short-lived command execution.

## Keep Set

These are the first-class product evidence records and should not be deleted or
externalized without a replacement manifest and a passing source-of-truth check:

| class | examples | required preservation |
| --- | --- | --- |
| Source and policy | `api/`, `core/`, `tools/`, `config/`, `docs/`, `tests/`, `deploy/`, `legal/` | Keep in git, with normal review |
| Current release ledgers | `runs/*_current.json`, `runs/*_current.md`, `runs/*_current.csv` that are referenced by `runs/product_release_source_of_truth_gate_current.json` | Keep active, or regenerate and verify before cleanup |
| Full-commercial blocker receipts | R8/R9 receipt JSON/CSV/MD, GPCR broad-claim receipt, API runner receipt, production AI receipt | Keep active until the relevant blocker is closed |
| Scientific accuracy frontier evidence | R9 public benchmark materialization summaries, coordinate validation CSV, metric source payload summaries, claim-grade gap audits | Keep active while they define the current accuracy boundary |
| CASP17 current evidence | final target folders, final PDB/mmCIF/object folders, viewer index, target/object manifests, validation reports | Keep current final evidence and sha256 manifests |
| Model/checkpoint evidence | production checkpoint readiness ledgers, selected checkpoint manifests, sha256/registry receipts | Keep selected/promoted evidence; review stale training intermediates separately |
| Legal and operator receipts | license review gates, rollout receipts, operator approval receipts, audit logs named by current gates | Keep active until superseded by a newer reviewed receipt |

## Cleanup Candidates

These may be cleaned only after a generated review manifest proves they are not
referenced by the current source-of-truth artifacts:

| class | examples | cleanup rule |
| --- | --- | --- |
| Regenerable caches | `.pytest_cache/`, `__pycache__/`, browser/selenium/pip caches outside the repo | Delete directly when disk pressure blocks work |
| Logs and transient command output | `logs/`, one-off smoke stdout/stderr, temp debug JSON not referenced by gates | Delete after preserving any summarized evidence in a current ledger |
| Historical bulk runs | old trajectory frames, stale stage outputs, historical branch/config/combined-gate payloads | Keep compact manifest and representative final outputs only |
| Duplicate archived experiment roots | old `runs/archive`-style experiment snapshots that have current reports | Retain report, sha256 manifest, and final representative structures |
| Training intermediates | unselected checkpoints, optimizer states, raw curriculum intermediates | Keep selected checkpoint receipt and config; clean only after model manifest review |
| CASP17 historical probes | massivefold probe workspaces, historical seed candidates, temporary rerank experiments | Keep final current target/object evidence and source authority manifest |

## Required Cleanup Flow

1. Build a cleanup review manifest that lists candidate paths, sizes, reason,
   source-of-truth reference status, and required replacement evidence.
2. For every candidate, prove it is not listed in current `source_artifacts`,
   receipt CSVs, current manifests, or release bundle entries.
3. Preserve compact evidence before deletion: relative path, size, sha256 where
   practical, role, final representative artifact, validation report, and the
   command that regenerates the artifact if regeneration is expected.
4. Require operator approval for any deletion, archive, externalization, git
   history rewrite, LFS rewrite, or movement of `runs/`, `data/`, `models/`, or
   `casp17/` payloads.
5. After cleanup, rerun the release source-of-truth gate, independent product
   readiness check, and any domain-specific gate whose evidence path changed.

## Verification Commands

Run these after a cleanup plan is generated or applied:

```bash
python3 tools/build_product_release_source_of_truth_gate.py
python3 scripts/check_independent_product_readiness.py
git status --short --branch
```

For applied cleanup that changes scientific evidence, also run the relevant
builder chain before committing.

## Current Decision

Do not move repository payloads into temporary locations. First create or update
the retention manifest and keep only the essential audited evidence. Actual
deletion remains a separate operator-approved step.

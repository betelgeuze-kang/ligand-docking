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
about 37 GiB available. After the approved NPZ/dynamics and ligand-heavy raw
payload cleanups, `df` reported about 48 GiB available and the generated
`runs/` tree measured about 13.79 GiB. The repository originally measured about
64 GiB, with the largest active areas:

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

## Essential Evidence Manifest

Large protected roots are not cleanup candidates just because the top-level path
is absent from the current source-of-truth JSON. `models/` and `casp17/`, for
example, can contain selected checkpoints, final structures, viewer objects, and
validation reports that are product evidence. Treat those paths as
`essential_evidence_manifest_required` until a compact register lists what must
be kept.

The read-only retention manifest builder is:

```bash
python3 tools/build_storage_retention_manifest.py
```

It writes local generated review files under `runs/storage_retention_manifest_current.*`.
Those files inventory sizes, current source-of-truth references, transient
cleanup candidates, and protected paths that need a compact evidence register.
The builder does not delete, move, archive, externalize, rewrite git history,
upload, commit, push, or mutate external state.

The current intended sequence is:

1. Generate the retention manifest.
2. For `essential_evidence_manifest_required` paths, create a compact register
   of final/selected artifacts, sha256s where practical, provenance, validation
   reports, and regeneration commands.
3. Clean only transient or regenerable paths that remain unreferenced.
4. Request a separate operator approval before any deletion of protected
   evidence roots or historical payloads.

The current compact evidence register builder is:

```bash
python3 tools/build_storage_essential_evidence_register.py
```

It inventories `models/` and `casp17/` by evidence role, top domain, size,
source-of-truth reference status, sha256 status, and keep policy. Large files
are intentionally marked `deferred_file_above_hash_max_bytes` or
`deferred_hash_row_limit_reached` instead of being aggressively hashed during a
disk-pressure review.

The domain-level selection review board is:

```bash
python3 tools/build_storage_essential_evidence_selection_review.py
```

It narrows the protected evidence register to the largest review domains and
assigns the next review action: model checkpoint selection, CASP17 final target
register, CASP17 viewer/object register, CASP17 run artifact register, or
manifest/receipt register. This board is still read-only and does not approve
cleanup.

## NPZ / Dynamics Cleanup

Generated trajectory bundles such as `stage2_traj_frames/**/*.npz` may be
deleted after preserving a JSON execution record, but only when they are not
exactly referenced by current evidence. Directory-level or command-level
mentions are not enough to keep every raw frame forever; exact selected
trajectory references stay protected.

The read-only candidate manifest is:

```bash
python3 tools/build_npz_dynamics_cleanup_manifest.py
```

The approval-gated execution command is:

```bash
python3 tools/apply_npz_dynamics_cleanup_manifest.py --execute --approval-token APPROVE_NPZ_DYNAMICS_CLEANUP
```

The apply command deletes only rows marked `delete_recommended=true` in
`runs/npz_dynamics_cleanup_manifest_current.json`, writes
`runs/npz_dynamics_cleanup_execution_current.*`, and refuses to touch referenced
keep rows, review-required rows, source code, model roots, CASP17 roots, git
history, or any path outside the repository.

## Ligand Heavy Run Cleanup

Old ligand/HTVS run payloads can be reduced to compact top-ranking evidence
when the generated manifest proves that `stage5_ranking_topk`,
`stage5_ranking_unique`, `stage5_ranking_summary`, shortlist, summary, claim,
SLA, or status evidence is already present. Raw ligand inventories, hard-decoy
labels, full stage score CSVs, full ADMET surfaces, stage2 sidecar directories,
and transient logs/locks are cleanup candidates only after the JSON manifest is
written.

The read-only candidate manifest is:

```bash
python3 tools/build_ligand_heavy_run_cleanup_manifest.py
```

The approval-gated execution command is:

```bash
python3 tools/apply_ligand_heavy_run_cleanup_manifest.py --execute --approval-token APPROVE_LIGAND_HEAVY_RUN_CLEANUP
```

The apply command deletes only rows marked `delete_recommended=true` in
`runs/ligand_heavy_run_cleanup_manifest_current.json`, writes
`runs/ligand_heavy_run_cleanup_execution_current.*`, and refuses to touch
top-ranking/summary keep rows, referenced keep rows, review-required rows,
source code, model roots, CASP17 roots, git history, or any path outside the
repository.

## Required Cleanup Flow

1. Build a cleanup review manifest that lists candidate paths, sizes, reason,
   source-of-truth reference status, and protected paths that need a compact
   essential evidence register.
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
python3 tools/build_storage_retention_manifest.py
python3 tools/build_storage_essential_evidence_register.py
python3 tools/build_storage_essential_evidence_selection_review.py
python3 tools/build_npz_dynamics_cleanup_manifest.py
python3 tools/build_ligand_heavy_run_cleanup_manifest.py
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

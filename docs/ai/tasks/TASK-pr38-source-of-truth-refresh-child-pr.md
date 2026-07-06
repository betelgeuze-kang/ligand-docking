# TASK-pr38-source-of-truth-refresh-child-pr

Status: draft child PR scaffold
Parent: PR #38
Prerequisite: PR #39 `ci_runner_hygiene` merged into `main`

## Purpose

This child PR prepares the next PR #38 extraction slice: `source_of_truth_refresh`.

The goal is to reconcile release/source-of-truth wording after the CI runner hygiene split, without promoting product, science, benchmark, customer, PocketMD Lite, GPCR, F2/G1, or paid-pilot claims.

## Remote Basis

- PR #39 closed the first split slice: `ci_runner_hygiene`.
- PR #39 was validated remotely before merge:
  - `product-api-worker`: success
  - `product-image-smoke`: success
- This child PR starts from the post-PR39 `main` merge commit.
- PR #38 remains an omnibus draft until its remaining slices are extracted.

## Claim Boundary

Allowed wording:

- CI runner hygiene has been split from PR #38 and merged through PR #39.
- Source-of-truth refresh is the next child PR slice.
- PR #38 is still not release-ready as an omnibus PR.

Disallowed wording:

- paid-pilot readiness
- broad commercial platform readiness
- benchmark claim closure
- PocketMD Lite claim-grade readiness
- broad GPCR/router/platform promotion
- F2/G1 solver closure
- ROCm/GPU solver-truth readiness
- customer evidence completion

## Candidate File Cluster

Expected source-of-truth slice files include, but are not limited to:

- `docs/product_stage_and_roadmap_2026_06_30.md`
- `docs/ai/tasks/TASK-pr38-stabilization-split.md`
- `tools/product/build_release_source_of_truth_gap5_scan.py`
- `tools/product/build_product_release_source_of_truth_gate.py`
- `tools/product/run_product_release_current_refresh.py`
- release source-of-truth tests
- PM queue / goal release decision tests if directly touched by stale state reconciliation

## Required Updates

1. Reconcile PR #38 split state after PR #39 merge.
2. Remove stale file-count or patch-count language where present.
3. Separate these states clearly:
   - `main` after PR #39
   - remaining PR #38 draft state
   - future child PR extraction state
4. Preserve `restricted Tier-alpha`, `pre-paid-pilot`, and `broad claims frozen` wording.
5. Keep source-of-truth freshness separate from paid-pilot or commercial science readiness.

## Focused Validation Expectations

This child PR should include focused tests for whichever source-of-truth builders it changes. Expected validation pattern:

```bash
python3 -m pytest -q \
  tests/unit/test_build_product_release_source_of_truth_gate.py \
  tests/unit/test_build_release_source_of_truth_gap5_scan.py \
  tests/unit/test_run_product_release_current_refresh.py \
  tests/unit/test_build_pm_priority_queue_status.py
./scripts/ai-verify.sh
```

Adjust the test list to match actual extracted files.

## Acceptance Criteria

- PR #38 split state is current after PR #39.
- No stale PR #38 file-count references remain.
- Release source-of-truth gate wording does not imply paid-pilot or broad science readiness.
- Any generated artifact status remains fail-closed when evidence is missing.
- Claim-boundary review is included in the PR body.
- No local `runs/` payload, customer data, benchmark raw data, checkpoint, or private evidence is committed.

## Non-goals

This child PR must not:

- run docking or MD;
- generate external benchmark receipts;
- ingest customer shadow evidence;
- recover F2g/F2h authoritative surfaces;
- mutate PR #38 science claims;
- mark PocketMD Lite claim-grade;
- promote broad platform wording.

## Next Child PR After This

After this source-of-truth slice lands, the recommended next child PR is:

1. `public_benchmark_phase2`
2. then `pocketmd_lite_recovery`
3. then `gpcr_hard_decoy_closure`

# TASK-pr38-stabilization-split: PR #38 Stabilization and Split

## Goal

Split draft PR #38 into small, reviewable PRs before merge. Current observed state: draft PR, 96 files, +22377/-464; first commit is an omnibus 91-file change. Current checked-in release gate reports `blocked_product_release_source_of_truth_gate`, `stale_artifact_count=49`, `blocker_count=82`; roadmap text still cites 37/71, so refresh reconciliation is required.

## Scope

1. Source-of-truth gap scan plus release refresh path.
2. Public benchmark Phase 2 audit surfaces.
3. GPCR hard-decoy closure tools and claim-lock evidence.
4. PocketMD Lite API/reporting/evidence recovery.
5. F2g/F2h preflight and authoritative-surface work order.

Child task specs:

- `docs/ai/tasks/TASK-pr38-slice-source-of-truth-refresh.md`
- `docs/ai/tasks/TASK-pr38-slice-public-benchmark-phase2.md`
- `docs/ai/tasks/TASK-pr38-slice-gpcr-hard-decoy-closure.md`
- `docs/ai/tasks/TASK-pr38-slice-pocketmd-lite-recovery.md`
- `docs/ai/tasks/TASK-pr38-slice-f2g-f2h-preflight.md`

## Non-goals

Do not merge the omnibus PR as-is. Do not promote paid-pilot, broad GPCR, benchmark, PocketMD Lite claim-grade, G1/solver, autonomous AI, or enterprise/on-prem claims. Do not execute external mutation, deployment, publication, CASP submission, or public/template structure lookup.

## Likely Files Or Search Targets

Source truth: `tools/product/build_release_source_of_truth_gap5_scan.py`, `tools/product/build_product_release_source_of_truth_gate.py`, `tools/product/run_product_release_current_refresh.py`, `docs/product_stage_and_roadmap_2026_06_30.md`.

Public benchmark: `betelgeuze_product/public_benchmark*.py`, `tools/product/build_public_benchmark_phase2_harness_audit.py`, `tools/accounting/build_pdbbind_casf_pose_affinity_results.py`, `betelgeuze_engine/benchmark/docking_gold.py`.

GPCR: `betelgeuze_product/gpcr_hard_decoy_suite.py`, `config/gpcr_hard_decoy*.csv`, `tools/product/build_gpcr_hard_decoy_*.py`.

PocketMD Lite: `api/product_pocketmd_lite.py`, `api/main.py`, `betelgeuze_product/pocketmd_lite_contract.py`, `betelgeuze_engine/product/runners/backmapping_scoring.py`, `tools/product/build_pocketmd_lite_*.py`, `config/pocketmd_lite_candidates_current.csv`.

F2g/F2h: `docs/f2g_f2h_surface_preflight.md`, `tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py`, `tools/build_f2g_f2h_authoritative_surface_recovery_packet.py`.

## Verification

Each child PR must run its focused unit tests plus `./scripts/ai-verify.sh`. Product/release-refresh child PRs should also run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` and preserve fail-closed blockers unless the artifacts truly refresh. Claim boundary review is mandatory for every child PR.

Run `python3 tools/product/build_pr38_split_review_packet.py` before extraction and require `unassigned_file_count=0`, `ambiguous_file_count=0`, and hunk-level review for every integration touchpoint.

Run `python3 tools/product/build_pr38_child_pr_extraction_plan.py` after the split packet and require `extraction_plan_ready=true`, `source_of_truth_registry_reconciles_last=true`, and focused tests plus `./scripts/ai-verify.sh` for each child PR before review.

Run `python3 tools/product/build_pr38_slice_patch_bundle.py` after the extraction plan and require `patch_bundle_ready=true`, `bundled_changed_file_count=96`, no empty patch slices, and one reviewed local patch per child PR before any branch/commit work.

Run `python3 tools/product/build_pr38_slice_patch_apply_preflight.py` after the patch bundle and require `patch_apply_preflight_ready=true` before any branch/commit work; this check uses temporary Git index files and must not mutate the real index or worktree.

Run `python3 tools/product/build_pr38_split_acceptance_packet.py` after apply preflight and require `split_acceptance_ready=true`; this is the final local handoff receipt for explicit human approval of branch/commit extraction and still keeps paid-pilot wording blocked.

Run `python3 tools/product/build_pr38_child_pr_verification_matrix.py` after the acceptance packet and require `verification_matrix_ready=true`; every child PR row must include a focused test command, `./scripts/ai-verify.sh`, claim-boundary review, and product-mode expectations where applicable.

## Stop Conditions

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries when the task touches CASP readiness.
- Stop if split surgery would require discarding unrelated dirty worktree changes.

## Risk Level

R2

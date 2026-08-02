# TASK-pr38-stabilization-split: PR #38 Stabilization and Split

## Goal

Split draft PR #38 into small, reviewable PRs before merge. Current owner-reported state: draft PR has grown to roughly 198 files / 65k additions, which is too large for CTO review, scientific review, and PM claim-boundary review in one pass. CI runner hygiene is the prerequisite: do not treat PR #38 or any child PR as verified until `product-image-smoke` no longer leaves root-owned or other-user-owned workspace artifacts.

## Scope

0. CI/runner hygiene prerequisite child PR: fix self-hosted cleanup ownership for `runs/product_image_smoke_runner_artifacts`, pin container output UID/GID, and keep generated smoke artifacts outside the workspace in CI.
1. Public benchmark harness / Phase 2 audit surfaces.
2. GPCR hard-decoy closure tools and claim-lock evidence.
3. PocketMD Lite API/reporting/evidence recovery.
4. Developer Preview reproducibility gates for clean checkout, Windows/platform checks, and new-user observation receipts.
5. API/operator cockpit surfaces and release-gate wiring.
6. Docs/tests-only reconciliation after code slices are separated.
7. Source-of-truth gap scan plus release refresh path, reconciled after the owning code/docs child PRs are separated.

Keep F2g/F2h preflight work as a separate child PR only if its files are still present in the omnibus diff after the default slices above are extracted.

Child task specs:

- `docs/ai/tasks/TASK-pr38-slice-ci-runner-hygiene.md`
- `docs/ai/tasks/TASK-pr38-slice-public-benchmark-phase2.md`
- `docs/ai/tasks/TASK-pr38-slice-gpcr-hard-decoy-closure.md`
- `docs/ai/tasks/TASK-pr38-slice-pocketmd-lite-recovery.md`
- `docs/ai/tasks/TASK-pr38-slice-developer-preview-reproducibility.md`
- `docs/ai/tasks/TASK-pr38-slice-api-operator-cockpit.md`
- `docs/ai/tasks/TASK-pr38-slice-docs-tests-reconciliation.md`
- `docs/ai/tasks/TASK-pr38-slice-source-of-truth-refresh.md`
- `docs/ai/tasks/TASK-pr38-slice-f2g-f2h-preflight.md`

## Non-goals

Do not merge the omnibus PR as-is. Do not promote paid-pilot, broad GPCR, benchmark, PocketMD Lite claim-grade, G1/solver, autonomous AI, or enterprise/on-prem claims. Do not execute external mutation, deployment, publication, CASP submission, or public/template structure lookup.

## Likely Files Or Search Targets

Source truth: `tools/product/build_release_source_of_truth_gap5_scan.py`, `tools/product/build_product_release_source_of_truth_gate.py`, `tools/product/run_product_release_current_refresh.py`, `docs/product_stage_and_roadmap_2026_06_30.md`.

Public benchmark: `betelgeuze_product/public_benchmark*.py`, `tools/product/build_public_benchmark_phase2_harness_audit.py`, `tools/accounting/build_pdbbind_casf_pose_affinity_results.py`, `betelgeuze_engine/benchmark/docking_gold.py`.

GPCR: `betelgeuze_product/gpcr_hard_decoy_suite.py`, `config/gpcr_hard_decoy*.csv`, `tools/product/build_gpcr_hard_decoy_*.py`.

PocketMD Lite: `api/product_pocketmd_lite.py`, `api/main.py`, `betelgeuze_product/pocketmd_lite_contract.py`, `betelgeuze_engine/product/runners/backmapping_scoring.py`, `tools/product/build_pocketmd_lite_*.py`, `config/pocketmd_lite_candidates_current.csv`.

CI hygiene: `.github/workflows/product-image-smoke.yml`, `deploy/verify_product_image.sh`, `tools/product/build_product_image_smoke_preflight.py`, `tools/product/build_release_ci_remote_green_receipt.py`.

API/operator cockpit: `api/product_operator_cockpit.py`, `api/main.py`, `api/product.py`, `tools/product/build_product_operator_cockpit.py`, `tools/product/build_product_release_source_of_truth_gate.py`.

F2g/F2h optional: `docs/f2g_f2h_surface_preflight.md`, `tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py`, `tools/build_f2g_f2h_authoritative_surface_recovery_packet.py`.

## Verification

Before extracting child PRs, run the product image smoke preflight tests and require the workflow/script contract to show runner-temp artifacts plus host UID/GID container output. Each child PR must run its focused unit tests plus `./scripts/ai-verify.sh`. Product/release-refresh child PRs should also run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` and preserve fail-closed blockers unless the artifacts truly refresh. Claim boundary review is mandatory for every child PR.

Run `python3 tools/product/build_pr38_split_review_packet.py` before extraction and require `unassigned_file_count=0`, `ambiguous_file_count=0`, and hunk-level review for every integration touchpoint.

Run `python3 tools/product/build_pr38_child_pr_extraction_plan.py` after the split packet and require `extraction_plan_ready=true`, `source_of_truth_registry_reconciles_last=true`, and focused tests plus `./scripts/ai-verify.sh` for each child PR before review.

Run `python3 tools/product/build_pr38_slice_patch_bundle.py` after the extraction plan and require `patch_bundle_ready=true`, `bundled_changed_file_count=198`, no empty patch slices, and one reviewed local patch per child PR before any branch/commit work.

Run `python3 tools/product/build_pr38_slice_patch_apply_preflight.py` after the patch bundle and require `patch_apply_preflight_ready=true` before any branch/commit work; this check uses temporary Git index files and must not mutate the real index or worktree.

Run `python3 tools/product/build_pr38_split_acceptance_packet.py` after apply preflight and require `split_structural_acceptance_ready=true`; require `split_acceptance_ready=true` only after product image smoke/source-of-truth runner hygiene blockers clear. This is the final local handoff receipt for explicit human approval of branch/commit extraction and still keeps paid-pilot wording blocked.

Run `python3 tools/product/build_pr38_child_pr_verification_matrix.py` after the acceptance packet and require `verification_matrix_ready=true` only when `split_acceptance_ready=true`; every child PR row must include a focused test command, `./scripts/ai-verify.sh`, claim-boundary review, and product-mode expectations where applicable.

## Stop Conditions

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries when the task touches CASP readiness.
- Stop if `product-image-smoke` fails from workspace cleanup or ownership before scientific tests run.
- Stop if split surgery would require discarding unrelated dirty worktree changes.

## Risk Level

R2

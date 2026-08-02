# TASK-pr38-slice-docs-tests-reconciliation: Docs and Tests Reconciliation Slice

## Goal

Extract cross-cutting docs and tests from PR #38 into the final child PR after code-bearing slices are separated, so review can focus on consistency, claim boundaries, and verification receipts.

## Scope

- Roadmap/status wording that reflects already-merged child PR evidence.
- Test-only reconciliation for renamed artifacts, route registration, and source-of-truth rows.
- Small docs updates for PR split status, Developer Preview blockers, and fail-closed receipts.

## Non-goals

Do not introduce new product behavior, new benchmark logic, new API routes, external evidence claims, or paid-pilot/full-commercial readiness wording.

## Likely Files Or Search Targets

`docs/product_stage_and_roadmap_2026_06_30.md`, `docs/developer_preview_final_gate_action_register.md`, `docs/ai/tasks/TASK-pr38-*.md`, `tests/unit/test_*`, `docs/ai/checklists/pre-review.md`, `docs/ai/checklists/pre-merge.md`.

## Verification

Run focused tests for any touched test modules.

Run `./scripts/ai-verify.sh`.

Run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` only when docs update product-readiness gates or release-source wording.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if docs imply a readiness claim not backed by a merged child PR and fresh local artifact.
- Stop if this slice needs code behavior changes; move those changes back to the owning child PR.

## Risk Level

R1

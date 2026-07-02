# TASK-pr38-slice-source-of-truth-refresh: Source-of-Truth Refresh Slice

## Goal

Extract the PR #38 source-of-truth gap scan and release refresh path into the first small child PR. This slice should reduce ambiguity around current release blockers without promoting paid-pilot readiness.

## Scope

- Gap-5 classification ledger.
- Release source-of-truth gate wiring for new local artifacts.
- Release refresh command registration for the newly split surfaces.
- Roadmap/source-of-truth wording only where it reflects current gate evidence.

## Non-goals

Do not claim release readiness, paid-pilot readiness, final refresh success, or full commercial release. Do not execute external mutation, deployment, publication, or CASP submission.

## Likely Files Or Search Targets

`tools/product/build_release_source_of_truth_gap5_scan.py`, `tools/product/build_product_release_source_of_truth_gate.py`, `tools/product/run_product_release_current_refresh.py`, `docs/product_stage_and_roadmap_2026_06_30.md`, `tests/unit/test_build_release_source_of_truth_gap5_scan.py`, `tests/unit/test_build_product_release_source_of_truth_gate.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_build_release_source_of_truth_gap5_scan.py tests/unit/test_build_product_release_source_of_truth_gate.py`.

Run `./scripts/ai-verify.sh`.

Run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`; expected outcome is fail-closed unless `release_source_of_truth_ready` and `release_refresh_final_gates_verified` are truly closed by fresh artifacts.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if current artifacts still contradict roadmap counts and the child PR would hide the contradiction.
- No claim text may imply paid pilot while release/source-of-truth gates are blocked.

## Risk Level

R2

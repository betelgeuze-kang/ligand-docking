# OpenCode Worker Slice: Product Release Current Refresh Gate

## Web access

Disabled. Do not browse or fetch web resources.

## Safety boundaries

- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not commit, push, delete, deploy, upload, email, submit external validation, or mutate external services.
- Keep all work local to this repository.
- Preserve unrelated dirty worktree changes. Do not revert files unless the change is clearly yours in this slice and needed to recover.
- Use the existing release/source-of-truth tooling. Do not invent a parallel release driver.

## Goal

Diagnose and unblock the current product-mode verification blockers:

- `release_source_of_truth_ready`
- `release_refresh_final_gates_verified`

The current local symptom is that `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` fails independent product readiness because:

- `runs/product_release_source_of_truth_gate_current.json` is blocked by stale artifacts and semantic rows.
- `runs/product_release_current_refresh_plan_current.json` is only a dry-run plan (`product_release_current_refresh_planned`, `executed_count=0`).

## Scope

1. Inspect the current release refresh/source-of-truth tools:
   - `tools/product/run_product_release_current_refresh.py`
   - `tools/product/build_product_release_source_of_truth_gate.py`
   - `scripts/check_independent_product_readiness.py`
   - focused tests around these tools.
2. Run the existing local refresh path if it is safe:
   - `python3 tools/run_product_release_current_refresh.py --execute`
   - If a command fails or times out, stop at the first failure and report the exact command/status/blocker.
3. If the failure is a narrow code/test contract issue, make the smallest local fix consistent with existing patterns.
4. Rebuild/verify only through existing tooling.

## Expected verification

Run as much as is practical and report exact results:

- `python3 tools/build_product_release_source_of_truth_gate.py`
- `python3 scripts/check_independent_product_readiness.py --quiet --out-json .betelgeuze/worker_independent_product_readiness.json`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`
- Focused pytest only if code changed:
  - `python3 -m pytest -q tests/unit/test_run_product_release_current_refresh.py tests/unit/test_build_product_release_source_of_truth_gate.py tests/unit/test_scripts_product_readiness_entrypoints.py`

## Return summary

Keep the summary concise:

- Changed files
- Commands run and pass/fail
- First failed refresh command, if any
- Final statuses for source-of-truth, release refresh, and independent product readiness
- Remaining blockers, if any

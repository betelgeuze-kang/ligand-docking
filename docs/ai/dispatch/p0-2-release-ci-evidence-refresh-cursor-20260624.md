# Cursor Worker Slice: P0-2 Release CI Evidence Refresh

Web access: disabled.

You are a scoped Cursor implementation worker in the ligand-docking worktree. You are not alone in the codebase: do not revert, overwrite, stage, commit, push, delete, deploy, dispatch workflows, edit branch protection, or mutate external state. Do not read or print `.env*` files. Work with the existing dirty tree.

Goal: make the P0-2 release CI remote-green evidence path more reproducible without performing external GitHub mutations.

Likely files:

- `tools/product/build_release_ci_remote_green_receipt.py`
- `tests/unit/test_build_release_ci_remote_green_receipt.py`
- optionally a small new `tools/product/*` helper if existing builder should stay pure
- optionally `docs/ai/github_self_hosted_runner_setup_2026-06-21.md` or `docs/tier_beta_vertical_slice_gap_audit.md` if a blocker note is needed

Scope:

1. Inspect the current release CI remote-green receipt builder and tests.
2. Identify whether the local toolchain already has a reproducible command/manifest for collecting read-only GitHub API JSON inputs used by the receipt.
3. If missing and low-risk, implement a small typed/read-only helper or receipt metadata addition that records the exact `gh api` endpoints needed for runner inventory, branch protection/required checks, schedule runs, failed-run artifacts, and release-tag runs. The helper must not execute `gh` unless explicitly invoked by an operator; it should emit commands/contract or validate supplied JSON only.
4. Add focused unit tests for the new behavior.

Acceptance:

- No external state mutation.
- No subprocess execution in unit tests.
- Failed/absent evidence remains fail-closed.
- Return a concise summary with changed files, tests run, and any blockers.

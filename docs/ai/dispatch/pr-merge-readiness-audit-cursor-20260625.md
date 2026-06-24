# Cursor Worker Slice: PR/Merge Readiness Audit

Web access: disabled

## Goal

Read-only audit for the active Codex goal's final PR creation and main merge steps.

## Scope

- Inspect current git branch, upstream, existing PR state if available from local/gh read-only commands.
- Inspect dirty worktree at a summary level only.
- Determine whether a PR created now would include the active goal changes.
- Determine what exact human approval is still required before stage/commit/push/PR/merge.

## Safety Boundaries

- Do not edit files.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not stage, commit, push, create PRs, merge, delete, deploy, publish, submit, or mutate external state.
- Do not run long test suites; this is a readiness audit only.

## Suggested Commands

- `git branch --show-current`
- `git status --short --branch`
- `git rev-list --left-right --count origin/main...HEAD`
- `gh pr list --head codex/commercialization-accounting-closure --state all --json number,title,state,url,baseRefName,headRefName,isDraft`

## Return Summary Only

Report:

- Branch/upstream summary.
- Existing PR state.
- Whether current local changes are committed and PR-ready.
- Concrete next commands that require explicit human approval.
- Any blockers to PR creation or main merge.

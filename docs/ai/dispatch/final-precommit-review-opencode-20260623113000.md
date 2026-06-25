# Worker Slice: final pre-commit review only

Web access: disabled.

## Goal
Review the current uncommitted diff for safety, scope, and test coverage before Codex commits and pushes.

## Scope
- Review only. Do not edit files.
- Do not stage, commit, push, delete, or mutate external state.
- Do not read or print `.env*`.
- Preserve the current uncommitted changes.

## Focus
- P0-2 release CI ROCm scheduled/tag gate and artifact retention.
- P0-4 ligand chemistry state routing through topology and ONSPS.
- Tier-beta runner shim/profile/KPI contract integration.
- Product capability surface split-router detection.

## Checks To Run Or Inspect
- `git diff --stat`
- `git diff --check`
- Focused tests already run by Codex may be trusted, but call out any missing test that should block commit.
- Inspect targeted hunks only where needed.

## Return
Concise summary:
- P0/P1 findings, if any
- Suspicious scope drift, if any
- Whether the diff is reasonable to commit
- Any tests you believe must be rerun before commit

# AGENTS.md

## Role Contract

This repository is operated with Codex native goal mode and optional Cursor/OpenCode implementation workers.

- Codex owns goal tracking through its native goal feature, plus design, task slicing, review, verification, and final acceptance.
- Cursor Agent and OpenCode may be used only as scoped implementation workers.
- The human owner owns push, merge, deployment, publication, external submission, billing changes, production mutation, and final accountability.

## Project Context

- Main stack: Python 3.10+ molecular dynamics, local product readiness tooling, API worker surfaces, CAMEO/CASP readiness utilities, and artifact gates under `runs/`.
- Mutable run state belongs under `.betelgeuze/`.
- Do not store Codex config in the current `.codex` path unless it is first resolved by the human owner; this repo currently has a file at `.codex`, not a config directory.
- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Active Safety Boundaries

- Do not revert unrelated dirty worktree changes.
- Do not stage, commit, push, delete, deploy, publish, submit to CASP, or mutate external state without explicit human confirmation.
- For the active CASP17 lane, use only the repo's internal torch/coarse-grain physics path.
- Do not use AlphaFold, ColabFold, ESMFold, OmegaFold, public/template structures, public PDB target lookups, or other-team models for active CASP17 work.
- CASP author code is runtime-only input. Do not store it in committed docs, configs, prompts, task specs, or state.

## Codex Goal Mode

- Keep the active goal in Codex native goal mode.
- Do not add or run repository-local autonomous drivers.
- Use `docs/ai/prompts/codex_pursue_goal_start.md` as the start-prompt shape for future goal-mode work.
- Use `docs/ai/tasks/TASK-TEMPLATE.md` for R1+ task specs when the scope is not already clear from a linked issue or work queue.
- Keep Codex-authored task specs short: goal, scope, likely files, and verification only.
- For Cursor delegation, create a run-specific prompt under `docs/ai/dispatch/` and call `./scripts/ai-worker-cursor.sh <prompt-file>`.
- For OpenCode-named delegation, create a run-specific prompt under `docs/ai/dispatch/` and call `./scripts/ai-worker-opencode.sh <prompt-file>`; this compatibility wrapper currently routes the assignment to Cursor Composer 2.5 instead of invoking OpenCode.
- Use one worker slice at a time. Codex reviews the worker summary first and opens full logs/diffs only when the summary, risk level, or tests require it.

## Delegation Bias

- At the start of each non-trivial task, Codex should explicitly choose one path: direct implementation, OpenCode worker slice, or Cursor worker slice.
- Bias toward using a worker when the work is broad, repetitive, uncertain, or likely to benefit from independent exploration before Codex final review.
- Consider Cursor as the default implementation worker for scoped code/test changes, repeated test repair, multi-file edits, and work where IDE-attached context may help.
- OpenCode-named broad repository exploration, broad grep/sweep, long-log review, large mechanical documentation/code updates, or other large-context passes currently run through Cursor Composer 2.5 via the compatibility wrapper.
- Codex may still handle narrow single-file fixes, obvious docs edits, tiny tests, and urgent safety corrections directly.
- Delegation does not change ownership: Codex still defines the slice, preserves safety boundaries, reviews the worker summary, inspects targeted hunks when needed, runs verification, and decides completion.

## Worker Selection

- Prefer Cursor for most scoped implementation slices, especially code/test edits, local repair loops, and IDE-attached edits where open files, selections, and current editor state matter.
- Treat OpenCode-named broad repository sweeps, long logs/docs, large mechanical edits, and large-context exploration as Cursor Composer 2.5 assignments unless the human owner explicitly restores direct OpenCode execution.
- Do not delegate truly small tasks: simple docs, tiny tests, obvious single-file fixes, or changes that Codex can safely complete faster than creating and reviewing a worker slice.
- Delegate broad exploration, repeated test repair, multi-file refactors, and mechanical work once it crosses the Delegation Bias thresholds.
- Workers implement; they do not redesign, broaden scope, decide completion, or change safety boundaries.
- Workers own local exploration, implementation, focused tests, and a concise return summary.
- Worker returns must not include full logs. They should include changed files, tests run, failed test names, key diff summary, and blockers.
- Codex should avoid reading full logs or full diffs by default; inspect targeted files or hunks only after the worker summary identifies a reason.

## Worker Web Access

- OpenCode and Cursor worker prompts must declare whether web access is disabled or enabled for the slice.
- Use web search/fetch only for scoped research, standards, dependency/API documentation, or commercial-readiness evidence collection.
- Do not use web search/fetch for active CASP17 target lookup, public/template/native structures, other-team models, secrets, `.env` content, author codes, or external mutation.
- Worker web findings are advisory evidence only until Codex reviews the sources and incorporates them into the accepted diff or audit.

## Verification

- Run `./scripts/ai-verify.sh` before marking orchestration or worker-driven work complete.
- For code changes, also run focused tests matching the changed files.
- Use `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` for product-readiness smoke checks.
- Use `AI_VERIFY_MODE=full ./scripts/ai-verify.sh` only when a full local pytest run is appropriate.

## Review Priority

Flag P0/P1 issues for:

- data loss or corruption
- secret, token, author-code, or PII leakage
- CASP rule or no-leak boundary violations
- external state mutation without approval
- unsafe execution enablement
- authorization or permission bypass
- missing tests for changed behavior
- scope drift from the task spec or active goal

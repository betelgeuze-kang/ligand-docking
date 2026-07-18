# AGENTS.md

## Role Contract

This repository is operated with Codex native goal mode. Codex performs design, implementation, review, verification, and final acceptance directly, with optional Codex internal subagents for bounded parallel work.

- Codex owns goal tracking through its native goal feature, plus design, task slicing, review, verification, and final acceptance.
- Kiro/Opus, Cursor, and Cursor-routed OpenCode wrappers are not part of the active agent workflow and must not be invoked by repository policy.
- Codex internal subagents may be used only for scoped, disjoint work; Codex remains responsible for all review and acceptance.
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
- For next-code-improvement goals, Codex defines one scoped slice, implements it directly, and verifies it before proceeding.
- Codex may use one or more internal subagents only when parallel, disjoint work materially improves speed or review quality.
- Codex reviews internal-subagent summaries first and opens full logs/diffs only when the summary, risk level, or tests require it.

## Implementation Bias

- At the start of each non-trivial task, Codex explicitly chooses direct implementation or a bounded internal-subagent slice.
- Prefer direct implementation for code, tests, docs, repair loops, and security-sensitive evidence contracts.
- Use internal subagents for disjoint exploration, mechanical work, or independent review only when that materially helps.
- Delegation never changes ownership: Codex defines the slice, preserves safety boundaries, reviews targeted hunks, runs verification, and decides completion.

## Internal Subagent Selection

- Do not delegate simple docs, tiny tests, obvious single-file fixes, or security-sensitive final decisions.
- Internal subagents do not redesign, broaden scope, decide completion, or change safety boundaries.
- Internal subagents return changed files, tests run, failed test names, a concise diff summary, and blockers without full logs.
- Keep write scopes disjoint when multiple internal subagents run concurrently.

## Web Access

- Use web search/fetch only for scoped research, standards, dependency/API documentation, or commercial-readiness evidence collection.
- Do not use web search/fetch for active CASP17 target lookup, public/template/native structures, other-team models, secrets, `.env` content, author codes, or external mutation.
- Internal-subagent web findings are advisory until Codex reviews the sources and incorporates them into the accepted diff or audit.

## Verification

- Run `./scripts/ai-verify.sh` before marking orchestration or code work complete.
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

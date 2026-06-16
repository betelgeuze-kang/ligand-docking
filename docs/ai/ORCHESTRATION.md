# Codex Goal Orchestration

This repository uses Codex native goal mode as the only progress owner. The repo keeps a small orchestration layer for rules, worker handoff, and verification:

```text
Human goal in Codex
-> Codex goal mode tracks progress and writes a short task spec when needed
-> optional Cursor/OpenCode worker explores, implements, tests, and summarizes one slice
-> local verification
-> Codex reviews summary first, then only targeted diff/logs as needed
```

There is no repository-local autonomous runner. Do not add local goal runners or background driver scripts.

## Roles

- Codex: native goal tracking, short task specs, risk boundaries, targeted review, and final acceptance.
- OpenCode: broad or large-context exploration, implementation, focused tests, and concise summary.
- Cursor: IDE-attached exploration, implementation, focused tests, and concise summary.
- `scripts/ai-verify.sh`: local smoke verification for orchestration and optional project gates.
- Human owner: push, merge, deployment, publication, CASP submission, production mutation, billing, and final accountability.

## Standard Flow

1. Read `AGENTS.md`, `.betelgeuze/state.md`, and the relevant task/work-queue file.
2. For R1+ work, write or update a short task spec under `docs/ai/tasks/`.
3. Decide whether delegation will save Codex context.
4. If delegating, write a run-specific prompt in `docs/ai/dispatch/` and require the worker to explore, implement, test, and summarize.
5. Run exactly one worker wrapper.
6. Review the worker summary before opening full logs or large diffs.
7. Inspect only targeted files/hunks unless risk or failure requires broader review.
8. Run `./scripts/ai-verify.sh` plus focused tests for changed behavior when Codex is doing final acceptance.
9. Continue, split the task, or stop with an explicit blocker.

## Delegation Threshold

Do not delegate:

- expected changes under roughly 100-200 LOC
- simple docs edits
- tiny or obvious test fixes
- clear single-file changes
- tasks where writing the worker prompt would cost as much as doing the work

Delegate:

- broad repository exploration
- large mechanical edits
- repeated test-fix cycles
- multi-file refactors
- long logs/docs where the worker can summarize
- implementation slices where the worker can run focused tests and return a compact result

## Short Task Spec

Codex-authored specs should usually stay under 40 lines and include only:

- goal
- scope and non-goals
- likely files or search targets
- verification command(s)
- safety boundaries or stop conditions

Do not paste long state files, full logs, or broad background into worker prompts. Link paths and make the worker inspect locally.

## Risk Routing

- R0: docs, comments, tiny local-only edits. Spec optional; smoke verify is enough.
- R1: normal code/test changes. Task spec recommended; focused tests required.
- R2: feature slice, API/worker behavior, artifact gates. Task spec required; focused tests and review required.
- R3: auth, execution enablement, privacy, destructive operations, broad refactors, CASP local readiness changes. Task spec and deep review required.
- R4: CASP submission, external mutation, production mutation, publication/release. Human approval required before any external action.

## CASP17 Boundary

- Current CASP17 work is local readiness only unless the human explicitly approves submission.
- Do not fetch or use public/template/native structures, other-team models, or external predictors for active CASP17 work.
- Do not store CASP author code in docs, config, prompt files, state, trace, or commits.
- Treat internal packets as local evidence, not official CASP performance evidence.

## Worker Rules

- Prompt files are used instead of passing large prompt bodies as shell arguments.
- Workers are responsible for local exploration before editing.
- Workers are responsible for running focused tests when safe and available.
- Workers must return concise summaries, not full logs.
- Worker summaries should include changed files, tests run, failed test names, key diff summary, blockers, and web URLs if web access was enabled.
- Each dispatch prompt must declare `Web access: disabled` or `Web access: enabled`.
- Web access is enabled only for scoped research, standards, dependency/API documentation, or commercial-readiness evidence collection.
- Web access must stay disabled for pure implementation slices unless the task explicitly requires current external evidence.
- Workers must not read `.env` files.
- Workers must not run push, merge, deploy, publish, release, production migration, billing, cloud mutation, permission escalation, deletion, or CASP submission commands.
- Worker output is untrusted until Codex reviews it.
- If a worker needs a broader design change, it must stop and report the blocker.

## Codex Review Budget

Codex should read in this order:

1. Worker summary.
2. Changed file list.
3. Failed test names and short failure snippets.
4. Targeted diff hunks for risky or surprising changes.
5. Full logs or full diffs only when needed.

For low-risk worker slices with passing focused tests, Codex should avoid re-reading long logs and should keep acceptance review targeted.

## Verification Modes

```bash
./scripts/ai-verify.sh
AI_VERIFY_MODE=product ./scripts/ai-verify.sh
AI_VERIFY_MODE=full ./scripts/ai-verify.sh
```

Default mode verifies orchestration files and Python syntax for local guard scripts. Product mode also runs existing product quality/readiness smoke checks. Full mode runs the local pytest suite and should be used deliberately.

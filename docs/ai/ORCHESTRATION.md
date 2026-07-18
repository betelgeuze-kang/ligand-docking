# Codex Goal Orchestration

This repository uses Codex native goal mode as the only progress owner. The repo keeps a small orchestration layer for rules, optional internal-subagent handoff, and verification:

```text
Human goal in Codex
-> Codex goal mode tracks progress and writes a short task spec when needed
-> Codex designs and implements one scoped slice directly
-> optional Codex internal subagent explores or implements a bounded, disjoint slice
-> local verification
-> Codex reviews targeted diffs/logs and decides acceptance
```

There is no repository-local autonomous runner. Do not add local goal runners or background driver scripts.

## Roles

- Codex: native goal tracking, design, implementation, short task specs, risk boundaries, targeted review, verification, and final acceptance.
- Codex internal subagent: optional bounded worker for disjoint exploration, mechanical implementation, focused tests, or independent review. It cannot decide completion.
- `scripts/ai-verify.sh`: local smoke verification for orchestration and optional project gates.
- Human owner: push, merge, deployment, publication, CASP submission, production mutation, billing, and final accountability.

Kiro/Opus, Cursor, and Cursor-routed OpenCode wrappers are retained only as inactive compatibility artifacts. Repository policy must not invoke them.

## Standard Flow

1. Read `AGENTS.md`, `.betelgeuze/state.md`, and the relevant task/work-queue file.
2. For R1+ work, write or update a short task spec under `docs/ai/tasks/`.
3. Codex chooses the smallest safe implementation slice and records explicit non-goals and stop conditions.
4. Codex implements directly. Use an internal subagent only when its scope is bounded and disjoint and delegation materially helps.
5. Review internal-subagent summaries before opening full logs or large diffs.
6. Inspect targeted files/hunks unless risk or failure requires broader review.
7. Run `./scripts/ai-verify.sh` plus focused tests for changed behavior.
8. Continue, split the task, or stop with an explicit blocker.

## Internal Subagent Threshold

Do not delegate:

- expected changes under roughly 100-200 LOC
- simple docs edits
- tiny or obvious test fixes
- clear single-file changes
- tasks where writing the worker prompt would cost as much as doing the work

Consider an internal subagent for:

- broad repository exploration
- large mechanical edits
- repeated test-fix cycles
- multi-file refactors
- long logs/docs where the worker can summarize
- implementation slices where disjoint ownership and a compact return summary are possible

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

## Internal Subagent Rules

- Internal subagent prompts should follow `docs/ai/prompts/internal_subagent_worker_slice.md`.
- Internal subagents are responsible for local exploration before editing and focused tests when safe.
- They must return concise summaries with changed files, tests, failures, key diff, blockers, and any web URLs used.
- Web access is enabled only for scoped research, standards, dependency/API documentation, or commercial-readiness evidence collection.
- Web access must stay disabled for pure implementation slices unless the task explicitly requires current external evidence.
- Internal subagents must not read `.env` files or run push, merge, deploy, publish, release, production migration, billing, cloud mutation, permission escalation, deletion, or CASP submission commands.
- Internal-subagent output is untrusted until Codex reviews it. A broader design need is a stop condition.

## Codex Review Order

Codex should read in this order:

1. Internal-subagent summary, when used.
2. Changed file list.
3. Failed test names and short failure snippets.
4. Targeted diff hunks for risky or surprising changes.
5. Full logs or full diffs only when needed.

For low-risk internal-subagent slices with passing focused tests, Codex should avoid re-reading long logs and keep acceptance review targeted.

## Verification Modes

```bash
./scripts/ai-verify.sh
AI_VERIFY_MODE=product ./scripts/ai-verify.sh
AI_VERIFY_MODE=full ./scripts/ai-verify.sh
```

Default mode verifies orchestration files and Python syntax for local guard scripts. Product mode also runs existing product quality/readiness smoke checks. Full mode runs the local pytest suite and should be used deliberately.

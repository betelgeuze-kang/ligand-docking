# Code Review Guidelines

Lead with actionable findings. Focus on correctness, safety, regressions, missing tests, and scope drift.

## Priorities

- P0: data loss, secret leakage, unauthorized external mutation, CASP rule/no-leak violation, production-breaking regression.
- P1: incorrect behavior, unsafe execution enablement, missing authorization, major missing tests, task-spec mismatch.
- P2: smaller correctness risks, maintainability risks that affect future safety, incomplete edge-case handling.

## Ignore Unless Risky

- Pure formatting preference.
- Local style nits that do not affect behavior or maintainability.
- Broad refactor suggestions outside the task.

## Required Checks

- Diff is scoped to the active goal or task spec.
- New behavior has focused tests or an explicit reason tests are not useful.
- `./scripts/ai-verify.sh` was run, or the reason it could not run is documented.
- No `.env` contents, secrets, CASP author code, private keys, tokens, cookies, or PII were exposed.
- CASP work remains local-only unless human approval for external submission is explicit.

# OpenCode-Named Worker Slice: P0-2 Release CI ROCm Gate

## Task

Update the local GitHub Actions release CI wiring so the existing ROCm runtime smoke is no longer manual-only. Keep external runner registration, branch protection, and remote state mutation out of scope.

## Files In Scope

- `.github/workflows/product-image-smoke.yml`
- A small docs note only if needed to record external-state prerequisites for runner registration / required checks.

## Acceptance Criteria

- `product-image-smoke` has a weekly scheduled trigger for the ROCm runtime smoke.
- Release tag pushes run the ROCm runtime gate automatically.
- The build smoke does not accidentally run during the ROCm-only schedule/tag gate unless explicitly intended.
- Build and ROCm runtime jobs preserve receipt/log artifacts on failure with `if: always()`.
- The workflow still supports `workflow_dispatch` build and `workflow_dispatch` rocm-runtime modes.
- External requirements that cannot be changed locally are documented as blocked-by-human/external-state, not silently claimed green.

## Verification

- Validate YAML parse for `.github/workflows/product-image-smoke.yml`.
- Run `./scripts/ai-verify.sh`.
- Run `git diff --check`.

## Web Access

Web access: disabled

## Constraints

- Follow `AGENTS.md` and `docs/ai/ORCHESTRATION.md`.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not run push, merge, deploy, publish, release, production migration, billing, cloud mutation, permission escalation, deletion, or CASP submission commands.
- Do not use external predictors, public/template/native structures, public PDB target lookups, or other-team models.
- Keep the change focused on local workflow configuration and evidence docs.
- If a required change needs GitHub UI/API mutation or runner registration, stop and report it as a blocker.

## Return Format

Return at most 80 lines:

- changed files
- tests/checks run with pass/fail status
- failed test names, if any
- key diff summary in 10 bullets or fewer
- blockers or risks
- web sources consulted, only if web access was enabled

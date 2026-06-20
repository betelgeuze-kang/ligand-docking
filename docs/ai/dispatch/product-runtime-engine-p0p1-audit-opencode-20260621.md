# OpenCode Slice: Product Runtime / Engine P0-P1 Audit

Web access: disabled

## Goal

Audit the current dirty worktree against `AGENTS.md`, `docs/ai/ORCHESTRATION.md`, and
`docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md` to identify any remaining
P0/P1 blockers before Codex finalizes this slice.

## Scope

- Review the current local worktree only. Do not edit files.
- Focus on product runtime evidence, ROCm/HIP/Rust clean-container gating, result artifact
  content-type contracts, lazy job store behavior, runner shims, force-term result metadata,
  ONSPS/H-bond evidence, guarded residual policy caps, and product evidence bundle validation.
- Inspect existing artifacts under `runs/` only enough to confirm status and blockers.
- Check whether the current tests/verification named below are sufficient for the dirty files.

## Non-Goals

- Do not run push, deploy, release, publication, external mutation, billing, CASP submission,
  or destructive commands.
- Do not read `.env` or `.env.*` files.
- Do not broaden the roadmap or redesign architecture.
- Do not produce full logs in the summary.

## Suggested Commands

Use local inspection commands such as:

```bash
git status --short --branch
git diff --stat
python3 -m pytest -q tests/unit/test_betelgeuze_engine_guarded_residual.py tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_build_product_image_smoke_preflight.py tests/unit/test_build_product_release_source_of_truth_gate.py tests/unit/test_scripts_product_readiness_entrypoints.py
AI_VERIFY_MODE=product ./scripts/ai-verify.sh
```

If a command is too expensive or blocked, skip it and report why.

## Return Summary

Return only:

- P0/P1 findings, if any, with file paths and short reasons.
- Tests/verification run, with pass/fail.
- Whether there are unreviewed risky files Codex should inspect directly.
- Recommended next Codex action in one sentence.

# OpenCode Slice: H-Bond Chemistry/Pose Validator Audit

Web access: disabled

## Goal

Audit the current dirty diff that strengthens AI-MD chemistry and pose/ranking H-bond KPI validation.
Do not edit files.

## Scope

- Review changed files only:
  - `tools/product/build_ai_md_engine_kpi_report.py`
  - `tools/product/build_ai_md_product_evidence_bundle.py`
  - `tests/unit/test_build_ai_md_engine_kpi_report.py`
  - `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- Confirm the diff moves toward the active goal:
  - chemistry KPI rows carry real H-bond geometry/distance/angle evidence;
  - chirality/ring/protonation/tautomer raw fixture rows are validated, not just aggregate counts;
  - pose/ranking benchmark rows validate top-1 recovery, blocked decoys, overanchoring, unsatisfied evidence, and expected H-bond status;
  - product evidence bundle remains fail-closed.

## Non-Goals

- Do not edit files.
- Do not read `.env` or `.env.*`.
- Do not run push, deploy, publish, release, billing, cloud mutation, CASP submission, deletion, or destructive commands.
- Do not broaden architecture.

## Suggested Verification

```bash
python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py
AI_VERIFY_MODE=product ./scripts/ai-verify.sh
git diff --check
```

If a command is too expensive or blocked, skip it and report why.

## Return Summary

Return only:

- P0/P1 findings, if any, with file paths and short reasons.
- Tests/verification run, with pass/fail.
- Any risky unreviewed hunk Codex should inspect directly.
- Recommended next Codex action in one sentence.

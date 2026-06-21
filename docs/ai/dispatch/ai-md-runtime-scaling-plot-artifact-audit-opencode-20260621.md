# OpenCode Slice: Runtime Scaling Plot Artifact Audit

## Goal

Audit the current local diff for the AI-MD runtime neighbor-cap scaling SVG artifact gate.

## Scope

- Inspect only the current working tree diff relevant to:
  - `betelgeuze_engine/benchmark/runtime_scaling.py`
  - `betelgeuze_engine/benchmark/__init__.py`
  - `tools/product/build_ai_md_engine_kpi_report.py`
  - `tools/product/build_ai_md_product_evidence_bundle.py`
  - `tests/unit/test_betelgeuze_engine_scaffold.py`
  - `tests/unit/test_build_ai_md_engine_kpi_report.py`
  - `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- Check whether the SVG artifact is generated/reused safely, included as a required bundle artifact, validated through KPI metadata and PM summary mirrors, and covered by positive/negative tests.
- Web access: disabled.

## Constraints

- Do not stage, commit, push, delete, deploy, publish, submit, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not broaden scope beyond this audit.
- Prefer concise findings over full logs.

## Verification Context

Codex has already run:

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `python3 tools/product/build_ai_md_engine_kpi_report.py`
- `python3 tools/product/build_ai_md_product_evidence_bundle.py`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`
- `git diff --check`

## Return Summary

Return only:

- Findings, ordered by severity, with file/line references.
- Test gaps or residual risks.
- If no blocking issue is found, say that clearly.

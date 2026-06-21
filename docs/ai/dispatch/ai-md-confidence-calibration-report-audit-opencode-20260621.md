# OpenCode Slice: AI-MD Confidence Calibration Report Audit

You are an OpenCode implementation worker for this repository. Codex owns final design, verification, acceptance, commit/push decisions, and safety boundaries.

## Mode

Audit only. Do not edit files. Web access disabled.

## Safety Boundaries

- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not use web search/fetch.
- Do not run destructive commands.
- Do not commit, stage, push, publish, submit, deploy, or mutate external state.
- Do not inspect public CASP targets, public/template/native structures, other-team models, or author codes.

## Context

Codex added the Milestone D confidence calibration report for the AI-MD pose/H-bond benchmark.

Intended behavior:

- `betelgeuze_engine.validation.build_confidence_calibration_report()` builds `confidence_calibration_v1` with bins, ECE, Brier, class counts, and fail-closed blockers.
- `tools/product/build_ai_md_engine_kpi_report.py` adds top-level `confidence_calibration_report` and PM chemistry mirror fields.
- `tools/product/build_ai_md_product_evidence_bundle.py` fails closed when calibration report/schema/rows/bins/PM gate are missing or invalid.
- Current focused tests passed: `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py`
- Current product verify passed: `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`

## Files To Inspect

- `betelgeuze_engine/validation/confidence_calibration.py`
- `betelgeuze_engine/validation/__init__.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

## Audit Task

Look for P0/P1 bugs, claim-boundary regressions, missing fail-closed checks, schema compatibility breaks, or test holes that could allow a missing/invalid confidence calibration report to remain product claim-ready.

## Return Summary Only

Return:

1. Findings ordered by severity with file/line references.
2. Whether the implemented behavior matches the intended behavior.
3. Any focused test or validation gap worth fixing now.
4. Explicitly state if you found no P0/P1 issues.

Do not include full logs or full diffs.

# OpenCode Slice: Delta Backmap H-Bond Yellow-Band Audit

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

Codex implemented the PR-5 ONSPS/H-bond gap where large `delta_backmap` should trigger a yellow-band/abstention instead of silently allowing H-bond claim-safe evidence.

Intended behavior:

- `evaluate_hbond_evidence(..., delta_backmap=3.0, delta_backmap_max=2.5)` with otherwise valid geometry returns `claim_safe=False`, `status=review`, and `blocked_reason=delta_backmap_yellow_band`.
- Small finite `delta_backmap` keeps valid geometry claim-safe while lowering confidence slightly.
- H-bond claim metadata exposes `hbond_delta_backmap*` fields.
- KPI pose/H-bond benchmark includes a `delta_backmap_yellow_band_pose` row and requires `delta_backmap_yellow_band_abstention_ready=true`.
- Product evidence bundle validator fails closed if the delta yellow-band row/summary is missing.

## Files To Inspect

- `betelgeuze_engine/interactions/hbond_evidence.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `python3 tools/product/build_ai_md_engine_kpi_report.py`
- `python3 tools/product/build_ai_md_product_evidence_bundle.py`
- `python3 tools/product/build_ai_md_engine_kpi_report.py`
- `python3 tools/product/build_ai_md_product_evidence_bundle.py`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`
- `git diff --check`

## Audit Task

Look for P0/P1 bugs, claim-boundary regressions, missing fail-closed checks, schema compatibility breaks, or test holes that could allow a large `delta_backmap` to be treated as claim-safe.

## Return Summary Only

Return:

1. Findings ordered by severity with file/line references.
2. Whether the implemented behavior matches the intended behavior.
3. Any focused test or validation gap worth fixing now.
4. Explicitly state if you found no P0/P1 issues.

Do not include full logs or full diffs.

# OpenCode Slice: AI-MD Confidence Calibration Next Gap Audit

You are an OpenCode implementation worker for this repository. Codex owns final design, verification, acceptance, commit/push decisions, and safety boundaries.

## Mode

Audit only. Do not edit files. Web access disabled.

## Safety Boundaries

- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not use web search/fetch.
- Do not run destructive commands.
- Do not commit, stage, push, publish, submit, deploy, or mutate external state.
- Do not inspect public CASP targets, public/template/native structures, other-team models, or author codes.
- Preserve runner shim and `core/` compatibility boundaries.

## Context

Codex is continuing the product-grade AI-MD engine goal. Recent slices added:

- force-term `EnergyForces`/claim row contracts
- guarded `PocketWallTerm`
- runtime neighbor-cap scaling benchmark
- `delta_backmap` H-bond yellow-band abstention

Current Milestone D in `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md` requires:

- pose RMSD fixtures
- active/decoy ranking fixtures
- H-bond recovery fixtures
- over-anchoring false-positive fixtures
- runtime O(N) scaling plot/report
- confidence calibration report

Current `runs/ai_md_engine_kpi_report_current.json` has pose ranking/H-bond benchmark and runtime neighbor-cap scaling, but no explicit AI-MD confidence calibration report.

## Audit Task

Using only local repo evidence, decide whether the next smallest high-value implementation slice should be an AI-MD confidence calibration report attached to the existing pose/H-bond benchmark and product evidence bundle gates.

Inspect relevant files:

- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `betelgeuze_engine/interactions/hbond_evidence.py`

## Return Summary Only

Return:

1. Recommended next slice, one sentence.
2. Why it is the best next slice, tied to local docs/code.
3. Likely files to change.
4. Focused tests to add/run.
5. P0/P1 risks or blockers, if any.
6. Any lower-priority gaps explicitly left for later.

Do not include full logs or full diffs.

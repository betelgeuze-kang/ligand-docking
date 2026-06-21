# OpenCode Slice: AI-MD Post Confidence Next Gap Audit

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
- confidence calibration report and product bundle gates

Current `runs/ai_md_engine_kpi_report_current.json` and `runs/ai_md_product_evidence_bundle_current.json` are ready, and the PM failed gate list is empty.

Milestone D in `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md` now appears covered at KPI level:

- pose RMSD fixtures
- active/decoy ranking fixtures
- H-bond recovery fixtures
- over-anchoring false-positive fixtures
- runtime O(N) scaling plot/report
- confidence calibration report

But the runtime scaling evidence is currently mostly JSON/MD metric rows, not a first-class plot artifact.

## Audit Task

Using only local repo evidence, recommend the next smallest high-value implementation slice after confidence calibration. Decide whether to:

1. strengthen Milestone D by adding a first-class runtime scaling plot/report artifact and bundle validator gate, or
2. move to the next product/engine gap.

Inspect at least:

- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
- `runs/ai_md_engine_kpi_report_current.json`
- `runs/ai_md_product_evidence_bundle_current.json`
- `betelgeuze_engine/benchmark/runtime_scaling.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- focused tests under `tests/unit/test_build_ai_md_engine_kpi_report.py` and `tests/unit/test_build_ai_md_product_evidence_bundle.py`

Avoid recommending:

- GUI work
- commit/push work
- GitHub billing/Actions work
- external public benchmark fetches
- broad rewrites

## Return Summary Only

Return:

1. Recommended next slice, one sentence.
2. Why it is the best next slice, tied to local docs/code.
3. Likely files to change.
4. Focused tests to add/run.
5. P0/P1 risks or blockers, if any.
6. Lower-priority gaps explicitly left for later.

Do not include full logs or full diffs.

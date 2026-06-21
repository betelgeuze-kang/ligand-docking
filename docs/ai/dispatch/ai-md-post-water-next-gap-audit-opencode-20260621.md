# OpenCode worker slice: post-water next engine-promotion gap audit

Web access: disabled.

## Goal

Audit the current worktree after `WaterDisplacementProxyTerm` and identify the next highest-value gap toward the active objective:

```text
Product runtime -> Topology -> ForceTerm -> ONSPS Evidence -> Guarded Residual -> Benchmark
```

This is review-only. Do not edit files.

## Scope

Inspect only:

- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
- `runs/ai_md_engine_kpi_report_current.json`
- `runs/ai_md_product_evidence_bundle_current.json`
- `betelgeuze_engine/`
- `core/forcefield.py`, `core/topology.py`, `core/onsps_backmap.py`
- `betelgeuze_engine/product/runners/`
- `tools/run_ligand_htvs_pipeline.py`
- `tools/run_ligand_backmapping_scoring.py`
- `tools/run_ligand_topk_delivery.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- relevant unit tests under `tests/unit/`

## Review questions

- Which objective segment is already strongly proven by current code/evidence: product runtime, topology, force terms, ONSPS evidence, guarded residual, benchmark?
- Which remaining segment has the weakest current proof or missing gate?
- Do existing runner shims preserve the allowlisted paths?
- Does `core/` remain a compatibility layer rather than being removed?
- Do product runners call canonical `betelgeuze_engine` modules directly where they should, or do they still depend on legacy `core/` paths in ways that block the transition plan?
- Are there missing KPI/bundle gates that would let a claimed segment pass on weak evidence?
- Suggest exactly one next implementation slice that is bounded enough for Codex to complete next.

## Return format

Return a concise summary only:

- strongest proven segments
- weakest/missing segment
- concrete next slice
- likely files
- focused verification commands
- P0/P1 risks, if any

Do not read `.env*`. Do not commit, push, delete, deploy, upload, or mutate external state.

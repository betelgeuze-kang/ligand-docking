# OpenCode Worker Slice: Post-AdResS Product Engine Gap Audit

Web access: disabled.

You are a scoped implementation/audit worker. Codex owns final design, review, verification, and acceptance.

## Goal

Inspect the current repository state after the AdResS production-blocked KPI gate work and identify the next highest-value product-engine gap that should be implemented without breaking existing runner paths or `core/` compatibility.

## Context

Use these local references:

- `AGENTS.md`
- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
- `runs/ai_md_engine_kpi_report_current.json`
- `runs/ai_md_product_evidence_bundle_current.json`
- `betelgeuze_engine/contracts/result.py`
- `betelgeuze_engine/physics/forcefield.py`
- `betelgeuze_engine/topology/validity.py`
- `betelgeuze_engine/interactions/hbond_evidence.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- focused tests under `tests/unit/`

## Safety Boundaries

- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not stage, commit, push, delete, deploy, submit, or mutate external state.
- Do not use AlphaFold, ColabFold, ESMFold, OmegaFold, public/template structures, public PDB target lookups, or other-team models.
- Preserve existing runner shim paths:
  - `tools/run_ligand_htvs_pipeline.py`
  - `tools/run_ligand_backmapping_scoring.py`
  - `tools/run_ligand_topk_delivery.py`
- Preserve `core/` as compatibility layer.

## Task

Do a broad but concise audit only. Prefer no code edits unless you find a tiny, obviously safe test/metadata fix that directly advances the objective.

Find the strongest next implementation slice among these product-engine principles:

1. all physical terms return energy + forces + diagnostics + claim metadata;
2. all corrections/residuals are bounded and abstainable;
3. engine aggregate results carry claim-safe metadata;
4. PM-visible KPI gates prove runtime, physics, chemistry, and product readiness;
5. clean ROCm/HIP/Rust product runner evidence remains green;
6. `core/` and runner shims are compatibility layers, not product claims.

## Return Summary Only

Return a concise summary with:

- recommended next slice title;
- why it is the highest-value remaining gap;
- exact files likely involved;
- current evidence that proves it is incomplete or weak;
- suggested focused tests/commands;
- any P0/P1 risks.

Do not include full logs.

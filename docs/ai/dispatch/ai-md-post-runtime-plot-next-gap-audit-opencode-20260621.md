# OpenCode Slice: Post Runtime Plot Next Gap Audit

## Goal

Audit the current working tree and product evidence to identify the next highest-value implementation slice for the active AI-MD product runtime/engine goal after the runtime scaling plot artifact gate.

## Scope

- Inspect current repo state and these evidence/docs:
  - `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`
  - `runs/ai_md_engine_kpi_report_current.json`
  - `runs/ai_md_product_evidence_bundle_current.json`
  - `runs/product_image_smoke_preflight_current.json`
  - `runs/rocm_environment_manifest_current.json`
  - current diffs in `betelgeuze_engine/`, `tools/product/`, and relevant `tests/unit/`
- Focus on gaps that move the requested end state forward:
  - runner shims preserved
  - `core/` compatibility retained
  - all force terms return energy + force + metadata
  - all corrections bounded
  - claim-safe metadata attached to engine results
  - PM-facing Runtime/Physics/Chemistry/Product KPI gates
  - ROCm/HIP/Rust product path, no CPU fallback promotion
- Web access: disabled.

## Constraints

- Audit only. Do not edit files.
- Do not stage, commit, push, delete, deploy, publish, submit, or mutate external state.
- Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not broaden into GUI work.
- Prefer one implementable slice that is high-value and small enough for Codex to complete next.

## Return Summary

Return only:

- Current evidence status in 3-5 bullets.
- Top 3 remaining gaps, ordered by product risk.
- Recommended next slice with likely files and focused verification.
- Any P0/P1 blocker if present.

# OpenCode Worker Slice: ROCm/HIP/Rust Product Gate Audit

## Goal

Audit the current uncommitted AI-MD product-runtime/engine changes for product-claim leaks and implement only a small focused fix if one is clearly required.

The product lane must stay GPU-first: ROCm/HIP/Rust evidence may support product-readiness claims; CPU-only execution must not unlock product readiness.

## Scope

- Inspect the current uncommitted changes, excluding `AGENTS.md`.
- Focus on:
  - `betelgeuze_engine/backmapping/`
  - `betelgeuze_engine/interactions/`
  - `betelgeuze_engine/physics/`
  - `betelgeuze_engine/topology/`
  - `tools/product/build_ai_md_engine_kpi_report.py`
  - `tools/product/build_ai_md_product_evidence_bundle.py`
  - `tools/product/build_product_image_smoke_preflight.py`
  - `tools/product/run_ligand_backmapping_scoring.py`
  - related unit tests
- Check that new topology, ONSPS, H-bond, ligand validity, and clean-container gates are fail-closed and schema-versioned where product evidence depends on them.
- If a narrow issue is found, patch it with the smallest change and add or update focused tests.

## Boundaries

- Web access: disabled.
- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not edit `AGENTS.md`.
- Do not commit, stage, push, delete, deploy, publish, or mutate external state.
- Do not use AlphaFold, ColabFold, ESMFold, OmegaFold, public/template structures, public PDB target lookups, or other-team models.
- Keep the worker slice implementation-only. Do not redesign the product gate or broaden scope.

## Suggested Verification

Run focused checks that match any files touched. If no code changes are needed, run at least:

```bash
python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_build_product_image_smoke_preflight.py tests/unit/test_run_ligand_backmapping_scoring.py tests/unit/test_run_ligand_backmapping_scoring_cli.py
git diff --check
```

## Return Summary

Return only:

- changed files
- whether any issue was found
- tests run and pass/fail
- key diff summary
- blockers or residual risks

# OpenCode Worker Slice: Runtime Neighbor-Cap Scaling Audit

## Mode

Audit only. Do not edit files.

## Web Access

Disabled. Use only local repository context. Do not read `.env`, `.env.*`, `*.env`, or `*.env.*`.

## Context

Codex added a local benchmark surface for the Benchmark phase after Topology, ForceTerm, ONSPS Evidence, and Guarded Residual work. The new gate is intentionally named `runtime_neighbor_cap_scaling`: it proves the provided capped-neighbor path has linear neighbor-pair growth and records measured timing rows, without overstating that the current dense `NeighborPairs` representation proves full runtime O(N).

Relevant changed files for this slice:

- `betelgeuze_engine/benchmark/__init__.py`
- `betelgeuze_engine/benchmark/runtime_scaling.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `runs/ai_md_engine_kpi_report_current.json`
- `runs/ai_md_engine_kpi_report_current.md`
- `runs/ai_md_product_evidence_bundle_current.json`
- `runs/ai_md_product_evidence_bundle_current.tar.gz`

## Audit Scope

Review whether:

- The benchmark uses `ProductForceField.energy_forces()` with provided neighbor pairs.
- It records positive timing rows but gates readiness on capped neighbor-pair scaling, finite outputs, claim-safe metadata, and provided-neighbor diagnostics.
- The KPI report exposes `runtime_kpi.neighbor_cap_scaling` and PM runtime fields.
- The product evidence bundle validator fails closed when the scaling packet, rows, or PM gate are missing/invalid.
- The implementation avoids overclaiming full runtime O(N) given the current dense neighbor-pair tensor representation.
- No runner shim, `core/` compatibility path, product Docker/runtime gate, or external state is weakened.

## Verification Already Run By Codex

- `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_engine_transition_shims.py` -> `124 passed, 1 warning`
- `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` -> `verify ok (product)`
- `python3 tools/product/build_ai_md_engine_kpi_report.py` -> `status=ai_md_engine_kpi_report_ready`
- `python3 tools/product/build_ai_md_product_evidence_bundle.py` -> `status=ai_md_product_evidence_bundle_ready`
- `git diff --check` -> clean

## Return Summary Format

Return only:

- P0/P1 findings, if any, with file and line references.
- Test gaps or residual risks.
- Whether the verification list is sufficient for this slice.
- Do not include full logs.

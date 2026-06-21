# OpenCode Slice: Runtime Neighbor-Cap Scaling Audit

Web access: disabled.

Goal: audit consistency for the runtime neighbor-cap scaling P0 update. Do not edit files.

Scope:
- `betelgeuze_engine/benchmark/runtime_scaling.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

Context:
- Runtime scaling should now use product-safe cell-list neighbor evidence, not the old dense/window `"provided"` row source.
- Expected row source is `"provided_cell_list"`.
- Evidence should fail closed when neighbor cap overflows.
- Runtime evidence should surface and gate:
  - `nxn_allocation_observed is False`
  - `memory_per_atom_linear_ready is True`
  - `max_memory_peak_mb_per_atom > 0`
  - `total_rebuild_count > 0`
  - row `neighbor_provider_status == "neighbor_provider_ready"`
  - row `neighbor_provider_overflow is False`
  - row `nxn_allocation_observed is False`
  - row `memory_peak_mb_per_atom > 0`

Return summary only:
- missing code/test updates, if any
- risky assumptions in the current runtime memory gate
- exact files/line hints for Codex to inspect
- tests you recommend Codex run

Do not stage, commit, push, delete, or mutate external state.

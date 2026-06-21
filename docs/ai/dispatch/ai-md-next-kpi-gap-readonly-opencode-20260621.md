# OpenCode Worker Slice: AI-MD Next KPI Gap Read-Only Audit

Web access: disabled.

You are a scoped read-only implementation-audit worker. Do not edit, stage, commit, push, delete, run external mutations, or read `.env*`.

Context:
- The repository is moving toward product-grade AI-MD runtime/core engine readiness.
- Keep existing allowlisted runner paths as shims.
- Keep `core/` as a compatibility layer.
- Force terms must return energy, forces, diagnostics, and claim metadata.
- Corrections must be bounded.
- Product and PM KPI surfaces must expose runtime, physics, chemistry, and product gates.
- Current worktree may contain Codex edits around force-term term-set PM KPI exposure. Do not modify them.

Task:
1. Read `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`.
2. Inspect the current KPI and evidence-bundle surfaces:
   - `tools/product/build_ai_md_engine_kpi_report.py`
   - `tools/product/build_ai_md_product_evidence_bundle.py`
   - relevant `tests/unit/test_build_ai_md_*`
   - relevant `betelgeuze_engine` modules only as needed.
3. Identify the single best next narrow gap after the current force-term term-set PM exposure work.

Return only a concise summary:
- Recommended next slice title.
- Why it is the highest aligned next step.
- Likely files to change.
- Exact verification commands.
- Risks/blockers.

Do not include full logs or broad diffs.

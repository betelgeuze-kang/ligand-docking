# OpenCode Slice: AI-MD Evidence Handoff Freshness Audit

Web access: disabled.

## Goal

Audit the current AI-MD KPI/product evidence handoff for stale-artifact, self-reference, or false-green risks while preserving the hard rule that product claim remains blocked until a clean ROCm/HIP/Rust container receipt exists.

## Scope

Read only. Do not edit, stage, commit, push, delete, install, run Docker, mutate external state, or read any `.env*` files.

Inspect:

- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tools/product/build_product_image_smoke_preflight.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- `runs/ai_md_engine_kpi_report_current.json`
- `runs/ai_md_product_evidence_bundle_current.json`
- `runs/product_image_smoke_preflight_current.json`
- `docs/ai_md_product_runtime_engine_next_steps_2026-06-18.md`

## Audit Questions

1. Can the current KPI or bundle look ready while source artifacts have changed after bundle export?
2. Does the current `source_artifacts_fresh` signal cover all included bundle artifacts without changing immutable tar validation semantics?
3. Does any summary field imply product readiness despite `clean_container_smoke_ready=false` or `docker_cli_missing`?
4. Is there a minimal additional code/test change that would reduce false-green risk before Docker becomes available?
5. If no patch is needed, name the strongest remaining blocker and the exact current evidence proving it.

## Verification Commands

Use focused checks only:

```bash
python3 -m pytest -q tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_build_ai_md_engine_kpi_report.py
python3 tools/product/build_ai_md_engine_kpi_report.py
python3 tools/product/build_ai_md_product_evidence_bundle.py
python3 -c "import json; k=json.load(open('runs/ai_md_engine_kpi_report_current.json')); b=json.load(open('runs/ai_md_product_evidence_bundle_current.json')); print(k['pm_kpi_summary']['failed_gate_ids']); print(b['summary']['source_artifacts_fresh'], b['summary']['product_claim_ready'], b['blockers'])"
```

## Return Summary

Return concise summary only:

- files inspected
- commands run and pass/fail
- P0/P1 findings, if any
- recommended minimal patch, if any
- specific line references Codex should inspect

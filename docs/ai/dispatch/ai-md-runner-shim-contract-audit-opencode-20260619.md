# OpenCode Slice: Runner Shim Contract Audit

Web access: disabled.

## Goal

Audit whether the current product runner transition preserves the legacy allowlisted runner paths while proving they route through the product engine runner adapters.

## Scope

Read only. Do not edit, stage, commit, push, delete, or mutate external state.

Check these files and nearby tests only:

- `api/validated_runner.py`
- `tools/run_ligand_htvs_pipeline.py`
- `tools/run_ligand_backmapping_scoring.py`
- `tools/run_ligand_topk_delivery.py`
- `betelgeuze_engine/product/runners/`
- `config/api_validated_runner_profiles/*.json`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tests/unit/test_engine_transition_shims.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`

## Audit Questions

1. Do the three legacy `tools/run_ligand_*.py` paths still exist and remain allowlisted?
2. Do the legacy paths behave as compatibility shims to `betelgeuze_engine.product.runners.*`?
3. Do profile `runner_script_sha256` values still match the allowlisted shim files?
4. Does the KPI report fail closed if a shim merely contains the adapter import string but does not expose the same runtime symbols?
5. Are there any obvious gaps in this evidence that could let a runner path drift away from the product adapter without tests/KPI catching it?

## Verification Commands

Prefer these focused checks:

```bash
python3 -m pytest -q tests/unit/test_engine_transition_shims.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_api_validated_runner_adapter.py
python3 tools/product/validate_api_runner_profiles.py --profiles-dir config/api_validated_runner_profiles --out-json /tmp/api_runner_profiles_validate_current.json
```

## Return Summary

Return a concise summary only:

- files inspected
- commands run and pass/fail
- P0/P1 findings, if any
- non-blocking observations
- whether Codex should inspect any specific file/line

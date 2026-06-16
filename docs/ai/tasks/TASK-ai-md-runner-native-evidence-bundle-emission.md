# Task: AI-MD Runner Native EvidenceBundle Emission

## Context

Validated-runner support for `evidence_bundle_template` exists, and profile promotion readiness now blocks delivery/proxy-refinement profiles that do not declare native EvidenceBundle emission.

Current local blockers:

- `runs/api_runner_profile_promotion_readiness_current.json`
  - `status=blocked_api_runner_profile_promotion_readiness`
  - `native_evidence_bundle_required_profile_count=3`
  - `native_evidence_bundle_missing_profile_count=3`
  - `first_native_evidence_bundle_missing_profile_id=backmapping_scoring.production`

The goal of this slice is to remove the native-template blocker honestly: profiles should declare a template only after their runner can actually produce a valid `EvidenceBundle` at that path.

## Files In Scope

- `config/api_validated_runner_profiles/*.json`
- `tools/product/run_ligand_backmapping_scoring.py`
- `tools/run_ligand_htvs_pipeline.py`
- `tools/product/run_ligand_topk_delivery.py`
- `betelgeuze_ai_md/contracts/*` only if a small reusable writer helper is useful
- focused tests under `tests/unit/`

## Requirements

- Add opt-in native EvidenceBundle output support for all enabled delivery/proxy-refinement runner profiles:
  - `backmapping_scoring.production`
  - `ligand_htvs_pipeline_default`
  - `ligand_topk_delivery.production`
- Profiles must declare:
  - `"evidence_bundle_template": "{job_results_dir}/evidence_bundle.json"`
  - runner arguments that pass the rendered `{evidence_bundle}` path to the runner.
- Runners must write a contract-valid `EvidenceBundle` only when the new output argument is provided.
- Native bundle generation must remain review-only/fail-closed:
  - no customer-facing claim widening
  - no external fetches
  - no docking/GPU jobs beyond existing runner behavior
  - `claim_safe=false` unless existing downstream delivery/topology/interaction gates prove otherwise
- Keep disabled/example profile behavior conservative; do not make disabled profiles promotion-ready.
- Preserve runner profile readiness hash checks. If the actual `runner_script` file changes, update the corresponding profile `runner_script_sha256` only for that script.

## Suggested Approach

- Prefer reusing `betelgeuze_ai_md.contracts.api_adapter.write_api_evidence_bundle`.
- Build the small `result_manifest` needed by the adapter from:
  - result file path
  - result file sha256
  - sanitized/read request JSON
  - runner metadata available inside the script
- Add tests proving:
  - enabled repo profiles all declare native EvidenceBundle templates
  - promotion readiness native missing count becomes `0`
  - at least one runner writes a valid native EvidenceBundle path when invoked with the new option

## Verification

Run focused checks:

```bash
python3 -m py_compile tools/product/run_ligand_backmapping_scoring.py tools/run_ligand_htvs_pipeline.py tools/product/run_ligand_topk_delivery.py tools/product/validate_api_runner_profiles.py tools/product/build_api_runner_profile_promotion_readiness.py tools/product/build_api_runner_profile_enablement_work_order.py
python3 -m pytest -q tests/unit/test_build_api_runner_profile_promotion_readiness.py tests/unit/test_api_runner_profile_enablement_work_order.py tests/unit/test_api_validated_runner_adapter.py
python3 tools/product/build_api_runner_profile_promotion_readiness.py
python3 tools/product/build_api_runner_profile_enablement_work_order.py
```

Codex will run broader release/source checks after review.

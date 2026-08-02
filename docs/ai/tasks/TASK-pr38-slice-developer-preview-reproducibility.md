# TASK-pr38-slice-developer-preview-reproducibility: Developer Preview Reproducibility Slice

## Goal

Extract Developer Preview reproducibility gates into a child PR that makes clean checkout, Windows/platform reproducibility, and new-user workflow observation blockers visible through fail-closed receipts.

## Scope

- Clean-checkout benchmark and silent-import-loss receipts.
- Platform/Windows reproducibility receipt surfaces.
- New-user workflow observation receipt and final Developer Preview gate audit.
- Large-model/OOM, unattended execution, support bundle, and on-prem readiness blockers where they affect Developer Preview exit criteria.

## Non-goals

Do not claim Developer Preview exit, paid-pilot readiness, enterprise/on-prem readiness, unattended execution readiness, or broad product readiness unless the required observations and receipts are attached and fresh.

## Likely Files Or Search Targets

`docs/developer_preview_*.md`, `tools/product/build_developer_preview_*.py`, `tools/product/build_restricted_unattended_execution_readiness.py`, `tools/product/build_enterprise_on_prem_readiness_gate.py`, `tools/product/build_support_bundle.py`, `tests/unit/test_build_developer_preview_*.py`, `tests/unit/test_build_restricted_unattended_execution_readiness.py`, `tests/unit/test_build_enterprise_on_prem_readiness_gate.py`, `tests/unit/test_build_support_bundle.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_build_developer_preview_clean_checkout_benchmark_receipt.py tests/unit/test_build_developer_preview_platform_reproducibility_receipt.py tests/unit/test_build_developer_preview_new_user_observation_receipt.py tests/unit/test_build_developer_preview_final_gate_audit.py`.

Run focused tests for any additional touched Developer Preview gate modules.

Run `./scripts/ai-verify.sh`.

Run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` when this slice updates product-readiness or final-gate artifacts.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if a missing clean-checkout, Windows/platform, or new-user observation receipt is hidden behind green wording.
- Stop if this slice mutates external systems or requires deployment.

## Risk Level

R2

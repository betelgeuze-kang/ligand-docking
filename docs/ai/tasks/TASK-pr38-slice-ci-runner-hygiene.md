# TASK-pr38-slice-ci-runner-hygiene: CI Runner Hygiene Slice

## Goal

Extract the self-hosted runner cleanup and product-image smoke ownership fixes into the first child PR, so later PR #38 child PRs are not treated as verified while workspace cleanup can still fail before tests run.

## Scope

- Product image smoke workflow pre-checkout recovery for stale workspace artifacts.
- Runner-temp smoke artifact root and numeric host UID:GID container output.
- Fail-closed receipts for invalid artifact roots, invalid UID:GID, Docker access blockers, and cleanup failures.
- Preflight and remote-green receipt contract rows that expose the CI hygiene boundary.

## Non-goals

Do not claim ROCm runtime readiness, product runtime readiness, scientific correctness, paid-pilot readiness, deployment readiness, or green release status from this slice alone.

## Likely Files Or Search Targets

`.github/workflows/product-image-smoke.yml`, `deploy/verify_product_image.sh`, `tools/product/build_product_image_smoke_preflight.py`, `tools/product/build_release_ci_remote_green_receipt.py`, `tests/unit/test_build_product_image_smoke_preflight.py`, `tests/unit/test_build_release_ci_remote_green_receipt.py`, `tests/unit/test_product_runtime_reality.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_build_product_image_smoke_preflight.py tests/unit/test_build_release_ci_remote_green_receipt.py tests/unit/test_product_runtime_reality.py`.

Run `./scripts/ai-verify.sh`.

Run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh`; product-mode blockers may remain fail-closed unless a fresh ROCm runtime receipt exists.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if the workflow writes smoke runner artifacts under the checkout workspace in GitHub Actions.
- Stop if container smoke output can be root-owned or non-runner-owned without a blocked receipt.
- Stop if the PR would mark product image runtime readiness green without a valid `rocm-runtime` receipt.

## Risk Level

R2

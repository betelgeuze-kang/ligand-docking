# TASK-pr38-slice-api-operator-cockpit: API Operator Cockpit Slice

## Goal

Extract API/operator cockpit surfaces from PR #38 into a child PR that improves read-only operator visibility without promoting paid-pilot, full-commercial, or claim-grade readiness.

## Scope

- Product operator cockpit builder, route, and registration.
- Release source-of-truth wiring for cockpit artifacts.
- Operator-facing status rows for PR split, claim boundaries, and fail-closed evidence.
- Focused tests for cockpit API, builder output, route registration, and source-of-truth tracking.

## Non-goals

Do not execute operators, dispatch jobs, deploy services, mutate external state, or claim paid-pilot/full-commercial readiness. Do not hide blocked evidence rows behind green cockpit wording.

## Likely Files Or Search Targets

`api/product_operator_cockpit.py`, `api/main.py`, `api/product.py`, `tools/product/build_product_operator_cockpit.py`, `tools/product/build_product_release_source_of_truth_gate.py`, `tests/unit/test_api_product_operator_cockpit*.py`, `tests/unit/test_build_product_operator_cockpit.py`, `tests/unit/test_build_product_release_source_of_truth_gate.py`.

## Verification

Run `python3 -m pytest -q tests/unit/test_api_product_operator_cockpit.py tests/unit/test_api_product_operator_cockpit_registration.py tests/unit/test_build_product_operator_cockpit.py tests/unit/test_build_product_release_source_of_truth_gate.py`.

Run `./scripts/ai-verify.sh`.

Run `AI_VERIFY_MODE=product ./scripts/ai-verify.sh` only after source-of-truth artifacts are intentionally refreshed; fail-closed product blockers are acceptable unless this child PR explicitly closes them with fresh evidence.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files.
- Stop if the cockpit text implies paid-pilot, broad product, or scientific claim readiness.
- Stop if route wiring would execute jobs or mutate external state.
- Stop if the child PR depends on unresolved self-hosted runner cleanup failures.

## Risk Level

R2

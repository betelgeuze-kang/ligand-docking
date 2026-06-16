# Task: AI-MD Native EvidenceBundle Profile Gate

## Goal

Make API runner profile readiness accounting expose missing native `EvidenceBundle` emission as a first-class blocker for delivery/profile promotion readiness.

The validated-runner adapter already supports opt-in `evidence_bundle_template`. Current enabled profiles do not declare it, so the product/commercial readiness artifacts should not describe those profiles as fully promotion-ready without naming that gap.

## Scope

In scope:

- `tools/product/validate_api_runner_profiles.py`
- `tools/product/build_api_runner_profile_promotion_readiness.py`
- `tools/product/build_api_runner_profile_enablement_work_order.py`
- focused unit tests under `tests/unit/`
- generated current artifacts only if needed by the builders

Out of scope:

- enabling/disabling profile JSONs
- running scientific runners
- adding fake native evidence bundles
- broad release-claim changes
- external state mutation

## Acceptance Criteria

- Enabled delivery/proxy-refinement profiles report whether native `evidence_bundle_template` is declared.
- Promotion readiness blocks profiles that are enabled or delivery-oriented but missing native `evidence_bundle_template`.
- Enablement work order rows/templates tell operators to add/review native EvidenceBundle output before promotion.
- Existing disabled example profiles stay disabled and do not become execution-ready.
- Tests cover both missing-template blocker and declared-template ready behavior.
- No claim widening: full commercial/general parity remains blocked.

## Verification

Run focused tests:

```bash
python3 -m pytest -q \
  tests/unit/test_build_api_runner_profile_promotion_readiness.py \
  tests/unit/test_api_runner_profile_enablement_work_order.py \
  tests/unit/test_api_validated_runner_adapter.py
```

Codex will run broader source-of-truth and product gate checks after review.

# TASK-ID: AI-MD Clean Container Gate Consistency Sweep

## Goal

Audit whether product readiness, bundle, KPI, release, and gate code still treats local ROCm/HIP evidence as sufficient for product claim readiness after the new clean-container gate.

## Scope

- Web access: disabled.
- Read-only sweep. Do not edit files.
- Find local code/tests/docs that mention product claim readiness, clean install, product image smoke, Docker image smoke, product bundle readiness, or AI-MD evidence bundle.
- Verify whether they now require or reference `clean_container_smoke_ready`, `product_image_smoke_preflight`, or `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime` before product claim promotion.
- Pay special attention to tools under `tools/product/`, `tools/accounting/`, `deploy/`, `.github/workflows/`, and tests under `tests/unit/`.

## Non-goals

- Do not run Docker.
- Do not install packages.
- Do not edit files.
- Do not stage, commit, push, delete, deploy, submit, or mutate external state.
- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not use web search/fetch.

## Likely Files Or Search Targets

- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tools/product/build_product_image_smoke_preflight.py`
- `tools/product/build_product_end_to_end_rocm_benchmark.py`
- `tools/product/build_product_release_source_of_truth_gate.py`
- `tools/product/build_product_commercial_readiness_handoff_bundle.py`
- `tools/accounting/build_product_goal_completion_audit.py`
- `deploy/verify_product_image.sh`
- `.github/workflows/product-image-smoke.yml`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`
- search terms: `product_claim_ready`, `clean_container_smoke_ready`, `clean install`, `clean_install`, `product_image_smoke`, `product_image_smoke_preflight`, `PRODUCT_IMAGE_VERIFY_MODE`, `rocm-runtime`, `product_bundle_evidence_export_ready`

## Verification

- Run only read-only commands such as `rg`, `sed`, `git diff --stat`, and targeted `python -m py_compile` if needed.
- Return a concise audit summary with:
  - likely missing gate links, with file paths and line references
  - any false positives or intentionally unrelated hits
  - recommended next edits, if any
  - commands run

## Stop Conditions

- Follow `AGENTS.md`.
- Stop immediately if a requested source requires reading `.env*`.
- Stop after one concise summary. Do not produce full logs or full diffs.

## Risk Level

R1

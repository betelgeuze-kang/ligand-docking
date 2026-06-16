# TASK-ID: ai-md-runtime-evidence-bundle-surface

## Goal

Make the API/runtime result surface treat `EvidenceBundle` as a first-class completed-job artifact instead of a status-file-only sidecar.

## Non-goals

- Do not widen restricted/local-delivery or full-commercial claims.
- Do not make API evidence bundles claim-safe.
- Do not change validated-runner execution semantics.
- Do not run docking, GPU jobs, external fetches, web calls, or production mutations.
- Do not redesign local delivery bundle generation.

## User Impact

Completed API jobs expose result manifest and evidence bundle provenance through durable job records and `/status/{job_id}`. A raw result file alone is not enough for `/results/{job_id}` to serve a completed result.

## Risk Level

R2

## Relevant Files

- `api/job_store.py`
- `api/worker.py`
- `api/main.py`
- `api/models.py`
- `tools/product/build_ai_md_contract_source_of_truth_gate.py`
- `tools/product/build_product_release_source_of_truth_gate.py`
- `tests/unit/test_api_job_store.py`
- `tests/unit/test_api_validated_runner_adapter.py`
- `tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Constraints

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries.
- Keep API evidence bundles review-only.
- Keep general-MD/full-commercial claim promotion blocked.
- Preserve backwards migration for existing SQLite job stores.

## Acceptance Criteria

- `SQLiteJobStore` has durable `evidence_bundle_path` and `evidence_bundle_sha256` fields with migration for existing DBs.
- Creating/recreating a job clears old result manifest and evidence bundle pointers.
- `update_job()` can persist result manifest path, evidence bundle path, and evidence bundle hash together for completed jobs.
- `worker.run_job_once()` persists evidence bundle path/hash into the durable job record after a completed run.
- `StatusResponse` and `/status/{job_id}` expose `result_manifest`, `evidence_bundle`, and `evidence_bundle_sha256` when present.
- `/results/{job_id}` refuses to serve the raw result file when a completed job lacks manifest or evidence bundle pointers.
- Focused tests prove the durable record and API status/result behavior.
- Source-of-truth gates track this runtime evidence-bundle surface.

## Required Tests

- `python3 -m py_compile api/job_store.py api/worker.py api/main.py api/models.py tools/product/build_ai_md_contract_source_of_truth_gate.py tools/product/build_product_release_source_of_truth_gate.py`
- `python3 -m pytest -q tests/unit/test_api_job_store.py tests/unit/test_api_validated_runner_adapter.py tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Review Focus

- No claim widening.
- Existing failed/retry behavior remains intact.
- Existing SQLite stores migrate safely.
- Raw result file is no longer the sole completed-result surface.
- Status response does not expose secrets or raw request payload.

## Rollback Plan

Remove the evidence-bundle DB columns, response fields, `/results` evidence checks, gate checks, and focused tests from this task; keep prior API evidence bundle file generation intact.

## Notes

This task advances R4 from `.betelgeuze/ai_md_refactor_commercial_audit_2026-06-16.md`.

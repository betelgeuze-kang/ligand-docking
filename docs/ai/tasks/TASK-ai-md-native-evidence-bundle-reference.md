# TASK-ID: ai-md-native-evidence-bundle-reference

## Goal

Allow an operator-approved validated-runner profile to declare and produce a native `EvidenceBundle` artifact, then let the API worker validate and adopt that bundle instead of always generating only a fallback review bundle.

## Non-goals

- Do not widen restricted/local-delivery or full-commercial claims.
- Do not make native bundles claim-safe by default.
- Do not change the allowlisted runner set.
- Do not run docking, GPU jobs, external fetches, web calls, or production mutations.
- Do not redesign local delivery bundle generation.

## User Impact

Delivery-capable runner profiles can begin moving from post-hoc API fallback wrapping toward runner-native evidence emission. Invalid or missing native bundles remain fail-closed.

## Risk Level

R2

## Relevant Files

- `api/validated_runner.py`
- `api/worker.py`
- `tools/product/validate_api_runner_profiles.py`
- `tools/product/build_ai_md_contract_source_of_truth_gate.py`
- `tools/product/build_product_release_source_of_truth_gate.py`
- `tests/unit/test_api_validated_runner_adapter.py`
- `tests/unit/test_api_job_store.py`
- `tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Constraints

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.
- Preserve CASP/no-leak boundaries.
- Keep general-MD/full-commercial claim promotion blocked.
- Native bundle support must be opt-in via profile fields.
- Existing profiles without native bundles must keep working and still receive fallback review-only bundles.

## Acceptance Criteria

- Profiles may define `evidence_bundle_template`, rendered with the same placeholders as `result_file_template`.
- The runner command context supports `{evidence_bundle}` when `evidence_bundle_template` is present.
- `execute_validated_runner_profile()` validates a produced native bundle as `EvidenceBundle` and records native bundle path/fingerprint in status and runner execution records.
- Invalid or missing native bundle files fail closed when the profile declares an evidence bundle template.
- Worker completed-job flow adopts a validated native bundle as the final `evidence_bundle.json` when present, preserving its canonical `EvidenceBundle.fingerprint()`.
- Existing profiles without native bundles continue to get fallback API-generated review-only bundles.
- `validate_api_runner_profiles.py` surfaces whether a profile declares native evidence bundle output.
- AI-MD source-of-truth gate checks native bundle profile/worker support.
- Product release source-of-truth tracks the changed files/tests.

## Required Tests

- `python3 -m py_compile api/validated_runner.py api/worker.py tools/product/validate_api_runner_profiles.py tools/product/build_ai_md_contract_source_of_truth_gate.py tools/product/build_product_release_source_of_truth_gate.py`
- `python3 -m pytest -q tests/unit/test_api_validated_runner_adapter.py tests/unit/test_api_job_store.py tests/unit/test_build_ai_md_contract_source_of_truth_gate.py`

## Review Focus

- No claim widening.
- Invalid native bundles fail closed.
- Existing fallback path remains compatible.
- The final worker status and durable DB record point to the adopted final bundle.
- Bundle fingerprint semantics are deterministic and based on `EvidenceBundle.fingerprint()`.

## Rollback Plan

Remove native bundle template support, worker adoption logic, source-gate checks, and focused tests from this task; keep prior runtime/API bundle surface intact.

## Notes

This task continues R4 from `.betelgeuze/ai_md_refactor_commercial_audit_2026-06-16.md`.

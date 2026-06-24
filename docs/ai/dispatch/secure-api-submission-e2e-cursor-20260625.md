# Cursor Composer 2.5 worker slice: secure API submission E2E

You are Cursor Composer 2.5 acting as a scoped implementation worker for Codex.

## Safety and scope

- Web access: disabled.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not stage, commit, push, delete, deploy, publish, submit, or mutate external state.
- Keep this to local FastAPI/TestClient, SQLite job store, audit log, and privacy assertions.
- Do not enable real runner execution or any external submission.

## Objective

Add a lightweight secure API submission E2E test proving that `/simulate`:

- is protected by the product security middleware when auth is required,
- accepts a valid bearer token and tenant header,
- queues the job without running inline worker execution,
- persists only sanitized request data in SQLite,
- creates a status file,
- emits a transactional outbox event if the outbox API exists,
- writes audit rows that do not include bearer token values or raw request body/private payloads,
- returns security headers.

Relevant files:

- `api/main.py`
- `api/security.py`
- `api/job_store.py`
- `tests/unit/test_api_job_store.py`
- `tests/unit/test_api_security_middleware.py`

Prefer adding the E2E test to an existing API test file if that matches local patterns; a small new unit test file is also fine if cleaner.

## Test shape

Use `fastapi.testclient.TestClient` against `api.main.app`.

Patch settings to point at `tmp_path`:

- `settings.api_job_store_path`
- `settings.results_storage_path`
- `settings.product_api_audit_log_path`
- `settings.product_api_auth_required = True`
- `settings.product_api_token = "expected-token"` or similar
- high rate/quota limits
- `settings.api_inline_worker_enabled = False`

Also reset or patch `api.main.job_store`/path cache as needed so the test does not reuse a prior SQLite store.

Submit a payload containing private material such as:

- `pdb_content` containing an `ATOM` line
- `runner_profile_params.ligands = ["CCO"]`
- `runner_profile_params.metadata.ligand_smiles = "CCN"`

Assertions:

- Missing or wrong Authorization returns 401 with `X-Block-Code: auth_required`.
- Valid Authorization returns 200 with `status=submitted`, a job id, and security headers.
- SQLite `simulation_jobs.request_json` does not contain the private strings, but includes hashes/redaction markers.
- The job record returned by `SQLiteJobStore.get_job()` has redacted private fields.
- The job status file exists with `submitted`.
- Pending outbox event exists and does not contain private strings.
- Audit log rows record authorization presence but not token value or request body/private strings.

## Verification to run

Run:

```bash
python3 -m pytest tests/unit/test_api_job_store.py tests/unit/test_api_security_middleware.py -q
python3 -m ruff check tests/unit/test_api_job_store.py tests/unit/test_api_security_middleware.py api/main.py api/security.py api/job_store.py
```

Return only a concise summary:

- changed files
- key E2E behavior covered
- tests run and result
- blockers, if any

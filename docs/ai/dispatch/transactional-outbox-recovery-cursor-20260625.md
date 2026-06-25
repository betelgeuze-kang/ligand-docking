# Cursor Composer 2.5 worker slice: transactional outbox recovery tests

You are Cursor Composer 2.5 acting as a scoped implementation worker for Codex.

## Safety and scope

- Web access: disabled.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not stage, commit, push, delete, deploy, publish, submit, or mutate external state.
- Keep the change focused on local SQLite API job store recovery behavior.
- Do not broaden into CASP/CAMEO submission or external API execution.

## Objective

Add focused coverage and minimal implementation, if needed, for transactional outbox recovery in the API job store.

The current relevant files are:

- `api/job_store.py`
- `api/worker.py`
- `tests/unit/test_api_job_store.py`

Observed current behavior:

- `SQLiteJobStore.create_job()` persists a sanitized request in `simulation_jobs`.
- `SQLiteJobStore.acquire_next_job()` uses `BEGIN IMMEDIATE` and recovers expired `running` leases by acquiring them again.
- `SQLiteJobStore.release_job_for_retry()` clears lease fields and returns `retry_ready` until max attempts are exhausted.
- There is not yet an explicit durable outbox table in `api/job_store.py`.

## Requested implementation shape

Prefer a small durable outbox in `SQLiteJobStore` if that is the cleanest interpretation:

- Add a `simulation_job_outbox` table initialized/migrated by `_init_db()`.
- Record a durable outbox event transactionally when creating a job and when updating terminal/retry states.
- Provide small methods to list pending outbox events and mark them delivered or recovered, using SQLite transactions.
- Make recovery idempotent: reopening the store after a simulated crash must still expose undelivered outbox events.
- Do not store private raw request payloads in outbox rows; use sanitized summaries or job ids/status only.

If you find an already-existing outbox/recovery abstraction I missed, extend that instead of adding a duplicate.

## Tests to add

Add tests in `tests/unit/test_api_job_store.py` proving:

- create-job outbox event is committed in the same durable store as the job and survives reopening the SQLite DB.
- terminal or retry state outbox event is recoverable after reopening, then can be marked delivered idempotently.
- raw private payload material is not present in outbox payload JSON.

Keep tests lightweight and deterministic.

## Verification to run

Run:

```bash
python3 -m pytest tests/unit/test_api_job_store.py -q
python3 -m ruff check api/job_store.py tests/unit/test_api_job_store.py
```

Return only a concise summary:

- changed files
- key behavior added
- tests run and result
- blockers, if any

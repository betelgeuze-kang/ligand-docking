# Cursor Worker Slice: Private Payload Round-Trip, Tamper, Expiry Tests

You are Cursor Agent acting as an implementation worker. Default model: Composer 2.5. Codex owns risk boundaries, targeted review, verification, and final acceptance.

## Task

Implement the next objective item: add private payload round-trip, tamper, and expiry tests.

Current context:
- `betelgeuze_product/payload_privacy.py` contains ledger redaction helpers only.
- `api/request_privacy.py` re-exports `sanitize_request_for_ledger`.
- No obvious existing private payload envelope helper was found.

Implement the smallest local helper needed to make the tests meaningful:
- Prefer adding functions to `betelgeuze_product/payload_privacy.py`, e.g. a local HMAC-signed private payload envelope.
- Use only Python stdlib.
- Do not claim encryption/confidentiality if the envelope only signs/integrity-protects the payload.
- Tests must prove:
  - round-trip recovers the original payload with nested content intact
  - tampering with payload or signature is rejected
  - expired payload is rejected using deterministic time injection
- Keep raw payloads out of ledger redaction tests; this slice is about the private envelope helper, not external storage.

Suggested API shape if no better local pattern exists:

```python
seal_private_payload(payload, *, signing_key, ttl_seconds, now=None) -> dict
open_private_payload(envelope, *, signing_key, now=None) -> dict
```

Return/raise behavior is up to the implementation, but tests should assert explicit errors such as `private_payload_tampered` and `private_payload_expired`.

## Files In Scope

- `betelgeuze_product/payload_privacy.py`
- `tests/unit/test_payload_privacy.py` or another focused test file if one already exists
- `api/request_privacy.py` only if re-exporting the helper is clearly useful

## Acceptance Criteria

- Focused tests pass.
- Existing `tests/unit/test_api_job_store.py::test_sqlite_job_store_redacts_sensitive_request_payload` still passes.
- No `.env*` reads, no external state mutation, no network, no database schema changes.
- Do not broaden into transactional outbox, secure API E2E, workflow, PR, merge, Docker, or ROCm work.

## Verification

Run:

```bash
python3 -m pytest tests/unit/test_api_job_store.py tests/unit/test_payload_privacy.py -q
python3 -m ruff check betelgeuze_product/payload_privacy.py tests/unit/test_payload_privacy.py
```

If the test file has a different name, adjust the commands and report it.

## Web Access

Web access: disabled

## Constraints

- Follow `AGENTS.md`.
- Do not expand scope.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not stage, commit, push, delete, deploy, publish, release, production migration, billing, cloud mutation, secret rotation, permission escalation, or CASP submission commands.

## Return Format

Return at most 80 lines:

- changed files
- tests/checks run with pass/fail status
- failed test names, if any
- key diff summary in 10 bullets or fewer
- blockers or risks
- web sources consulted, only if web access was enabled

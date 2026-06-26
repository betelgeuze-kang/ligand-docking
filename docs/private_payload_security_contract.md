# Private Payload Security Contract

Status: reference. Distinguishes what is **merged on `main`** from what is
**in review**.

This contract governs how raw customer docking inputs (SMILES, PDB, SDF, MOL2,
PDBQT, mmCIF, and similar) are handled so they never leak into public artifacts.

## Threat model

- Public job ledger files, API responses, and the SQLite queue payloads are
  treated as **non-confidential**: they may be read by operators, logged, or
  surfaced in status views.
- Raw customer inputs are **confidential**. They must not appear in any of the
  above, and at-rest storage of the original request must be protected.

## Layer 1 — Public ledger redaction (merged, `main`)

Source: `betelgeuze_product/payload_privacy.py` →
`sanitize_request_for_ledger` (re-exported via `api/request_privacy.py`).

- Sensitive scalar keys (e.g. `smiles`, `canonical_smiles`, `inline_pdb`,
  `pdb_content`, `protein_pdb`, `sdf_content`, `mol2_content`, `source_value`,
  `structure_content`, ...) and key suffixes (`_pdb_content`, `_pdb_text`,
  `_smiles`) are replaced with a redaction record:

  ```json
  {"redacted": true, "redaction": "sha256", "sha256": "<hex>", "byte_length": <n>}
  ```

- Sensitive collection keys (`ligand`, `ligands`, `compound`, `compounds`) are
  redacted when string-valued.
- Pre-computed `*_sha256` / `request_sha256` fields are preserved (already
  non-sensitive digests).
- Used wherever records are persisted (`persist_docking_job_record`,
  `write_job_record`) and in outbox payloads (`api/job_store.py`).

## Layer 2 — Private payload integrity envelope (merged, `main`)

Source: `betelgeuze_product/payload_privacy.py` → `seal_private_payload` /
`open_private_payload`.

- Envelope version `private_payload_integrity_v1`, integrity algorithm
  `hmac-sha256`.
- **Integrity + authenticity only** (it signs; it does not encrypt). Do not
  claim confidentiality from this envelope alone.
- TTL enforced via `issued_at` / `expires_at`.
- Errors are stable strings: `private_payload_tampered` (bad/absent signature or
  malformed payload), `private_payload_expired` (past TTL).

## Layer 3 — Encrypted at-rest store (IN REVIEW — not yet on `main`)

Proposed in the encrypted private payload store PR. Documented here so the
contract is complete; treat as the target state, not current `main`.

Intended properties (`betelgeuze_product/private_payload_store.py`):

- **Confidentiality at rest** for the original request, stored outside the
  public ledger.
- Authenticated encryption bound to `job_id` **and** the canonical
  `request_sha256` (both authenticated), so a record cannot be read under a
  different job id or substituted request.
- TTL expiry, ordered multi-key **key rotation** (decrypt under any retained
  key, encrypt under the primary), restrictive `0600` file / `0700` directory
  permissions, and atomic temp-write + rename.
- A versioned `cipher` field so the backend can be upgraded (e.g. to an AEAD
  such as AES-GCM/Fernet) without breaking stored records.
- Stable error codes: `private_payload_store_tampered`,
  `private_payload_store_expired`, `private_payload_store_job_id_mismatch`,
  `private_payload_store_request_mismatch`, `private_payload_store_unknown_key`,
  `private_payload_store_missing`, `private_payload_store_no_keys`,
  `private_payload_store_malformed`.

> Note: the current `main` implementation is stdlib-only (HKDF-SHA256 +
> HMAC-SHA256 CTR keystream + encrypt-then-MAC) because the third-party
> `cryptography`/Fernet dependency is unavailable in the restricted build/CI
> network. The versioned `cipher` field is what allows a later AEAD backend.

## Invariants (must always hold)

1. Raw customer inputs never appear in: API responses, SQLite queue payloads,
   public job ledgers, outbox events, or logs.
2. Error messages derived from customer input are redacted to a SHA-256 summary
   before persistence (see `api/job_store.py` outbox error handling).
3. The internal filesystem path of a stored record is never returned to the
   customer API (see the docking response contract — `ledger_path` removed).
4. Any private payload read must verify both `job_id` and `request_sha256`
   binding before returning plaintext.

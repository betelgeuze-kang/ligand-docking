# External immutable reservation authority for the historical one-shot A/B

## Purpose

The repository-local `.betelgeuze` store is a second line of defense. It cannot
by itself prove that a copied checkout or a checkout whose local state was
deleted has not already consumed the sole historical run.

This contract defines the request and signed receipt that a separately operated,
append-only external ledger must implement before historical execution can be
considered.

## Reservation key

The global key is derived from:

```text
one-shot policy SHA-256
historical cohort SHA-256
reviewed source commit SHA-1
reviewed execution-environment SHA-256
```

The first valid request for that key may obtain `run_ordinal = 1`. Every later
request for the same key must fail, even when it comes from another clone, a
new local directory, a deleted `.betelgeuze` store, or another nonce.

## Request

The request binds:

- the frozen policy and cohort identities;
- the exact source commit;
- the reviewed execution environment;
- a human/operator identity;
- a one-time nonce;
- requested run ordinal one; and
- false historical, fresh, product, and public/scientific authorities.

GitHub Actions, Dependabot, workflow identities, and unnormalized operator
identities are rejected. Repository CI must never acquire external execution
authority.

## Signed receipt

The external receipt must be signed by a separately trusted Ed25519 key and
must contain:

- the exact request identity and reservation key;
- source, environment, operator, and nonce identities;
- `ledger_sequence = 1` and `run_ordinal = 1`;
- an independently meaningful ledger identifier;
- bounded whole-second UTC validity timestamps;
- `immutable = true` and `append_only = true`; and
- false historical, fresh, product, and public/scientific authorities.

Verification checks the canonical self-hash, signature, key/request binding,
time window, revocation set, and every non-authority boundary.

## Provider interface

An external provider exposes only:

```text
reserve(request) -> immutable receipt
lookup(reservation_key) -> immutable receipt or none
```

It must not expose release, delete, reset, rollback-to-unused, runner, or docking
operations. Incident recovery may restore availability from backup but may not
remove an accepted reservation. A revoked receipt remains retained and blocks
reuse of the same global key.

## Test-only provider

The repository includes an in-memory provider solely for deterministic tests.
Two independent clients sharing that provider have exactly one winner; deleting
a simulated local state does not restore authority; nonce replay and a second
reservation fail closed.

```text
operational_for_historical_execution = false
```

The test provider, GitHub Actions, and this document do not satisfy the external
operations requirement.

## Remaining operational gate

Actual historical execution remains blocked until an independently reviewed
external service is deployed with:

- durable append-only storage outside the repository and runner;
- protected signing key or HSM;
- operator and reviewer separation;
- backup, retention, revocation, and incident procedures;
- availability and timeout behavior that fails closed;
- audit export and independent receipt verification; and
- downstream binding into local reservation, run-start, full evidence, and
  final result receipts.

No fresh-128, Stage 0, profile-promotion, product, customer-pose, or public claim
authority is created by this contract.

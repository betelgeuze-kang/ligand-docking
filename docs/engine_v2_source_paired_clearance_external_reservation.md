# External immutable reservation authority for the historical one-shot A/B

## Status

```text
contract_implemented: true
external_service_operational: false
provider_endpoint_configured: false
trust_anchor_configured: false
historical_execution_operational: false
fresh_holdout_execution_authorized: false
stage0_admission_authority: false
profile_promotion_authority: false
product_execution_authorized: false
customer_pose_emission_authorized: false
public_or_scientific_claim_authorized: false
```

The local `.betelgeuze` store protects one exact checkout, but deleting the store
or copying the repository cannot be treated as global lifetime uniqueness. This
contract defines the external authority required to close that gap without
pretending that repository tests or GitHub Actions are the external ledger.

Machine-readable policy:

```text
config/engine_v2_source_paired_clearance_external_reservation.json
```

Policy identity:

```text
betelgeuze.engine_v2_source_paired_clearance_external_reservation_policy/1.1.0
e018b149a010b337ddc3705c0cb904466a6cd870db82836b3b5c580c3cb650c4
```

## Review-only operations decision record

The separate review record below enumerates the operational decisions that an
external provider owner and independent reviewer must make. It is deliberately
unresolved and is not consumed by the reservation runtime, external gate, or
operator CLI:

```text
config/engine_v2_source_paired_clearance_external_reservation_operations_decision.json
betelgeuze.engine_v2_source_paired_clearance_external_reservation_operations_decision/1.0.0
0ce7914de8a02b2ce438aee35dd7907e161f82fa92e9175d684cd96a22800100
```

It pins the current external-reservation policy, historical one-shot policy,
and Phase 2.5 cohort identities. Its 32 unresolved fields cover ledger
ownership, the isolated production realm and strongly consistent store,
non-exporting HSM/KMS signing custody, trust-anchor lifecycle, mTLS, distinct
real-name author/operator/reviewer rosters, WORM retention and recovery, and
ambiguous-commit, revocation, incident, and break-glass procedures.

Every decision value remains `null` or empty, provider qualification and
independent review remain false, and every authority value remains false. The
review record verifier exits successfully for this valid unresolved state while
reporting `operations_decision_ready=false`; success is evidence of schema
integrity, not operational readiness. Any filled value, authority escalation,
source-policy drift, duplicate key, sensitive-material field, or re-sealed
semantic change fails closed.

The record preserves the same four operational blockers listed below. It does
not contain an endpoint, account/project selection, identity roster,
authentication material, signing material, or qualification receipt. GitHub
Actions and test doubles remain prohibited from production authority and
production network access.

## Lifetime uniqueness and exact execution keys

The immutable create-if-absent lifetime key is the canonical SHA-256 of:

```text
one_shot_policy_sha256
historical_case_ids_sha256
```

It admits only reserved run ordinal one and at most one lifetime receipt. A
second checkout, source commit, environment, or nonce cannot create another
ordinal for the same frozen policy and cohort. Deleting local state does not
alter this key or restore authority.

The exact execution key additionally binds the immutable lifetime key to:

```text
source_commit_git_sha1
execution_environment_sha256
```

This second identity prevents source or environment substitution inside the
sole reservation. It is not a new uniqueness namespace.

## Request boundary

A reservation request binds:

- the frozen one-shot policy;
- exact clean source commit;
- reviewed execution-environment identity;
- exact historical cohort identity;
- distinct author, operator, and reviewer identities;
- a one-time SHA-256 nonce;
- a bounded issue/expiry window; and
- requested ordinal one.

The repository provides canonical request construction only. It contains no
production endpoint, credential, private signing key, or network implementation.

## Signed receipt boundary

A reviewed service must return an Ed25519-signed canonical receipt and a
separately signed, short-lived revocation snapshot. The receipt contains:

- provider and reservation identities;
- exact lifetime key, execution key, and request identity;
- policy, source, environment, cohort, nonce, author, operator, and reviewer
  bindings;
- signed author/operator/reviewer authentication attestations and an explicit
  non-GitHub-Actions operator assertion;
- ordinal one, maximum lifetime count one, and ledger sequence one;
- server commit and retention timestamps;
- immutable and append-only flags;
- explicit non-test and non-revoked state; and
- a canonical receipt self-hash.

The revocation snapshot binds the same policy-pinned provider and Ed25519 trust
anchor, a monotonic ledger sequence, a bounded validity window, the sorted
revoked-receipt set, append-only state, and its canonical self-hash. A caller
cannot supply or omit an unsigned local revocation list.

Verification rejects non-canonical encodings, duplicate JSON keys, either
signature failure, provider/policy/trust-anchor cross-wire, stale request or
revocation snapshot, inadequate retention, revocation, test-only receipts, role
collision, automated operators, source/environment/cohort mismatch, and any
execution, fresh, product, promotion, customer-pose, or claim authority
escalation.

A cryptographically valid receipt remains `authoritative_for_execution=false` in
repository code. Operational execution requires a separate reviewed policy update
and external infrastructure qualification.

## Downstream binding

The module defines a self-hashed binding for each required downstream role:

```text
local_reservation
run_start
candidate_evidence
result
```

Each binding includes the receipt and receipt-signature hashes, revocation
snapshot hash, lifetime and exact execution keys, request identity, author,
source commit, execution environment, and local document hash. Missing, stale,
substituted, or cross-wired bindings fail closed.

The current PR defines these contracts but does not silently rewrite the already
frozen PR #245 receipt schemas. A later reviewed integration must version those
schemas and require the binding at every stage. Until that integration and the
external service are both operational, historical molecular execution remains
blocked.

## Operator composition gate

The canonical verifier and operator CLI compose local one-shot eligibility with
this external policy. `status` reports both local and external blockers, and all
three mutating commands fail before local durable state or molecular evidence is
opened:

```text
reserve
start
write-result
```

The committed non-operational policy therefore cannot be bypassed through the
canonical operator entrypoint. A future operational provider still requires a
reviewed policy/code update that consumes the signed external receipt and its
versioned downstream bindings; changing or resealing the current JSON is rejected.

## Provider operational requirements

A production provider must be reviewed outside the repository and supply:

1. an immutable append-only create-if-absent store;
2. a stable provider ID and policy-pinned Ed25519 public trust anchor;
3. mutually authenticated TLS and a mandatory network round trip;
4. independent author, reviewer, and operator identities;
5. a server-controlled clock and bounded request expiry;
6. primary and off-site backups;
7. at least ten years of receipt retention;
8. signed, short-lived views of append-only revocation and incident records;
9. no reservation rollback or deletion; and
10. no replacement reservation after an incident without a newly reviewed policy.

GitHub Actions and test doubles are explicitly forbidden from acquiring production
reservation authority.

## Failure semantics

The repository policy deliberately ships with:

```text
provider_id = unconfigured
endpoint = ""
trust_anchor_public_key_hex = ""
provider_operational = false
historical_execution_operational = false
```

The verifier therefore reports these blockers before any network call:

```text
external_reservation_provider_not_operational
external_reservation_endpoint_not_configured
external_reservation_trust_anchor_not_configured
historical_execution_operational_authority_false
```

Provider timeout, network failure, signature failure, revocation, or policy drift
must also fail before local run-start or molecular output.

## Incident and rollback semantics

A reservation is never rolled back. An incident may append a revocation or
quarantine record, but it cannot delete the reservation or free ordinal one.
Recovery requires independent review. A replacement run requires a new frozen
policy and cannot reuse the original global reservation key.

## Authority boundary

This implementation is a verifiable integration contract, not a deployed ledger.
It does not close the operational part of issue #247, reserve a run, execute
molecular work, open fresh data, enable products, promote a profile, sign a
release, or authorize a scientific/public claim.

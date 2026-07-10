# Server-Bound Product API Identity

## Scope

This contract prevents an authenticated caller from selecting an arbitrary tenant by changing `X-Tenant-ID`.

For the single configured product token, the authoritative tenant comes from the server setting:

```text
PRODUCT_API_TOKEN_TENANT_ID
```

The optional request header is only an assertion. When supplied under authenticated mode, it must match the server-bound tenant or the middleware returns `tenant_identity_mismatch` with HTTP 403.

## Authentication settings

```text
PRODUCT_API_AUTH_REQUIRED=1
PRODUCT_API_TOKEN=<tenant token>
PRODUCT_API_TOKEN_TENANT_ID=<authoritative tenant id>
PRODUCT_API_ADMIN_TOKEN=<separate privileged token>
```

The product and administrator tokens must be distinct. Equal non-empty values fail closed with `server_token_configuration_invalid`.

Tenant identifiers accept 1–80 allowlisted characters:

```text
A-Z a-z 0-9 _ . : -
```

The first character must be alphanumeric.

## Identity shapes

A product token produces:

```json
{
  "tenant_id": "server-configured-tenant",
  "principal": "token:server-configured-tenant",
  "authenticated": true,
  "is_admin": false
}
```

The administrator token produces:

```json
{
  "tenant_id": "admin",
  "principal": "admin-token",
  "authenticated": true,
  "is_admin": true
}
```

The middleware stores the resulting immutable identity on `request.state.product_identity`. Endpoint code reads it through `api.request_identity.request_identity` rather than trusting request headers directly.

## Local development

When authentication and hosted exposure are both disabled, `X-Tenant-ID` remains available for trusted local development, but it is validated against the same allowlist. This local mode is not a hosted multi-tenant security boundary.

When authentication or hosted exposure is configured, calling an endpoint without `ProductSecurityMiddleware` fails closed with HTTP 401.

## Path and request preflight

The allowlist requires a real path segment. For example:

- `/product` and `/product/...` are permitted;
- `/productevil` is not permitted;
- malformed or negative `Content-Length` is rejected before endpoint execution.

`/metrics` retains its existing unauthenticated monitoring exception. It receives a non-privileged local metrics identity and must remain secret-free.

## Product docking object authorization

The product docking ledger routes enforce the stored record's `customer_id`:

```text
GET  /product/docking/jobs
GET  /product/docking/jobs/{job_id}
GET  /product/docking/jobs/{job_id}/history
POST /product/docking/jobs/{job_id}/cancel
POST /product/docking/jobs/{job_id}/retry
```

For non-administrator identities:

- list filters are overwritten with the authenticated tenant;
- cross-tenant reads and mutations return HTTP 404;
- malformed job identifiers return HTTP 404 before a filesystem path is built;
- `debug=true` is rejected;
- cancel/retry event actors are derived from the authenticated principal, not a caller-provided `actor` field.

On submission, a non-administrator cannot select a different `customer_id`. An omitted customer is filled from the server-derived identity. A privileged administrator may submit for an explicitly supplied valid customer.

Administrator identities may review cross-tenant records and request the bounded diagnostics envelope. This does not grant permission to bypass scientific or release gates.

The read/list/cancel/retry authorization path is kept dependency-light. Scientific, chemistry, runner, and structure-analysis imports occur only after an authorized endpoint enters the relevant execution path.

## SQLite simulation ownership ledger

`api.simulation_job_ownership` adds a separate, durable ownership table in the same SQLite database as the simulation queue:

```text
simulation_job_ownership(
  job_id PRIMARY KEY,
  tenant_id,
  created_at_utc,
  updated_at_utc
)
```

The separate table keeps queue and worker-lease behavior outside this security slice while making ownership explicit and reviewable.

The ownership contract is:

- job identifiers are allowlisted before SQL or filesystem use;
- a non-administrator can create only for its authenticated tenant;
- an administrator can explicitly create for another valid tenant;
- an owner binding is idempotent for the same tenant and immutable across tenants;
- an existing simulation queue row with no ownership row cannot be claimed later;
- a queue row with no ownership row is inaccessible;
- cross-tenant reads return HTTP 404;
- ownership persists across process/store reopen.

New queue-writing code should call `create_owned_job` or `create_owned_job_if_absent`, and reads should call `get_owned_job`. Calling the raw `SQLiteJobStore.create_job` method remains an internal legacy path and does not create an externally accessible owned job.

## Remaining endpoint integration boundary

The SQLite ownership primitive is implemented and tested, but `/simulate`, `/status/{job_id}`, and `/results/{job_id}` have not yet been rewired to use it in this slice.

Until that integration child PR lands, do not describe the whole API as completely multi-tenant isolated. Existing unowned rows intentionally remain unavailable rather than being assigned to the first caller who knows their identifier.

## Claim boundary

A green identity, product-job isolation, and SQLite ownership-ledger test demonstrates only the named authentication and authorization primitives. It does not demonstrate:

- complete object authorization across every API route;
- live `/simulate`, `/status`, and `/results` endpoint integration;
- production secret management or rotation;
- external identity-provider integration;
- TLS termination correctness;
- docking, scientific, GPU, benchmark, wetlab, paid-pilot, or commercial readiness.

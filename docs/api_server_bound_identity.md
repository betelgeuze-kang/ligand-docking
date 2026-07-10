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
- authenticated/hosted access to a queue row with no ownership row is blocked;
- cross-tenant reads return HTTP 404;
- ownership persists across process/store reopen.

New queue-writing code should call `create_owned_job` or `create_owned_job_if_absent`, and reads should call `get_owned_job`. Calling the raw `SQLiteJobStore.create_job` method remains an internal legacy path and does not create an authenticated externally accessible owned job.

## Live simulation endpoint integration

The live simulation routes now use the request identity and ownership adapter:

```text
POST /simulate
GET  /status/{job_id}
GET  /results/{job_id}
```

`POST /simulate` creates the ownership row and job row before creating status files or scheduling inline worker work. `GET /status/{job_id}` and `GET /results/{job_id}` authorize the SQLite object before reading status, manifest, bundle, or result paths.

Authenticated and hosted requests always require a persisted owner binding. Missing, invalid, and cross-tenant identifiers are concealed as HTTP 404 at the object boundary.

A narrow compatibility rule remains for trusted local development: when both authentication and hosted exposure are disabled, the unauthenticated `local` identity may read a legacy unowned queue row. The row is not silently assigned or mutated. Enabling authentication or hosted exposure immediately disables this compatibility rule.

The worker's internal lease/heartbeat processing remains independent of caller identity after a job has been durably admitted. This slice does not alter runner selection, retry policy, scientific computation, or evidence generation.

## Validation boundary

The mobile CI validates the ownership adapter dynamically and verifies the `api.main` route wiring through AST-based source contracts because the complete application tree intentionally requires heavier product/science dependencies.

The self-hosted `product-api-worker` lane remains the authority for full application import and the existing API job-store/security regression suite.

## Claim boundary

A green identity, product-job isolation, SQLite ownership-ledger, and route-wiring test demonstrates authorization for the named product and simulation job surfaces under the configured token model. It does not demonstrate:

- authorization correctness for every future or unreviewed API route;
- production secret management or automatic token rotation;
- external identity-provider, per-user RBAC, or federated tenancy integration;
- TLS termination correctness;
- docking accuracy, scientific validity, GPU parity, benchmark performance, wetlab evidence, paid-pilot readiness, or commercial readiness.

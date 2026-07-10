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

## Remaining SQLite simulation boundary

The product docking JSON ledger now has route-level object authorization, but the separate SQLite simulation queue used by `/simulate`, `/status/{job_id}`, and `/results/{job_id}` still requires its own persisted tenant-owner column and endpoint checks.

Until that child slice lands, do not describe the whole API as completely multi-tenant isolated.

## Claim boundary

A green identity and product-job isolation test demonstrates only authentication and authorization for the named product docking ledger routes. It does not demonstrate:

- complete object authorization across every API route;
- SQLite simulation status/result tenant isolation;
- production secret management or rotation;
- external identity-provider integration;
- TLS termination correctness;
- docking, scientific, GPU, benchmark, wetlab, paid-pilot, or commercial readiness.

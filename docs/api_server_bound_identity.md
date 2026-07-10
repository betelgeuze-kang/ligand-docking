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

The middleware stores the resulting immutable identity on `request.state.product_identity`. Endpoint code should read it through `api.request_identity.request_identity` rather than trusting request headers directly.

## Local development

When authentication and hosted exposure are both disabled, `X-Tenant-ID` remains available for trusted local development, but it is validated against the same allowlist. This local mode is not a hosted multi-tenant security boundary.

When authentication or hosted exposure is configured, calling an endpoint without `ProductSecurityMiddleware` fails closed with HTTP 401.

## Path and request preflight

The allowlist requires a real path segment. For example:

- `/product` and `/product/...` are permitted;
- `/productevil` is not permitted;
- malformed or negative `Content-Length` is rejected before endpoint execution.

`/metrics` retains its existing unauthenticated monitoring exception. It receives a non-privileged local metrics identity and must remain secret-free.

## Object authorization boundary

This slice establishes authentication identity primitives only. It does not, by itself, prove object-level tenant isolation for every job/result endpoint.

Endpoints that load tenant-owned objects must additionally call:

```python
require_tenant_match(identity, owner_tenant_id, resource="job")
```

Cross-tenant access is reported as HTTP 404 to avoid confirming that another tenant's object exists. Administrator identities may bypass this ownership check for explicitly privileged operations.

The next child slice should bind tenant ownership into the SQLite job record and the product docking job endpoints, then add cross-tenant read/list/cancel/retry regression tests.

## Claim boundary

A green identity test demonstrates only authentication and request-identity behavior. It does not demonstrate:

- complete object authorization across all routes;
- production secret management or rotation;
- external identity-provider integration;
- TLS termination correctness;
- docking, scientific, GPU, benchmark, or commercial readiness.

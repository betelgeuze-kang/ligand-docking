# Product Security And Deployment Policy

The hosted/customer API profile must keep these controls available before exposure:

- API token hook through `PRODUCT_API_AUTH_REQUIRED` and `PRODUCT_API_TOKEN`.
- Tenant marker through `X-Tenant-ID` for audit separation.
- Per-tenant/client rate limit through `PRODUCT_API_RATE_LIMIT_PER_MINUTE`.
- Payload size limit through `PRODUCT_API_MAX_PAYLOAD_BYTES`.
- Path allowlist and security headers in the product middleware.
- JSONL audit log through `PRODUCT_API_AUDIT_LOG_PATH`.
- `/metrics` endpoint for deployment smoke and monitoring.
- Product container recipe in `Dockerfile.product`.
- Rollback runbook in `deploy/product_rollback_runbook.md`.
- Hosted external exposure is fail-closed unless `PRODUCT_API_HOSTED_EXPOSURE_APPROVED=1` is set after the
  `APPROVE_HOSTED_PRODUCT_API_EXPOSURE` operator approval.
- TLS termination must be operator verified through `PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1` before hosted claims.
- If hosted exposure is approved but TLS termination is not operator verified, the product middleware blocks non-`/metrics`
  requests with `hosted_tls_termination_not_verified`.

This policy does not authorize external exposure by itself. Exposure still requires operator approval, secret injection, and environment-specific deployment review.

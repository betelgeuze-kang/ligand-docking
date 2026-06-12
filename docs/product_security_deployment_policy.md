# Product Security And Deployment Policy

The hosted/customer API profile must keep these controls available before exposure:

- API token hook through `PRODUCT_API_AUTH_REQUIRED` and `PRODUCT_API_TOKEN`.
- Tenant marker through `X-Tenant-ID` for audit separation.
- Per-tenant/client rate limit through `PRODUCT_API_RATE_LIMIT_PER_MINUTE`.
- Tenant quota through `PRODUCT_API_TENANT_DAILY_QUOTA`; quota overflow must fail closed with
  `tenant_quota_exceeded`.
- Payload size limit through `PRODUCT_API_MAX_PAYLOAD_BYTES`.
- Path allowlist and security headers in the product middleware.
- JSONL audit log through `PRODUCT_API_AUDIT_LOG_PATH`.
- Audit retention through `PRODUCT_API_AUDIT_RETENTION_DAYS`; default hosted/on-prem retention is 90 days.
- `/metrics` endpoint for deployment smoke and monitoring.
- Product container recipe in `Dockerfile.product`.
- Rollback runbook in `deploy/product_rollback_runbook.md`.
- Backup/DR procedure: the operator must snapshot the `micf-product-results` volume and verify restore against
  `API_JOB_STORE_PATH` plus signed result manifests before enabling hosted exposure.
- Secret rotation: `PRODUCT_API_TOKEN` and `API_RESULT_MANIFEST_SIGNING_KEY` must rotate at least every
  `PRODUCT_API_SECRET_ROTATION_DAYS` days; rotation evidence stays outside git and is represented by operator
  verification, not by checked-in secret values.
- Pager route: `PRODUCT_API_PAGER_WEBHOOK_CONFIGURED=1` may be set only after `tools/smoke_alert_delivery.py`
  passes against the operator-managed pager receiver; the local receiver smoke is not a hosted pager substitute.
- Hosted external exposure is fail-closed unless `PRODUCT_API_HOSTED_EXPOSURE_APPROVED=1` is set after the
  `APPROVE_HOSTED_PRODUCT_API_EXPOSURE` operator approval.
- TLS termination must be operator verified through `PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1` before hosted claims.
- If hosted exposure is approved but TLS termination is not operator verified, the product middleware blocks non-`/metrics`
  requests with `hosted_tls_termination_not_verified`.

This policy does not authorize external exposure by itself. Exposure still requires operator approval, secret injection, and environment-specific deployment review.

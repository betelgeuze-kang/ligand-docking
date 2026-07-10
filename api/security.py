from __future__ import annotations

import json
import hmac
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import settings
from api.request_identity import ProductRequestIdentity, normalize_tenant_id

ALLOWED_PRODUCT_PREFIXES = (
    "/product",
    "/cameo",
    "/casp17",
    "/cleanup",
    "/goal",
    "/metrics",
    "/docs",
    "/openapi.json",
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

METRICS_REGISTRY = CollectorRegistry()
SECURITY_CONTROL_GAUGE = Gauge(
    "betelgeuze_product_security_controls",
    "Product security control readiness.",
    ("control",),
    registry=METRICS_REGISTRY,
)
HTTP_REQUESTS = Counter(
    "betelgeuze_product_http_requests_total",
    "Product API HTTP requests by method, normalized path, status, and block code.",
    ("method", "path", "status_code", "blocked_code"),
    registry=METRICS_REGISTRY,
)
BLOCKED_REQUESTS = Counter(
    "betelgeuze_product_blocked_requests_total",
    "Product API blocked requests by block code.",
    ("code",),
    registry=METRICS_REGISTRY,
)
AUDIT_WRITE_FAILURES = Counter(
    "betelgeuze_product_audit_write_failures_total",
    "Product API audit log write failures.",
    registry=METRICS_REGISTRY,
)

for _control in (
    "auth_hook",
    "tenant_header",
    "rate_limit",
    "tenant_quota",
    "payload_limit",
    "path_allowlist",
    "audit_log",
    "audit_retention",
    "runtime_request_counters",
    "hosted_tls_guard",
):
    SECURITY_CONTROL_GAUGE.labels(control=_control).set(1)


class ProductSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._tenant_quota_counts: dict[tuple[str, str], int] = defaultdict(int)

    @staticmethod
    def _path_is_allowed(path: str) -> bool:
        return any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in ALLOWED_PRODUCT_PREFIXES
        ) or path in {"/simulate"} or path.startswith(("/status/", "/results/"))

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        blocked, identity = self._preflight_blocker(request)
        if blocked is not None:
            self._audit_request(request, blocked.status_code)
            self._attach_security_headers(blocked)
            self._record_metrics(request, blocked.status_code, blocked_code=str(blocked.headers.get("X-Block-Code", "") or "blocked"))
            return blocked
        assert identity is not None
        request.state.product_identity = identity
        payload_blocked = await self._payload_blocker(request)
        if payload_blocked is not None:
            self._audit_request(request, payload_blocked.status_code)
            self._attach_security_headers(payload_blocked)
            self._record_metrics(
                request,
                payload_blocked.status_code,
                blocked_code=str(payload_blocked.headers.get("X-Block-Code", "") or "blocked"),
            )
            return payload_blocked
        try:
            response = await call_next(request)
        except Exception:
            self._record_metrics(request, 500, blocked_code="")
            raise
        self._attach_security_headers(response)
        self._audit_request(request, response.status_code)
        self._record_metrics(request, response.status_code, blocked_code="")
        return response

    @staticmethod
    def _attach_security_headers(response: Response) -> None:
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)

    def _preflight_blocker(
        self,
        request: Request,
    ) -> tuple[JSONResponse | None, ProductRequestIdentity | None]:
        path = request.url.path
        if not self._path_is_allowed(path):
            return self._blocked("path_not_allowed", 404), None
        if (
            settings.product_api_hosted_exposure_approved
            and not settings.product_api_tls_termination_operator_verified
            and path != "/metrics"
        ):
            return self._blocked("hosted_tls_termination_not_verified", 503), None
        raw_content_length = request.headers.get("content-length")
        try:
            content_length = int(raw_content_length or 0)
        except (TypeError, ValueError):
            return self._blocked("invalid_content_length", 400), None
        if content_length < 0:
            return self._blocked("invalid_content_length", 400), None
        if content_length > settings.product_api_max_payload_bytes:
            return self._blocked("payload_too_large", 413), None

        identity_or_block = self._authenticate(request, path=path)
        if isinstance(identity_or_block, JSONResponse):
            return identity_or_block, None
        identity = identity_or_block
        tenant_id = identity.tenant_id
        client_host = request.client.host if request.client else "unknown"
        rate_key = f"{tenant_id}:{client_host}"
        if self._rate_limited(rate_key):
            return self._blocked("rate_limited", 429), None
        if self._tenant_quota_exceeded(tenant_id):
            return self._blocked("tenant_quota_exceeded", 429), None
        return None, identity

    def _authenticate(
        self,
        request: Request,
        *,
        path: str,
    ) -> ProductRequestIdentity | JSONResponse:
        if path == "/metrics":
            return ProductRequestIdentity(
                tenant_id="local",
                principal="metrics",
                authenticated=False,
                is_admin=False,
            )

        supplied_tenant = request.headers.get("X-Tenant-ID", "").strip()
        if not settings.product_api_auth_required:
            try:
                tenant_id = normalize_tenant_id(supplied_tenant or "local")
            except ValueError:
                return self._blocked("invalid_tenant_id", 400)
            return ProductRequestIdentity(
                tenant_id=tenant_id,
                principal=f"local:{tenant_id}",
                authenticated=False,
                is_admin=False,
            )

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return self._blocked("auth_required", 401)
        token = authorization[len("Bearer ") :]
        admin_token = str(settings.product_api_admin_token or "")
        product_token = str(settings.product_api_token or "")
        if admin_token and hmac.compare_digest(token, admin_token):
            return ProductRequestIdentity(
                tenant_id="admin",
                principal="admin-token",
                authenticated=True,
                is_admin=True,
            )
        if not product_token or not hmac.compare_digest(token, product_token):
            return self._blocked("auth_required", 401)
        try:
            tenant_id = normalize_tenant_id(settings.product_api_token_tenant_id)
        except ValueError:
            return self._blocked("server_tenant_configuration_invalid", 503)
        if supplied_tenant and supplied_tenant != tenant_id:
            return self._blocked("tenant_identity_mismatch", 403)
        return ProductRequestIdentity(
            tenant_id=tenant_id,
            principal=f"token:{tenant_id}",
            authenticated=True,
            is_admin=False,
        )

    async def _payload_blocker(self, request: Request) -> JSONResponse | None:
        if request.method.upper() not in {"POST", "PUT", "PATCH"}:
            return None
        limit = max(int(settings.product_api_max_payload_bytes), 0)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return self._blocked("payload_too_large", 413)
        # Starlette's cached request wrapper will replay _body to the endpoint.
        request._body = bytes(body)  # type: ignore[attr-defined]
        return None

    def _rate_limited(self, key: str) -> bool:
        now = time.time()
        if len(self._requests) > 4096:
            self._requests = defaultdict(
                deque,
                {
                    request_key: window
                    for request_key, window in self._requests.items()
                    if window and now - window[-1] <= 60
                },
            )
        window = self._requests[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.product_api_rate_limit_per_minute:
            return True
        window.append(now)
        return False

    def _tenant_quota_exceeded(self, tenant_id: str) -> bool:
        quota = int(settings.product_api_tenant_daily_quota or 0)
        if quota <= 0:
            return False
        day_key = time.strftime("%Y-%m-%d", time.gmtime())
        if len(self._tenant_quota_counts) > 4096:
            self._tenant_quota_counts = defaultdict(
                int,
                {
                    key: value
                    for key, value in self._tenant_quota_counts.items()
                    if key[1] == day_key
                },
            )
        key = (tenant_id or "local", day_key)
        if self._tenant_quota_counts[key] >= quota:
            return True
        self._tenant_quota_counts[key] += 1
        return False

    def _audit_request(self, request: Request, status_code: int) -> None:
        path = Path(settings.product_api_audit_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        identity = getattr(request.state, "product_identity", None)
        tenant_id = (
            identity.tenant_id
            if isinstance(identity, ProductRequestIdentity)
            else (
                "unauthenticated"
                if settings.product_api_auth_required
                else str(request.headers.get("X-Tenant-ID", "local") or "local")[:80]
            )
        )
        row = {
            "ts": int(time.time()),
            "path": request.url.path,
            "method": request.method,
            "tenant_id": tenant_id,
            "status_code": status_code,
            "client_host_present": request.client is not None,
            "authorization_present": bool(request.headers.get("Authorization")),
            "request_body_logged": False,
            "authorization_value_logged": False,
            "audit_retention_days": settings.product_api_audit_retention_days,
        }
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        except Exception:
            AUDIT_WRITE_FAILURES.inc()

    @staticmethod
    def _metric_path(path: str) -> str:
        if path.startswith("/status/"):
            return "/status/{job_id}"
        if path.startswith("/results/"):
            return "/results/{job_id}"
        return path

    def _record_metrics(self, request: Request, status_code: int, *, blocked_code: str = "") -> None:
        code = str(blocked_code or "")
        path = self._metric_path(request.url.path)
        HTTP_REQUESTS.labels(
            method=request.method,
            path=path,
            status_code=str(status_code),
            blocked_code=code,
        ).inc()
        if code:
            BLOCKED_REQUESTS.labels(code=code).inc()

    @staticmethod
    def _blocked(code: str, status_code: int) -> JSONResponse:
        response = JSONResponse(
            {
                "status": "blocked",
                "code": code,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            },
            status_code=status_code,
        )
        response.headers["X-Block-Code"] = code
        return response


def security_metrics_text() -> str:
    return generate_latest(METRICS_REGISTRY).decode("utf-8")

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import settings

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

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        blocked = self._preflight_blocker(request)
        if blocked is not None:
            self._audit_request(request, blocked.status_code)
            self._attach_security_headers(blocked)
            self._record_metrics(request, blocked.status_code, blocked_code=str(blocked.headers.get("X-Block-Code", "") or "blocked"))
            return blocked
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

    def _preflight_blocker(self, request: Request) -> JSONResponse | None:
        path = request.url.path
        if not path.startswith(ALLOWED_PRODUCT_PREFIXES) and path not in {"/simulate"} and not path.startswith(("/status/", "/results/")):
            return self._blocked("path_not_allowed", 404)
        if (
            settings.product_api_hosted_exposure_approved
            and not settings.product_api_tls_termination_operator_verified
            and path != "/metrics"
        ):
            return self._blocked("hosted_tls_termination_not_verified", 503)
        content_length = int(request.headers.get("content-length") or 0)
        if content_length > settings.product_api_max_payload_bytes:
            return self._blocked("payload_too_large", 413)
        tenant_id = request.headers.get("X-Tenant-ID", "local")
        client_host = request.client.host if request.client else "unknown"
        rate_key = f"{tenant_id}:{client_host}"
        if self._rate_limited(rate_key):
            return self._blocked("rate_limited", 429)
        if self._tenant_quota_exceeded(tenant_id):
            return self._blocked("tenant_quota_exceeded", 429)
        if settings.product_api_auth_required:
            if path == "/metrics":
                return None
            token = request.headers.get("Authorization", "").replace("Bearer ", "", 1)
            if not settings.product_api_token or token != settings.product_api_token:
                return self._blocked("auth_required", 401)
        return None

    def _rate_limited(self, key: str) -> bool:
        now = time.time()
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
        key = (tenant_id or "local", day_key)
        if self._tenant_quota_counts[key] >= quota:
            return True
        self._tenant_quota_counts[key] += 1
        return False

    def _audit_request(self, request: Request, status_code: int) -> None:
        path = Path(settings.product_api_audit_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": int(time.time()),
            "path": request.url.path,
            "method": request.method,
            "tenant_id": request.headers.get("X-Tenant-ID", "local"),
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

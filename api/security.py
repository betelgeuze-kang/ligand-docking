from __future__ import annotations

import hmac
import json
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.config import settings
from api.request_identity import ProductRequestIdentity, normalize_tenant_id
from api.security_ledger import SecurityLedgerError, get_configured_security_ledger

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
    "server_bound_tenant_identity",
    "persistent_rate_limit",
    "persistent_tenant_quota",
    "streamed_payload_limit",
    "path_allowlist",
    "audit_log",
    "audit_retention",
    "runtime_request_counters",
    "hosted_tls_guard",
):
    SECURITY_CONTROL_GAUGE.labels(control=_control).set(1)


class _PayloadTooLarge(RuntimeError):
    pass


class ProductSecurityMiddleware:
    """Pure-ASGI product security chain with streamed body enforcement."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _path_is_allowed(path: str) -> bool:
        return any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in ALLOWED_PRODUCT_PREFIXES
        ) or path == "/simulate" or path.startswith(("/status/", "/results/"))

    @staticmethod
    def _security_ledger_path() -> str:
        configured = str(settings.product_api_security_ledger_path or "").strip()
        default = "./results/product_security.sqlite3"
        audit_path = Path(settings.product_api_audit_log_path)
        if configured in {"", default} and str(audit_path) not in {
            "results/product_audit_log.jsonl",
            "./results/product_audit_log.jsonl",
        }:
            return str(audit_path.parent / "product_security.sqlite3")
        return configured or default

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        finalized = False

        def finalize(status_code: int, blocked_code: str = "") -> None:
            nonlocal finalized
            if finalized:
                return
            finalized = True
            self._audit_request(request, status_code)
            self._record_metrics(request, status_code, blocked_code=blocked_code)

        blocked, identity = self._preflight_blocker(request)
        if identity is not None:
            request.state.product_identity = identity
        if blocked is not None:
            self._attach_security_headers(blocked)
            finalize(
                blocked.status_code,
                str(blocked.headers.get("X-Block-Code", "") or "blocked"),
            )
            await blocked(scope, receive, send)
            return

        assert identity is not None
        consumed = 0
        max_bytes = int(settings.product_api_max_payload_bytes)
        response_started = False
        response_status = 500

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                consumed += len(body)
                if consumed > max_bytes:
                    raise _PayloadTooLarge("request body exceeds configured byte limit")
            return message

        async def security_send(message: Message) -> None:
            nonlocal response_started, response_status
            if message.get("type") == "http.response.start":
                if not response_started:
                    response_status = int(message.get("status", 500))
                response_started = True
                message = dict(message)
                message["headers"] = self._headers_with_security_defaults(
                    list(message.get("headers", []))
                )
            await send(message)

        try:
            await self.app(scope, limited_receive, security_send)
        except _PayloadTooLarge:
            if response_started:
                finalize(response_status)
                raise
            response = self._blocked("payload_too_large", 413)
            self._attach_security_headers(response)
            finalize(413, "payload_too_large")
            await response(scope, receive, send)
            return
        except ClientDisconnect:
            finalize(499)
            return
        except Exception:
            finalize(response_status if response_started else 500)
            raise
        finalize(response_status if response_started else 500)

    @staticmethod
    def _attach_security_headers(response: Response) -> None:
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)

    @staticmethod
    def _headers_with_security_defaults(
        headers: list[tuple[bytes, bytes]],
    ) -> list[tuple[bytes, bytes]]:
        observed = {key.lower() for key, _ in headers}
        for key, value in SECURITY_HEADERS.items():
            encoded_key = key.lower().encode("latin-1")
            if encoded_key not in observed:
                headers.append((encoded_key, value.encode("latin-1")))
        return headers

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

        raw_content_lengths = [
            value
            for name, value in request.scope.get("headers", [])
            if bytes(name).lower() == b"content-length"
        ]
        if len(raw_content_lengths) > 1:
            return self._blocked("invalid_content_length", 400), None
        raw_content_length = raw_content_lengths[0] if raw_content_lengths else b"0"
        if not raw_content_length or not raw_content_length.isdigit():
            return self._blocked("invalid_content_length", 400), None
        content_length = int(raw_content_length)
        if content_length > settings.product_api_max_payload_bytes:
            return self._blocked("payload_too_large", 413), None

        identity_or_block = self._authenticate(request, path=path)
        if isinstance(identity_or_block, JSONResponse):
            return identity_or_block, None
        identity = identity_or_block

        if path == "/metrics":
            return None, identity

        client_host = request.client.host if request.client else "unknown"
        rate_key = f"{identity.tenant_id}:{client_host}"
        try:
            block_code = get_configured_security_ledger(
                self._security_ledger_path()
            ).consume(
                rate_key=rate_key,
                tenant_id=identity.tenant_id,
                rate_limit_per_minute=settings.product_api_rate_limit_per_minute,
                tenant_daily_quota=settings.product_api_tenant_daily_quota,
            )
        except SecurityLedgerError:
            return self._blocked("security_ledger_unavailable", 503), identity
        if block_code:
            return self._blocked(block_code, 429), identity
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

        if (
            admin_token
            and product_token
            and hmac.compare_digest(admin_token, product_token)
        ):
            return self._blocked("server_token_configuration_invalid", 503)

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

        if supplied_tenant:
            try:
                normalized_supplied_tenant = normalize_tenant_id(supplied_tenant)
            except ValueError:
                return self._blocked("invalid_tenant_id", 400)
            if normalized_supplied_tenant != tenant_id:
                return self._blocked("tenant_identity_mismatch", 403)

        return ProductRequestIdentity(
            tenant_id=tenant_id,
            principal=f"token:{tenant_id}",
            authenticated=True,
            is_admin=False,
        )

    def _audit_request(self, request: Request, status_code: int) -> None:
        path = Path(settings.product_api_audit_log_path)
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
            path.parent.mkdir(parents=True, exist_ok=True)
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

    def _record_metrics(
        self,
        request: Request,
        status_code: int,
        *,
        blocked_code: str = "",
    ) -> None:
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

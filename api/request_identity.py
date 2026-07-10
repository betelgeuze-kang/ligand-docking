from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from fastapi import HTTPException, Request

from api.config import settings

_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


@dataclass(frozen=True)
class ProductRequestIdentity:
    tenant_id: str
    principal: str
    authenticated: bool
    is_admin: bool = False


def normalize_tenant_id(value: Any, *, default: str = "local") -> str:
    tenant_id = str(value or default).strip()
    if not _TENANT_ID_RE.fullmatch(tenant_id):
        raise ValueError("tenant id must be 1-80 allowlisted characters")
    return tenant_id


def request_identity(request: Request | None) -> ProductRequestIdentity:
    if request is None:
        # Preserve trusted in-process/local callers without manufacturing an
        # HTTP request object. Any configured authentication boundary remains
        # fail-closed even if a router is mounted without security middleware.
        if bool(
            settings.product_api_hosted_exposure_approved
            or settings.product_api_auth_required
        ):
            raise HTTPException(status_code=401, detail="authenticated product identity missing")
        return ProductRequestIdentity(
            tenant_id="local",
            principal="local:local",
            authenticated=False,
            is_admin=False,
        )
    identity = getattr(request.state, "product_identity", None)
    if isinstance(identity, ProductRequestIdentity):
        return identity

    # Endpoints are normally reached through ProductSecurityMiddleware.  This
    # fallback preserves unauthenticated local/dev applications only. If auth
    # is configured, a missing middleware identity is itself an auth failure.
    if bool(
        settings.product_api_hosted_exposure_approved
        or settings.product_api_auth_required
    ):
        raise HTTPException(status_code=401, detail="authenticated product identity missing")
    tenant_id = normalize_tenant_id(request.headers.get("X-Tenant-ID", "local"))
    return ProductRequestIdentity(
        tenant_id=tenant_id,
        principal=f"local:{tenant_id}",
        authenticated=False,
        is_admin=False,
    )


def require_tenant_match(
    identity: ProductRequestIdentity,
    owner_tenant_id: Any,
    *,
    resource: str = "resource",
) -> None:
    if identity.is_admin:
        return
    owner = normalize_tenant_id(owner_tenant_id or "local")
    if owner != identity.tenant_id:
        raise HTTPException(status_code=404, detail=f"{resource} not found")


def require_admin(identity: ProductRequestIdentity) -> None:
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail="administrator authorization required")

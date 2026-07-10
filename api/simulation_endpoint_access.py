from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api.config import settings
from api.job_store import SQLiteJobStore
from api.request_identity import ProductRequestIdentity, require_tenant_match
from api.simulation_job_ownership import (
    SQLiteSimulationJobOwnershipStore,
    create_owned_job,
    validate_simulation_job_id,
)

_configured_ownership_store: SQLiteSimulationJobOwnershipStore | None = None
_configured_ownership_store_path: str | None = None


def _normalized_path(path_like: object) -> str:
    return str(Path(str(path_like)).expanduser())


def get_configured_simulation_ownership_store(
    job_store: SQLiteJobStore,
) -> SQLiteSimulationJobOwnershipStore:
    """Return an ownership ledger colocated with the active job store."""

    global _configured_ownership_store, _configured_ownership_store_path
    configured_path = _normalized_path(job_store.path)
    if (
        _configured_ownership_store is None
        or _configured_ownership_store_path != configured_path
    ):
        _configured_ownership_store = SQLiteSimulationJobOwnershipStore(
            configured_path
        )
        _configured_ownership_store_path = configured_path
    return _configured_ownership_store


def reset_configured_simulation_ownership_store_for_tests() -> None:
    global _configured_ownership_store, _configured_ownership_store_path
    _configured_ownership_store = None
    _configured_ownership_store_path = None


def create_simulation_job_for_identity(
    job_store: SQLiteJobStore,
    identity: ProductRequestIdentity,
    job_id: Any,
    request_data: dict[str, Any],
    *,
    status: str = "submitted",
    max_attempts: int = 3,
) -> dict[str, Any]:
    ownership_store = get_configured_simulation_ownership_store(job_store)
    return create_owned_job(
        job_store,
        ownership_store,
        identity,
        job_id,
        request_data,
        status=status,
        max_attempts=max_attempts,
    )


def _legacy_local_access_allowed(identity: ProductRequestIdentity) -> bool:
    """Preserve trusted local tests/tools without weakening hosted auth mode."""

    return bool(
        not settings.product_api_auth_required
        and not settings.product_api_hosted_exposure_approved
        and not identity.authenticated
        and not identity.is_admin
        and identity.tenant_id == "local"
    )


def get_simulation_job_for_identity(
    job_store: SQLiteJobStore,
    identity: ProductRequestIdentity,
    job_id: Any,
    *,
    resource: str = "job",
) -> dict[str, Any]:
    """Load a job with tenant authorization and a narrow local compatibility mode.

    Authenticated or hosted requests always require an ownership row. A legacy
    unowned row may be read only by the unauthenticated `local` identity while
    both authentication and hosted exposure are disabled. This avoids silently
    assigning legacy rows and keeps production fail-closed.
    """

    normalized_job_id = validate_simulation_job_id(job_id)
    record = job_store.get_job(normalized_job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"{resource} not found")

    ownership_store = get_configured_simulation_ownership_store(job_store)
    owner = ownership_store.owner_for_job(normalized_job_id)
    if owner is None:
        if _legacy_local_access_allowed(identity):
            return record
        raise HTTPException(status_code=404, detail=f"{resource} not found")

    require_tenant_match(identity, owner, resource=resource)
    return record

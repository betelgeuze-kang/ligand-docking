from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from betelgeuze_product.job_ledger_atomic import install_atomic_job_ledger_writes

# Install atomic persistence before importing the legacy router. Cancel, retry,
# lease, heartbeat, failure, and stale-lease functions resolve the writer from
# their module globals when called, so the replacement covers the whole API
# orchestration surface.
install_atomic_job_ledger_writes()

from api import product as legacy_product  # noqa: E402
from api.config import settings  # noqa: E402
from api.docking_dispatch import dispatch_docking_job_if_eligible  # noqa: E402
from api.job_store import get_configured_job_store  # noqa: E402
from betelgeuze_product.atomic_io import atomic_write_json  # noqa: E402
from betelgeuze_product.docking_request import build_docking_job_record  # noqa: E402
from betelgeuze_product.engine_dispatch import (  # noqa: E402
    build_customer_production_dispatch_manifest,
)
from betelgeuze_product.payload_privacy import sanitize_request_for_ledger  # noqa: E402
from betelgeuze_product.private_payload_store import (  # noqa: E402
    PrivatePayloadConfigurationError,
    PrivatePayloadError,
    PrivatePayloadStore,
)

router = legacy_product.router


def _remove_legacy_submit_route() -> None:
    retained = []
    for route in router.routes:
        path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if path.endswith("/docking/jobs") and "POST" in methods:
            continue
        retained.append(route)
    router.routes[:] = retained


def _jobs_dir() -> Path:
    return Path(settings.results_storage_path) / "product_docking_jobs"


def _safe_submission_response(
    record: dict[str, Any],
    *,
    dispatch_outcome: dict[str, Any],
) -> dict[str, Any]:
    response = dict(record)
    for key in (
        "private_payload_ref",
        "private_payload_ciphertext_sha256",
        "materialization_ligands",
    ):
        response.pop(key, None)
    response.update(
        {
            "private_payload_ref_present": bool(record.get("private_payload_ref")),
            "private_payload_store_ready": record.get("private_payload_store_ready") is True,
            "input_materialization_ready": record.get("input_materialization_ready") is True,
            "execution_mode": str(
                (record.get("engine_dispatch_manifest") or {}).get("execution_mode") or ""
            ),
            "worker_dispatch_enqueued": bool(dispatch_outcome.get("dispatched")),
            "worker_dispatch_reason": str(dispatch_outcome.get("reason") or ""),
            "worker_dispatch_outbox_event_id": str(
                (dispatch_outcome.get("enqueue") or {}).get("event_id") or ""
            ),
            "links": {
                "self": f"/product/docking/jobs/{record['job_id']}",
                "history": f"/product/docking/jobs/{record['job_id']}/history",
                "cancel": f"/product/docking/jobs/{record['job_id']}/cancel",
                "retry": f"/product/docking/jobs/{record['job_id']}/retry",
            },
        }
    )
    return response


def _persist_public_record(record: dict[str, Any]) -> Path:
    path = _jobs_dir() / f"{record['job_id']}.json"
    safe_record = sanitize_request_for_ledger(record)
    return atomic_write_json(path, safe_record, mode=0o600)


_remove_legacy_submit_route()


@router.post("/docking/jobs")
async def submit_secure_docking_job(
    payload: legacy_product.DockingJobRequest,
    request: Request,
) -> dict[str, Any]:
    request_payload = legacy_product._model_to_dict(payload)
    job_id = str(uuid.uuid4())
    record = build_docking_job_record(
        request_payload,
        job_id=job_id,
        source_host=request.client.host if request.client else "",
        residual_registry_packet=legacy_product._read_json_object(
            legacy_product.RESIDUAL_MODEL_REGISTRY_ARTIFACT
        ),
        scope_claim_guard_packet=legacy_product._read_json_object(
            legacy_product.PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT
        ),
    )
    record["engine_dispatch_manifest"] = build_customer_production_dispatch_manifest(
        job_id=job_id,
        target_id=str(record.get("target_id") or ""),
        family=str(record.get("family") or ""),
        ligand_model_hint="auto",
    )
    record["engine_dispatch_ready"] = bool(
        record["engine_dispatch_manifest"].get("dispatch_ready")
    )
    record["scoring_ranking_contract_ready"] = bool(
        record["engine_dispatch_manifest"].get("engine_roadmap_ready")
    )

    dispatch_outcome: dict[str, Any] = {
        "dispatched": False,
        "reason": "contract_validation_failed",
        "job_id": job_id,
    }
    if record.get("validation_status") == "pass":
        store: PrivatePayloadStore | None = None
        try:
            store = PrivatePayloadStore.from_settings(settings)
            private_metadata = store.put(
                job_id=job_id,
                payload=request_payload,
                expected_request_sha256=str(record.get("request_sha256") or ""),
            )
            record.update(private_metadata)
            record["input_materialization_ready"] = True
            record["private_payload_ligand_count"] = int(record.get("ligand_count") or 0)
            # The public ledger must never carry raw ligand sources. The worker
            # resolves them from the authenticated encrypted payload reference.
            record["materialization_ligands"] = []
            _persist_public_record(record)
        except PrivatePayloadConfigurationError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "private_payload_store_not_configured",
                    "message": str(exc),
                    "execution_enabled": False,
                    "docking_results_emitted": False,
                },
            ) from exc
        except PrivatePayloadError as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "private_payload_store_failed",
                    "message": str(exc),
                    "execution_enabled": False,
                    "docking_results_emitted": False,
                },
            ) from exc
        except Exception:
            if store is not None and record.get("private_payload_ref"):
                try:
                    store.delete(str(record["private_payload_ref"]))
                except PrivatePayloadError:
                    pass
            raise

        dispatch_outcome = dispatch_docking_job_if_eligible(
            record,
            jobs_dir=_jobs_dir(),
            store=get_configured_job_store(),
        )
    else:
        record["input_materialization_ready"] = False
        record["private_payload_store_ready"] = False
        _persist_public_record(record)

    return _safe_submission_response(record, dispatch_outcome=dispatch_outcome)

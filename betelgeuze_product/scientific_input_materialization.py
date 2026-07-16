"""Worker-side scientific-input receipt recheck for docking materializers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from betelgeuze_product.docking_materialization_errors import DockingMaterializationError
from betelgeuze_product.scientific_input_provenance import (
    build_scientific_input_provenance,
    verify_scientific_input_provenance,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def recover_private_request(docking_job_id: str, request_sha256: str) -> dict[str, Any] | None:
    """Recover one encrypted request bound to job and request identity."""

    if not docking_job_id or not request_sha256:
        return None
    try:
        from betelgeuze_product.docking_private_payload import (
            configured_store,
            recover_docking_request,
        )

        recovered = recover_docking_request(
            configured_store(),
            job_id=docking_job_id,
            request_sha256=request_sha256,
        )
    except Exception:
        return None
    return recovered if isinstance(recovered, dict) else None


def _receipt_from(params: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    value = params.get("scientific_input_provenance")
    if not isinstance(value, dict):
        value = ledger.get("scientific_input_provenance")
    return dict(value) if isinstance(value, dict) else {}


def _manifest_from(params: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    value = params.get("engine_dispatch_manifest")
    if not isinstance(value, dict):
        value = ledger.get("engine_dispatch_manifest")
    return dict(value) if isinstance(value, dict) else {}


def recheck_scientific_input_for_materialization(
    *,
    params: dict[str, Any],
    ledger: dict[str, Any],
    docking_job_id: str,
    root: str | Path,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Recover inputs and reissue their receipt immediately before materialization.

    The API-generated simulation request explicitly carries
    ``scientific_input_provenance_required=true`` for restricted production. A
    present-but-false flag is rejected. An absent flag remains a legacy local
    materializer contract and does not gain a verified status.
    """

    request_sha256 = _text(params.get("request_sha256") or ledger.get("request_sha256"))
    recovered_request = recover_private_request(docking_job_id, request_sha256)
    mode = _text(params.get("runner_execution_mode"))
    flag_present = "scientific_input_provenance_required" in params
    required = params.get("scientific_input_provenance_required") is True

    if mode == "restricted-production" and flag_present and not required:
        raise DockingMaterializationError("scientific_input_provenance_enforcement_disabled")
    if not required:
        return recovered_request, {
            "required": False,
            "verified": False,
            "status": "legacy_materialization_request_not_bound",
            "receipt_sha256": "",
            "claim_safe": False,
        }
    if mode != "restricted-production":
        raise DockingMaterializationError("scientific_input_provenance_required_for_wrong_execution_mode")
    if params.get("private_payload_stored") is not True or ledger.get("private_payload_stored") is not True:
        raise DockingMaterializationError("scientific_input_private_payload_not_stored")
    if recovered_request is None:
        raise DockingMaterializationError("scientific_input_private_payload_unavailable")

    receipt = _receipt_from(params, ledger)
    manifest = _manifest_from(params, ledger)
    ready, reason = verify_scientific_input_provenance(
        receipt,
        request_sha256=request_sha256,
        dispatch_manifest=manifest,
        require_ready=True,
    )
    if not ready:
        raise DockingMaterializationError(reason)

    rebuilt = build_scientific_input_provenance(
        recovered_request,
        request_sha256=request_sha256,
        dispatch_manifest=manifest,
        root=root,
    )
    rebuilt_ready, rebuilt_reason = verify_scientific_input_provenance(
        rebuilt,
        request_sha256=request_sha256,
        dispatch_manifest=manifest,
        require_ready=True,
    )
    if not rebuilt_ready:
        raise DockingMaterializationError(rebuilt_reason)
    if _text(rebuilt.get("receipt_sha256")) != _text(receipt.get("receipt_sha256")):
        raise DockingMaterializationError("scientific_input_provenance_recheck_mismatch")
    expected_sha = _text(params.get("scientific_input_provenance_sha256"))
    if expected_sha and expected_sha != _text(receipt.get("receipt_sha256")):
        raise DockingMaterializationError("scientific_input_provenance_queue_digest_mismatch")

    return recovered_request, {
        "required": True,
        "verified": True,
        "status": "scientific_input_provenance_rechecked",
        "receipt_sha256": _text(receipt.get("receipt_sha256")),
        "request_sha256": request_sha256,
        "runner_profile_id": _text(receipt.get("runner_profile_id")),
        "explicit_pocket": bool((receipt.get("pocket") or {}).get("explicit") is True),
        "ligand_count": int(receipt.get("ligand_count") or 0),
        "claim_safe": False,
    }


__all__ = [
    "recover_private_request",
    "recheck_scientific_input_for_materialization",
]

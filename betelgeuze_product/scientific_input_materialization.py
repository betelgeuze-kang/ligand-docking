"""Worker-side scientific-input receipt recheck for docking materializers."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import secrets
import stat
from typing import Any

from betelgeuze_product.docking_materialization_errors import DockingMaterializationError
from betelgeuze_product.scientific_input_provenance import (
    MAX_SCIENTIFIC_INPUT_BYTES,
    build_scientific_input_provenance,
    verify_scientific_input_provenance,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _request_or_metadata(request: dict[str, Any], key: str) -> Any:
    value = request.get(key)
    if value not in (None, "", []):
        return value
    metadata = request.get("metadata")
    return metadata.get(key) if isinstance(metadata, dict) else None


def _finite_vector(value: Any, *, length: int, positive: bool = False) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    result: list[float] = []
    for item in value:
        if isinstance(item, bool):
            return None
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or (positive and number <= 0.0):
            return None
        result.append(number)
    return result


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


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _read_regular_file_bytes(path_value: str, *, root: Path) -> bytes:
    root_path = Path(os.path.abspath(str(root.expanduser())))
    requested = Path(path_value).expanduser()
    relative_input = not requested.is_absolute()
    logical = Path(os.path.abspath(str(root_path / requested if relative_input else requested)))
    if relative_input and not _is_within(root_path, logical):
        raise DockingMaterializationError("scientific_input_relative_path_escapes_root")

    cursor = Path(logical.anchor)
    try:
        for component in logical.parts[1:]:
            cursor = cursor / component
            metadata = os.lstat(cursor)
            if stat.S_ISLNK(metadata.st_mode):
                raise DockingMaterializationError("scientific_input_path_contains_symlink")
    except OSError as exc:
        raise DockingMaterializationError("scientific_input_file_unavailable_or_unsafe") from exc

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        file_fd = os.open(logical, flags)
    except OSError as exc:
        raise DockingMaterializationError("scientific_input_file_unavailable_or_unsafe") from exc
    payload = bytearray()
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise DockingMaterializationError("scientific_input_path_not_regular_file")
        if before.st_nlink != 1:
            raise DockingMaterializationError("scientific_input_path_hard_link_forbidden")
        if before.st_size < 0 or before.st_size > MAX_SCIENTIFIC_INPUT_BYTES:
            raise DockingMaterializationError("scientific_input_file_size_out_of_bounds")
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > MAX_SCIENTIFIC_INPUT_BYTES:
                raise DockingMaterializationError("scientific_input_file_size_out_of_bounds")
        after = os.fstat(file_fd)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or len(payload) != before.st_size:
            raise DockingMaterializationError("scientific_input_file_changed_during_snapshot")
        return bytes(payload)
    finally:
        os.close(file_fd)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        directory_fd = os.open(path.parent, directory_flags)
    except OSError as exc:
        raise DockingMaterializationError("scientific_input_snapshot_directory_unsafe") from exc
    temporary_name = f".{path.name}.{secrets.token_hex(16)}.tmp"
    file_fd = -1
    try:
        file_fd = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise DockingMaterializationError("scientific_input_snapshot_not_exclusive_regular_file")
        view = memoryview(payload)
        while view:
            written = os.write(file_fd, view)
            if written <= 0:
                raise DockingMaterializationError("scientific_input_snapshot_short_write")
            view = view[written:]
        os.fsync(file_fd)
        os.close(file_fd)
        file_fd = -1
        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
    except Exception:
        if file_fd >= 0:
            os.close(file_fd)
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except OSError:
            pass
        raise
    finally:
        os.close(directory_fd)


def materialize_verified_pdb_structure(
    request: dict[str, Any],
    receipt: dict[str, Any],
    *,
    destination: str | Path,
    root: str | Path,
) -> dict[str, Any]:
    """Snapshot the exact verified receptor bytes into a job-local PDB file."""

    structure = receipt.get("structure") if isinstance(receipt.get("structure"), dict) else {}
    source_kind = _text(structure.get("source_kind"))
    expected_sha256 = _text(structure.get("source_sha256"))
    expected_size = int(structure.get("source_size_bytes") or 0)
    if structure.get("content_bytes_verified") is not True or not expected_sha256:
        raise DockingMaterializationError("scientific_input_structure_bytes_not_verified")

    if source_kind == "pdb_content":
        value = request.get("pdb_content")
        if not isinstance(value, str) or not value:
            raise DockingMaterializationError("scientific_input_pdb_content_missing")
        payload = value.encode("utf-8")
    elif source_kind == "pdb_path":
        value = _text(request.get("pdb_path"))
        if not value:
            raise DockingMaterializationError("scientific_input_pdb_path_missing")
        payload = _read_regular_file_bytes(value, root=Path(root))
    elif source_kind in {"mmcif_content", "mmcif_path"}:
        raise DockingMaterializationError("scientific_input_mmcif_not_supported_by_htvs_materializer")
    else:
        raise DockingMaterializationError("scientific_input_structure_source_not_materializable")

    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != expected_sha256 or len(payload) != expected_size:
        raise DockingMaterializationError("scientific_input_structure_snapshot_mismatch")
    destination_path = Path(destination)
    _atomic_write_bytes(destination_path, payload)
    return {
        "status": "scientific_input_receptor_snapshot_ready",
        "path": str(destination_path),
        "sha256": observed_sha256,
        "size_bytes": len(payload),
        "source_kind": source_kind,
        "claim_safe": False,
    }


def explicit_pocket_materialization(
    request: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Return execution fields for the exact explicit pocket bound by the receipt."""

    pocket = receipt.get("pocket") if isinstance(receipt.get("pocket"), dict) else {}
    definition_kind = _text(pocket.get("definition_kind"))
    definition_sha256 = _text(pocket.get("definition_sha256"))
    if pocket.get("explicit") is not True or not definition_kind or not definition_sha256:
        raise DockingMaterializationError("scientific_input_explicit_pocket_missing")

    base: dict[str, Any] = {
        "pocket_definition_kind": definition_kind,
        "pocket_definition_sha256": definition_sha256,
        "pocket_residue_count": int(pocket.get("residue_count") or 0),
        "claim_safe": False,
    }
    if definition_kind == "center_box":
        center = _finite_vector(_request_or_metadata(request, "pocket_center"), length=3)
        box = _finite_vector(
            _request_or_metadata(request, "pocket_box_size"),
            length=3,
            positive=True,
        )
        if center is None or box is None:
            raise DockingMaterializationError("scientific_input_explicit_pocket_recovery_failed")
        return {
            **base,
            "pocket_status": "explicit_center_box_ready",
            "pocket_method": "customer_explicit_center_box",
            "pocket_x": center[0],
            "pocket_y": center[1],
            "pocket_z": center[2],
            "pocket_center_x": center[0],
            "pocket_center_y": center[1],
            "pocket_center_z": center[2],
            "pocket_box_size_x": box[0],
            "pocket_box_size_y": box[1],
            "pocket_box_size_z": box[2],
            "pocket_radius_a": 0.0,
            "materialization_supported": True,
        }
    if definition_kind == "center_radius":
        center = _finite_vector(_request_or_metadata(request, "pocket_center"), length=3)
        raw_radius = _request_or_metadata(request, "pocket_radius_a")
        try:
            radius = float(raw_radius)
        except (TypeError, ValueError):
            radius = math.nan
        if center is None or not math.isfinite(radius) or radius <= 0.0:
            raise DockingMaterializationError("scientific_input_explicit_pocket_recovery_failed")
        return {
            **base,
            "pocket_status": "explicit_center_radius_ready",
            "pocket_method": "customer_explicit_center_radius",
            "pocket_x": center[0],
            "pocket_y": center[1],
            "pocket_z": center[2],
            "pocket_center_x": center[0],
            "pocket_center_y": center[1],
            "pocket_center_z": center[2],
            "pocket_radius_a": radius,
            "materialization_supported": True,
        }
    if definition_kind == "residue_indices":
        return {
            **base,
            "pocket_status": "explicit_residue_indices_not_materializable",
            "pocket_method": "customer_explicit_residue_indices",
            "materialization_supported": False,
        }
    raise DockingMaterializationError("scientific_input_pocket_definition_unknown")


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

    structure = receipt.get("structure") if isinstance(receipt.get("structure"), dict) else {}
    pocket = receipt.get("pocket") if isinstance(receipt.get("pocket"), dict) else {}
    return recovered_request, {
        "required": True,
        "verified": True,
        "status": "scientific_input_provenance_rechecked",
        "receipt_sha256": _text(receipt.get("receipt_sha256")),
        "request_sha256": request_sha256,
        "runner_profile_id": _text(receipt.get("runner_profile_id")),
        "structure_source_kind": _text(structure.get("source_kind")),
        "structure_sha256": _text(structure.get("source_sha256")),
        "explicit_pocket": pocket.get("explicit") is True,
        "pocket_definition_kind": _text(pocket.get("definition_kind")),
        "pocket_definition_sha256": _text(pocket.get("definition_sha256")),
        "ligand_count": int(receipt.get("ligand_count") or 0),
        "claim_safe": False,
    }


__all__ = [
    "explicit_pocket_materialization",
    "materialize_verified_pdb_structure",
    "recover_private_request",
    "recheck_scientific_input_for_materialization",
]

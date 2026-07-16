"""Fail-closed provenance receipts for product docking scientific inputs.

The public docking ledger must not retain raw receptor or ligand content.  This
module therefore records bounded byte digests, source kinds, explicit-pocket
identity, and request/dispatch bindings without copying the scientific payload.
Implementation readiness is deliberately separate from scientific or product
claim safety.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any

SCIENTIFIC_INPUT_PROVENANCE_SCHEMA_VERSION = "scientific_input_provenance_v1"
MAX_SCIENTIFIC_INPUT_BYTES = 64 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STRUCTURE_FIELDS = ("pdb_content", "pdb_path", "mmcif_content", "mmcif_path", "pdb_id")
_LIGAND_FIELDS = ("smiles", "inchi", "sdf_path", "mol2_path", "pdbqt_path", "compound_id")
_CURRENT_MATERIALIZABLE_LIGAND_FIELDS = {"smiles", "inchi"}


class ScientificInputProvenanceError(ValueError):
    """Raised when a receipt cannot be built or verified safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _valid_sha256(value: Any) -> bool:
    return bool(_SHA256_RE.fullmatch(_text(value)))


def _file_digest(path_value: str, *, root: Path) -> tuple[str, int]:
    """Hash one bounded regular single-link file without following symlinks."""

    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    logical = Path(os.path.abspath(str(candidate)))

    # Reject every symlink in the caller-provided path before opening the final
    # component.  The descriptor checks below still own the final byte identity.
    cursor = Path(logical.anchor)
    for component in logical.parts[1:]:
        cursor = cursor / component
        metadata = os.lstat(cursor)
        if stat.S_ISLNK(metadata.st_mode):
            raise ScientificInputProvenanceError("scientific_input_path_contains_symlink")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    file_fd = os.open(logical, flags)
    digest = hashlib.sha256()
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ScientificInputProvenanceError("scientific_input_path_not_regular_file")
        if before.st_nlink != 1:
            raise ScientificInputProvenanceError("scientific_input_path_hard_link_forbidden")
        if before.st_size < 0 or before.st_size > MAX_SCIENTIFIC_INPUT_BYTES:
            raise ScientificInputProvenanceError("scientific_input_file_size_out_of_bounds")
        observed = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > MAX_SCIENTIFIC_INPUT_BYTES:
                raise ScientificInputProvenanceError("scientific_input_file_size_out_of_bounds")
            digest.update(chunk)
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
        if before_identity != after_identity or observed != before.st_size:
            raise ScientificInputProvenanceError("scientific_input_file_changed_during_hash")
        return digest.hexdigest(), observed
    finally:
        os.close(file_fd)


def _inline_digest(value: str) -> tuple[str, int]:
    raw = value.encode("utf-8")
    if not raw or len(raw) > MAX_SCIENTIFIC_INPUT_BYTES:
        raise ScientificInputProvenanceError("scientific_input_inline_size_out_of_bounds")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _source_digest(
    source_kind: str,
    source_value: str,
    *,
    root: Path,
) -> tuple[str, int, bool, str]:
    if source_kind in {"pdb_content", "mmcif_content", "smiles", "inchi"}:
        try:
            digest, size = _inline_digest(source_value)
            return digest, size, True, ""
        except ScientificInputProvenanceError as exc:
            return "", 0, False, str(exc)
    if source_kind in {"pdb_path", "mmcif_path", "sdf_path", "mol2_path", "pdbqt_path"}:
        try:
            digest, size = _file_digest(source_value, root=root)
            return digest, size, True, ""
        except (OSError, ScientificInputProvenanceError):
            return "", 0, False, "scientific_input_file_unavailable_or_unsafe"
    return "", 0, False, "scientific_input_source_bytes_unavailable"


def _structure_receipt(payload: dict[str, Any], *, root: Path) -> tuple[dict[str, Any], list[str]]:
    present = [(key, _text(payload.get(key))) for key in _STRUCTURE_FIELDS if _text(payload.get(key))]
    blockers: list[str] = []
    if len(present) != 1:
        blockers.append("structure_source_must_be_exactly_one")
        return {
            "source_kind": "",
            "source_reference_sha256": "",
            "source_sha256": "",
            "source_size_bytes": 0,
            "content_bytes_verified": False,
        }, blockers

    source_kind, source_value = present[0]
    digest, size, verified, reason = _source_digest(source_kind, source_value, root=root)
    if not verified:
        blockers.append(reason or "structure_source_bytes_unavailable")
    return {
        "source_kind": source_kind,
        "source_reference_sha256": (
            _sha256_text(source_value) if source_kind in {"pdb_path", "mmcif_path", "pdb_id"} else ""
        ),
        "source_sha256": digest,
        "source_size_bytes": int(size),
        "content_bytes_verified": bool(verified),
    }, blockers


def _ligand_id(row: dict[str, Any], index: int) -> str:
    return _text(row.get("ligand_id") or row.get("id") or row.get("name") or f"ligand_{index}")


def _ligand_receipts(payload: dict[str, Any], *, root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    raw_rows = payload.get("ligands")
    if not isinstance(raw_rows, list) or not raw_rows:
        return [], ["ligands_missing"]

    receipts: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, raw_row in enumerate(raw_rows, start=1):
        row = raw_row if isinstance(raw_row, dict) else {}
        present = [(key, _text(row.get(key))) for key in _LIGAND_FIELDS if _text(row.get(key))]
        ligand_id = _ligand_id(row, index)
        row_blockers: list[str] = []
        if len(present) != 1:
            row_blockers.append("ligand_source_must_be_exactly_one")
            source_kind = ""
            source_value = ""
            digest = ""
            size = 0
            verified = False
        else:
            source_kind, source_value = present[0]
            digest, size, verified, reason = _source_digest(source_kind, source_value, root=root)
            if not verified:
                row_blockers.append(reason or "ligand_source_bytes_unavailable")
            if source_kind not in _CURRENT_MATERIALIZABLE_LIGAND_FIELDS:
                row_blockers.append("ligand_source_not_materializable_by_current_runner")

        receipts.append(
            {
                "ligand_id": ligand_id,
                "source_kind": source_kind,
                "source_reference_sha256": (
                    _sha256_text(source_value)
                    if source_kind in {"sdf_path", "mol2_path", "pdbqt_path", "compound_id"}
                    else ""
                ),
                "source_sha256": digest,
                "source_size_bytes": int(size),
                "content_bytes_verified": bool(verified),
                "materialization_supported": source_kind in _CURRENT_MATERIALIZABLE_LIGAND_FIELDS,
                "blockers": sorted(set(row_blockers)),
            }
        )
        blockers.extend(f"{ligand_id}:{reason}" for reason in row_blockers)
    return receipts, blockers


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("metadata")
    return value if isinstance(value, dict) else {}


def _payload_or_metadata(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    return value if value not in (None, "", []) else _metadata(payload).get(key)


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


def _pocket_receipt(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    raw_indices = _payload_or_metadata(payload, "pocket_residue_indices")
    center = _finite_vector(_payload_or_metadata(payload, "pocket_center"), length=3)
    box_size = _finite_vector(_payload_or_metadata(payload, "pocket_box_size"), length=3, positive=True)
    radius_value = _payload_or_metadata(payload, "pocket_radius_a")
    radius: float | None = None
    if radius_value not in (None, ""):
        try:
            radius = float(radius_value)
        except (TypeError, ValueError):
            radius = None
        if radius is None or not math.isfinite(radius) or radius <= 0.0:
            radius = None

    indices: list[int] | None = None
    if isinstance(raw_indices, list) and raw_indices:
        candidate: list[int] = []
        for item in raw_indices:
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                candidate = []
                break
            candidate.append(int(item))
        if candidate and len(candidate) == len(set(candidate)):
            indices = sorted(candidate)

    definitions: list[tuple[str, dict[str, Any]]] = []
    if indices is not None:
        definitions.append(("residue_indices", {"residue_indices": indices}))
    if center is not None and box_size is not None and radius is None:
        definitions.append(("center_box", {"center": center, "box_size": box_size}))
    if center is not None and radius is not None and box_size is None:
        definitions.append(("center_radius", {"center": center, "radius_a": radius}))

    if len(definitions) != 1:
        reason = "explicit_pocket_definition_missing" if not definitions else "multiple_explicit_pocket_definitions"
        return {
            "explicit": False,
            "definition_kind": "",
            "definition_sha256": "",
            "residue_count": 0,
        }, [reason]

    definition_kind, definition = definitions[0]
    return {
        "explicit": True,
        "definition_kind": definition_kind,
        "definition_sha256": _canonical_sha256(definition),
        "residue_count": len(indices or []),
    }, []


def build_scientific_input_provenance(
    payload: dict[str, Any],
    *,
    request_sha256: str,
    dispatch_manifest: dict[str, Any],
    root: str | Path,
) -> dict[str, Any]:
    """Build a redacted receipt bound to exact scientific input bytes."""

    if not isinstance(payload, dict):
        raise ScientificInputProvenanceError("scientific input payload must be an object")
    manifest = dict(dispatch_manifest) if isinstance(dispatch_manifest, dict) else {}
    root_path = Path(root).expanduser().resolve(strict=False)
    structure, structure_blockers = _structure_receipt(payload, root=root_path)
    ligands, ligand_blockers = _ligand_receipts(payload, root=root_path)
    pocket, pocket_blockers = _pocket_receipt(payload)
    runner_profile_id = _text(manifest.get("runner_profile_id"))

    blockers = [*structure_blockers, *ligand_blockers, *pocket_blockers]
    if not _valid_sha256(request_sha256):
        blockers.append("request_sha256_invalid")
    if not runner_profile_id:
        blockers.append("runner_profile_id_missing")
    if not manifest:
        blockers.append("dispatch_manifest_missing")

    content_ready = bool(
        structure.get("content_bytes_verified") is True
        and ligands
        and all(row.get("content_bytes_verified") is True for row in ligands)
        and all(row.get("materialization_supported") is True for row in ligands)
        and pocket.get("explicit") is True
    )
    unique_blockers = sorted(set(str(reason) for reason in blockers if str(reason)))
    body = {
        "schema_version": SCIENTIFIC_INPUT_PROVENANCE_SCHEMA_VERSION,
        "request_sha256": _text(request_sha256),
        "runner_profile_id": runner_profile_id,
        "dispatch_manifest_sha256": _canonical_sha256(manifest) if manifest else "",
        "structure": structure,
        "ligands": ligands,
        "ligand_count": len(ligands),
        "pocket": pocket,
        "content_identity_ready": content_ready,
        "execution_input_ready": bool(content_ready and not unique_blockers),
        "blockers": unique_blockers,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "claim_boundary": (
            "Input byte identity and explicit-pocket provenance only. This receipt does not validate docking accuracy, "
            "affinity, force-field physics, benchmark performance, GPU parity, or customer execution."
        ),
    }
    body["receipt_sha256"] = _canonical_sha256(body)
    return body


def verify_scientific_input_provenance(
    receipt: Any,
    *,
    request_sha256: str,
    dispatch_manifest: dict[str, Any],
    require_ready: bool = True,
) -> tuple[bool, str]:
    """Verify receipt integrity and request/dispatch bindings."""

    if not isinstance(receipt, dict):
        return False, "scientific_input_provenance_missing"
    observed = _text(receipt.get("receipt_sha256"))
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if not _valid_sha256(observed) or observed != _canonical_sha256(body):
        return False, "scientific_input_provenance_digest_mismatch"
    if receipt.get("schema_version") != SCIENTIFIC_INPUT_PROVENANCE_SCHEMA_VERSION:
        return False, "scientific_input_provenance_schema_mismatch"
    if _text(receipt.get("request_sha256")) != _text(request_sha256):
        return False, "scientific_input_provenance_request_mismatch"
    manifest = dict(dispatch_manifest) if isinstance(dispatch_manifest, dict) else {}
    if _text(receipt.get("dispatch_manifest_sha256")) != (_canonical_sha256(manifest) if manifest else ""):
        return False, "scientific_input_provenance_dispatch_mismatch"
    if _text(receipt.get("runner_profile_id")) != _text(manifest.get("runner_profile_id")):
        return False, "scientific_input_provenance_profile_mismatch"
    if receipt.get("claim_safe") is not False or receipt.get("customer_execution_enabled") is not False:
        return False, "scientific_input_provenance_claim_boundary_invalid"
    if require_ready and receipt.get("execution_input_ready") is not True:
        return False, "scientific_input_provenance_not_ready"
    return True, "ready"


__all__ = [
    "MAX_SCIENTIFIC_INPUT_BYTES",
    "SCIENTIFIC_INPUT_PROVENANCE_SCHEMA_VERSION",
    "ScientificInputProvenanceError",
    "build_scientific_input_provenance",
    "verify_scientific_input_provenance",
]

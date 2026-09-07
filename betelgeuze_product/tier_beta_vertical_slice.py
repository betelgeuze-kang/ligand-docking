from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Callable

TIER_BETA_DIRECT_RUNNER_PROFILE_ID = "tier_beta_biodiscovery_direct"
TIER_BETA_WORKFLOW_ID = "tier_beta_biodiscovery_screening_v1"

SafeTextWriter = Callable[[Path, str], None]
SafeFileHasher = Callable[[Path], str]


def is_tier_beta_vertical_slice_request(request_data: dict[str, Any]) -> bool:
    params = request_data.get("runner_profile_params")
    if not isinstance(params, dict):
        params = {}
    return (
        str(request_data.get("runner_profile_id", "") or "").strip()
        == TIER_BETA_DIRECT_RUNNER_PROFILE_ID
        or str(params.get("workflow_id", "") or "").strip() == TIER_BETA_WORKFLOW_ID
    )


def _directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _write_all(file_fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(file_fd, view)
        if written <= 0:
            raise OSError("short tier-beta artifact write")
        view = view[written:]


def _standalone_atomic_write_text(path: Path, payload: str) -> None:
    """Atomically replace one standalone artifact without following links."""

    path.parent.mkdir(parents=True, exist_ok=True)
    directory_fd = os.open(path.parent, _directory_open_flags())
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
            raise OSError("temporary tier-beta artifact is not an exclusive regular file")
        _write_all(file_fd, payload.encode("utf-8"))
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


def _standalone_artifact_bytes(path: Path) -> bytes:
    """Read one standalone no-follow, single-link regular-file descriptor."""

    directory_fd = os.open(path.parent, _directory_open_flags())
    file_fd = -1
    chunks: list[bytes] = []
    try:
        file_fd = os.open(
            path.name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=directory_fd,
        )
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("tier-beta artifact is not a regular file")
        if metadata.st_nlink != 1:
            raise OSError("hard-linked tier-beta artifacts are forbidden")
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(directory_fd)


def _standalone_sha256_file(path: Path) -> str:
    return hashlib.sha256(_standalone_artifact_bytes(path)).hexdigest()


def _json_safe(value: Any) -> Any:
    from betelgeuze_engine.biodiscovery.manifest import normalize_manifest_json

    return normalize_manifest_json(value)


def _params(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("runner_profile_params")
    return dict(params) if isinstance(params, dict) else {}


def _integer_parameter(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid_{name}:expected_integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        parsed = int(value.strip())
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        parsed = int(value)
    else:
        raise ValueError(f"invalid_{name}:expected_integer")
    if parsed < minimum or (maximum is not None and parsed > maximum):
        raise ValueError(f"invalid_{name}:out_of_range")
    return parsed


def build_tier_beta_request_from_api(request_data: dict[str, Any]) -> dict[str, Any]:
    params = _params(request_data)
    protein_input = (
        params.get("protein_input")
        or params.get("pdb_content")
        or request_data.get("pdb_content")
        or params.get("pdb_path")
        or request_data.get("pdb_path")
        or ""
    )
    ligand_input = (
        params.get("ligand_input")
        or params.get("smiles")
        or params.get("sdf_content")
        or params.get("sdf_path")
        or ""
    )
    pocket_indices = params.get("pocket_residue_indices")
    if pocket_indices is not None:
        if not isinstance(pocket_indices, list) or not pocket_indices:
            raise ValueError("invalid_pocket_residue_indices:expected_nonempty_list")
        pocket_indices = [
            _integer_parameter(index, "pocket_residue_indices") for index in pocket_indices
        ]
        if len(set(pocket_indices)) != len(pocket_indices):
            raise ValueError("invalid_pocket_residue_indices:duplicates")
    return {
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "protein_input": str(protein_input or ""),
        "ligand_input": str(ligand_input or ""),
        "pocket_residue_indices": pocket_indices,
        "pose_count": _integer_parameter(params.get("pose_count", 8), "pose_count", minimum=1),
        "top_k": _integer_parameter(params.get("top_k", 3), "top_k", minimum=1),
        "stability_steps": _integer_parameter(params.get("stability_steps", 0), "stability_steps"),
        "seed": _integer_parameter(params.get("seed", 42), "seed", maximum=2**31 - 1),
    }


def _consumed_input_snapshot(manifest: dict[str, Any], name: str) -> dict[str, Any] | None:
    snapshot = None
    for stage in manifest.get("stage_records", []):
        candidate = stage.get("diagnostics", {}).get(f"{name}_input_snapshot")
        if candidate is None:
            continue
        if (
            not isinstance(candidate, dict)
            or not isinstance(candidate.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", candidate["sha256"]) is None
            or type(candidate.get("byte_count")) is not int
            or candidate["byte_count"] < 0
            or not isinstance(candidate.get("source_kind"), str)
            or not candidate["source_kind"]
        ):
            raise ValueError(f"invalid_{name}_input_snapshot")
        if snapshot is not None and candidate != snapshot:
            raise ValueError(f"conflicting_{name}_input_snapshots")
        snapshot = candidate
    return snapshot


def run_tier_beta_vertical_slice_job(
    *,
    job_id: str,
    request_data: dict[str, Any],
    results_dir: str | Path,
    artifact_writer: SafeTextWriter | None = None,
    artifact_hasher: SafeFileHasher | None = None,
) -> dict[str, Any]:
    request = build_tier_beta_request_from_api(request_data)
    # The request predicate and API schema remain importable without Torch/RDKit.
    # Load the scientific execution stack only when an approved job actually runs.
    from betelgeuze_engine.biodiscovery import TierBetaScreening
    from betelgeuze_engine.biodiscovery.manifest import verify_screening_manifest

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_artifact = artifact_writer or _standalone_atomic_write_text
    hash_artifact = artifact_hasher or _standalone_sha256_file

    service = TierBetaScreening(
        device="cpu",
        pose_count=request["pose_count"],
        top_k=request["top_k"],
        stability_steps=request["stability_steps"],
        seed=request["seed"],
    )
    result = service.screen(
        protein_input=str(request["protein_input"]),
        ligand_input=str(request["ligand_input"]),
        pocket_residue_indices=request["pocket_residue_indices"],
    )
    if not verify_screening_manifest(result.result_manifest):
        raise ValueError("invalid_screening_manifest_integrity")
    protein_snapshot = _consumed_input_snapshot(result.result_manifest, "protein")
    ligand_snapshot = _consumed_input_snapshot(result.result_manifest, "ligand")
    result_payload = {
        "artifact_type": "tier_beta_vertical_slice_result",
        "job_id": str(job_id),
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "request": {
            "pose_count": request["pose_count"],
            "top_k": request["top_k"],
            "stability_steps": request["stability_steps"],
            "seed": request["seed"],
            "pocket_residue_indices": request["pocket_residue_indices"],
            "protein_input_spec_sha256": hashlib.sha256(
                str(request["protein_input"]).encode("utf-8")
            ).hexdigest(),
            "ligand_input_spec_sha256": hashlib.sha256(
                str(request["ligand_input"]).encode("utf-8")
            ).hexdigest(),
            "protein_input_sha256": protein_snapshot["sha256"] if protein_snapshot else None,
            "ligand_input_sha256": ligand_snapshot["sha256"] if ligand_snapshot else None,
            "protein_input_snapshot": protein_snapshot,
            "ligand_input_snapshot": ligand_snapshot,
            "input_hash_scope": "consumed_byte_snapshots_when_available",
        },
        "result": _json_safe(result),
        "claim_metadata": _json_safe(result.claim_metadata),
        "result_manifest": _json_safe(result.result_manifest),
        "docking_results_emitted": bool(result.ok),
        "execution_enabled": True,
        "external_state_mutated": False,
    }
    result_path = out_dir / "tier_beta_result.json"
    write_artifact(
        result_path,
        json.dumps(result_payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
    )
    saved_bytes = _standalone_artifact_bytes(result_path)
    saved_payload = json.loads(saved_bytes)
    if saved_payload != result_payload or not verify_screening_manifest(saved_payload.get("result_manifest")):
        raise ValueError("persisted_screening_manifest_integrity_mismatch")
    result_sha = hash_artifact(result_path)
    if result_sha != hashlib.sha256(saved_bytes).hexdigest():
        raise ValueError("persisted_screening_artifact_changed")
    status = "completed" if result.ok else "failed"
    status_payload = {
        "job_id": str(job_id),
        "status": status,
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "result_file": str(result_path),
        "result_file_sha256": result_sha,
        "result_manifest_signed": True,
        "result_manifest_verified": True,
        "result_manifest_signature_scope": result.result_manifest["signature_scope"],
        "tier_beta_ok": bool(result.ok),
        "tier_beta_blocked_reason": str(result.blocked_reason),
    }
    status_path = out_dir / "status.json"
    write_artifact(
        status_path,
        json.dumps(status_payload, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
    )
    if not result.ok:
        raise RuntimeError(str(result.blocked_reason or "tier_beta_vertical_slice_failed"))
    return status_payload

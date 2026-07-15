from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
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


def _standalone_sha256_file(path: Path) -> str:
    """Hash one standalone no-follow, single-link regular-file descriptor."""

    directory_fd = os.open(path.parent, _directory_open_flags())
    file_fd = -1
    digest = hashlib.sha256()
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
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(directory_fd)


def _json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    return value


def _params(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("runner_profile_params")
    return dict(params) if isinstance(params, dict) else {}


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
    if not isinstance(pocket_indices, list):
        pocket_indices = None
    return {
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "protein_input": str(protein_input or ""),
        "ligand_input": str(ligand_input or ""),
        "pocket_residue_indices": pocket_indices,
        "pose_count": int(params.get("pose_count") or 8),
        "top_k": int(params.get("top_k") or 3),
        "stability_steps": int(params.get("stability_steps") or 0),
        "seed": int(params.get("seed") or 42),
    }


def run_tier_beta_vertical_slice_job(
    *,
    job_id: str,
    request_data: dict[str, Any],
    results_dir: str | Path,
    artifact_writer: SafeTextWriter | None = None,
    artifact_hasher: SafeFileHasher | None = None,
) -> dict[str, Any]:
    # The request predicate and API schema remain importable without Torch/RDKit.
    # Load the scientific execution stack only when an approved job actually runs.
    from betelgeuze_engine.biodiscovery import TierBetaScreening

    request = build_tier_beta_request_from_api(request_data)
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_artifact = artifact_writer or _standalone_atomic_write_text
    hash_artifact = artifact_hasher or _standalone_sha256_file

    service = TierBetaScreening(
        device="cpu",
        pose_count=int(request["pose_count"]),
        top_k=int(request["top_k"]),
        stability_steps=int(request["stability_steps"]),
        seed=int(request["seed"]),
    )
    result = service.screen(
        protein_input=str(request["protein_input"]),
        ligand_input=str(request["ligand_input"]),
        pocket_residue_indices=request["pocket_residue_indices"],
    )
    result_payload = {
        "artifact_type": "tier_beta_vertical_slice_result",
        "job_id": str(job_id),
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "request": {
            "pose_count": request["pose_count"],
            "top_k": request["top_k"],
            "stability_steps": request["stability_steps"],
            "seed": request["seed"],
            "protein_input_sha256": hashlib.sha256(
                str(request["protein_input"]).encode("utf-8")
            ).hexdigest(),
            "ligand_input_sha256": hashlib.sha256(
                str(request["ligand_input"]).encode("utf-8")
            ).hexdigest(),
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
        json.dumps(result_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
    )
    result_sha = hash_artifact(result_path)
    status = "completed" if result.ok else "failed"
    status_payload = {
        "job_id": str(job_id),
        "status": status,
        "workflow_id": TIER_BETA_WORKFLOW_ID,
        "result_file": str(result_path),
        "result_file_sha256": result_sha,
        "result_manifest_signed": bool(result.result_manifest.get("signature")),
        "tier_beta_ok": bool(result.ok),
        "tier_beta_blocked_reason": str(result.blocked_reason),
    }
    status_path = out_dir / "status.json"
    write_artifact(
        status_path,
        json.dumps(status_payload, sort_keys=True, ensure_ascii=True) + "\n",
    )
    if not result.ok:
        raise RuntimeError(str(result.blocked_reason or "tier_beta_vertical_slice_failed"))
    return status_payload

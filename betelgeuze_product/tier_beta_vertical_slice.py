from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from betelgeuze_engine.biodiscovery import TierBetaScreening

TIER_BETA_DIRECT_RUNNER_PROFILE_ID = "tier_beta_biodiscovery_direct"
TIER_BETA_WORKFLOW_ID = "tier_beta_biodiscovery_screening_v1"


def is_tier_beta_vertical_slice_request(request_data: dict[str, Any]) -> bool:
    params = request_data.get("runner_profile_params")
    if not isinstance(params, dict):
        params = {}
    return (
        str(request_data.get("runner_profile_id", "") or "").strip()
        == TIER_BETA_DIRECT_RUNNER_PROFILE_ID
        or str(params.get("workflow_id", "") or "").strip() == TIER_BETA_WORKFLOW_ID
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
) -> dict[str, Any]:
    request = build_tier_beta_request_from_api(request_data)
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
    result_path.write_text(
        json.dumps(result_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    result_sha = _sha256_file(result_path)
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
    status_path.write_text(
        json.dumps(status_payload, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    if not result.ok:
        raise RuntimeError(str(result.blocked_reason or "tier_beta_vertical_slice_failed"))
    return status_payload

"""Opt-in native EvidenceBundle emission for validated API runner scripts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle
from betelgeuze_ai_md.contracts.claim_scope import TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
from betelgeuze_ai_md.contracts.manifest import EvidenceBundle
from betelgeuze_ai_md.contracts.serialization import sha256_payload

DEFAULT_RUNNER_CLAIM_SCOPE = "restricted_local_delivery_proxy_refinement_only"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path_like: str | Path) -> dict[str, Any]:
    path = Path(path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_job_id(request: dict[str, Any], request_json_path: str) -> str:
    for key in ("job_id", "docking_job_id"):
        value = str(request.get(key, "") or "").strip()
        if value:
            return value
    path = Path(request_json_path)
    if path.name == "request.json" and path.parent.name:
        return path.parent.name
    profile_id = str(request.get("runner_profile_id", "") or "").strip()
    return profile_id or "runner_native_job"


def maybe_write_runner_native_evidence_bundle(
    evidence_bundle_path: str | Path | None,
    *,
    request_json_path: str | Path = "",
    request: dict[str, Any] | None = None,
    result_file: str | Path,
    status: str = "completed",
    claim_scope: str = DEFAULT_RUNNER_CLAIM_SCOPE,
    topology_fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    accuracy_claim_grade: str = "restricted-local-delivery",
    runner_script: str = "",
    runner_script_sha256: str = "",
    result_payload: dict[str, Any] | None = None,
    runner_metadata: dict[str, Any] | None = None,
) -> EvidenceBundle | None:
    path_value = str(evidence_bundle_path or "").strip()
    if not path_value:
        return None

    request_path = str(request_json_path or "").strip()
    resolved_request = request if isinstance(request, dict) else _read_json_object(request_path)
    result_path = Path(result_file)
    if not result_path.exists() or not result_path.is_file():
        raise FileNotFoundError(f"runner result file is required for native EvidenceBundle: {result_path}")
    if result_payload is None:
        result_payload = _read_json_object(result_path)
    request_hash = sha256_payload(resolved_request) if resolved_request else ""
    if request_path and Path(request_path).exists():
        request_hash = request_hash or _sha256_file(Path(request_path))
    result_hash = _sha256_file(result_path)

    job_id = _resolve_job_id(resolved_request, request_path)
    runner_execution: dict[str, Any] = {"runner_script": runner_script}
    if runner_script_sha256:
        runner_execution["profile_readiness"] = {"runner_script_sha256": runner_script_sha256}
    elif runner_script:
        script_path = Path(runner_script)
        if not script_path.is_absolute():
            repo_root = Path(__file__).resolve().parents[2]
            script_path = repo_root / runner_script
        if script_path.exists():
            runner_execution["profile_readiness"] = {"runner_script_sha256": _sha256_file(script_path)}

    metadata = runner_metadata if isinstance(runner_metadata, dict) else {}
    result_manifest = {
        "job_id": job_id,
        "status": status,
        "request_sha256": request_hash,
        "result_file": str(result_path),
        "result_file_sha256": result_hash,
        "claim_scope": claim_scope,
        "topology_fidelity": topology_fidelity,
        "accuracy_claim_grade": accuracy_claim_grade,
        "runner_metadata": metadata,
    }

    return write_api_evidence_bundle(
        path_value,
        job_id=job_id,
        request=resolved_request,
        result_manifest=result_manifest,
        result_payload=result_payload,
        runner_execution=runner_execution,
        status_payload={"status": status},
    )

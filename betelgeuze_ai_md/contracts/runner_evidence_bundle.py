"""Opt-in native EvidenceBundle emission for validated API runner scripts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle
from betelgeuze_ai_md.contracts.claim_scope import TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
from betelgeuze_ai_md.contracts.job_scoped_hbond import (
    build_job_scoped_hbond_evidence,
)
from betelgeuze_ai_md.contracts.manifest import EvidenceBundle
from betelgeuze_ai_md.contracts.serialization import (
    parse_finite_json_float,
    sha256_payload,
)

DEFAULT_RUNNER_CLAIM_SCOPE = "restricted_local_delivery_proxy_refinement_only"


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


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
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
            parse_float=parse_finite_json_float,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_job_id(request: dict[str, Any], request_json_path: str) -> str:
    explicit_job_id = str(request.get("job_id", "") or "").strip()
    path = Path(request_json_path)
    if path.name == "request.json" and path.parent.name:
        if path.parent.parent.name == ".attempts" and path.parent.parent.parent.name:
            attempt_job_id = path.parent.parent.parent.name
            if explicit_job_id and explicit_job_id != attempt_job_id:
                raise ValueError(
                    "request job_id does not match the active attempt path"
                )
            return attempt_job_id
    if explicit_job_id:
        return explicit_job_id
    if path.name == "request.json" and path.parent.name:
        return path.parent.name
    docking_job_id = str(request.get("docking_job_id", "") or "").strip()
    if docking_job_id:
        return docking_job_id
    profile_id = str(request.get("runner_profile_id", "") or "").strip()
    return profile_id or "runner_native_job"


def _extract_refine_element_summary(payload: dict[str, Any]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        sources.append(payload)
        score = payload.get("score")
        if isinstance(score, dict):
            sources.append(score)
    keys = (
        "refine_element_model",
        "refine_element_fallback_used",
        "refine_protein_element_fallback_used",
        "refine_ligand_element_fallback_used",
        "refine_protein_element_count",
        "refine_ligand_element_count",
        "refine_protein_element_source",
        "refine_protein_element_projection_used",
        "refine_protein_element_sequence_mapped",
        "refine_ligand_element_source",
        "refine_ligand_element_projection_used",
        "refine_ligand_element_topology_valid",
    )
    for source in sources:
        if any(key in source for key in keys):
            return {key: source.get(key) for key in keys if key in source}
    return {}


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
    # Scientific evidence is always derived from the exact JSON file hashed
    # below.  A caller-supplied in-memory payload is intentionally not trusted.
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
        "execution_request_sha256": request_hash,
        "execution_request_transform_id": "identity_v1",
        "result_file": str(result_path),
        "result_file_sha256": result_hash,
        "claim_scope": claim_scope,
        "topology_fidelity": topology_fidelity,
        "accuracy_claim_grade": accuracy_claim_grade,
        "runner_metadata": metadata,
    }
    refine_element_summary = _extract_refine_element_summary(result_payload)
    if refine_element_summary:
        result_manifest["refine_element_summary"] = refine_element_summary

    payload_for_bundle = dict(result_payload)
    scoped_hbond = build_job_scoped_hbond_evidence(
        payload_for_bundle,
        job_id=job_id,
        admission_request_sha256=request_hash,
        execution_request_sha256=request_hash,
        result_file_sha256=result_hash,
    )
    if scoped_hbond is not None:
        payload_for_bundle["job_scoped_hbond_evidence"] = scoped_hbond.to_dict()

    return write_api_evidence_bundle(
        path_value,
        job_id=job_id,
        request=resolved_request,
        result_manifest=result_manifest,
        result_payload=payload_for_bundle,
        runner_execution=runner_execution,
        status_payload={"status": status},
    )

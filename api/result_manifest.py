from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.claim_boundary import (
    CLAIM_SCOPE_PRODUCT_LIGAND,
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    GENERAL_MD_ACCURACY_CLAIM,
    PRODUCT_CLAIM_BOUNDARY_TEXT,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    general_md_accuracy_promotion_allowed,
    validate_manifest_claim_fields,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TRANSFORM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_text(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload if isinstance(payload, dict) else {"value": payload})).hexdigest()


def _sha256_file(path_like: str | Path) -> str:
    path = Path(path_like)
    if not path.exists() or not path.is_file():
        return ""
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


_RESULT_ARTIFACT_TYPES: dict[str, tuple[str, str]] = {
    ".json": ("json", "application/json"),
    ".pdb": ("pdb", "chemical/x-pdb"),
    ".sdf": ("sdf", "chemical/x-mdl-sdfile"),
    ".mol": ("mol", "chemical/x-mdl-molfile"),
    ".zip": ("zip", "application/zip"),
}


def infer_result_artifact_metadata(path_like: str | Path) -> dict[str, str]:
    suffix = Path(path_like).suffix.lower()
    artifact_type, media_type = _RESULT_ARTIFACT_TYPES.get(
        suffix,
        ("binary", "application/octet-stream"),
    )
    return {
        "result_file_suffix": suffix,
        "result_artifact_type": artifact_type,
        "result_file_media_type": media_type,
    }


def _extract_result_metadata(path_like: str | Path) -> dict[str, dict[str, Any]]:
    payload = _read_json_object(path_like)
    if not payload:
        return {}
    out: dict[str, dict[str, Any]] = {}
    claim_metadata = payload.get("claim_metadata")
    if isinstance(claim_metadata, dict):
        out["result_claim_metadata"] = dict(claim_metadata)
    hbond_summary = payload.get("hbond_evidence_summary")
    if isinstance(hbond_summary, dict):
        out["hbond_evidence_summary"] = dict(hbond_summary)
    force_residual = payload.get("force_residual_summary")
    if not isinstance(force_residual, dict):
        force_residual = payload.get("force_residual_shortlist")
    if isinstance(force_residual, dict):
        out["force_residual_summary"] = dict(force_residual)
    refine_element = _extract_refine_element_summary(payload)
    if refine_element:
        out["refine_element_summary"] = refine_element
    return out


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
        if not any(key in source for key in keys):
            continue
        return {key: source.get(key) for key in keys if key in source}
    return {}


def build_result_manifest(
    *,
    job_id: str,
    request: dict[str, Any],
    status: str,
    request_sha256: str | None = None,
    execution_request_sha256: str | None = None,
    execution_request_transform_id: str | None = None,
    result_file: str = "",
    error: str = "",
    signing_key: str,
    key_id: str,
    claim_scope: str = CLAIM_SCOPE_PRODUCT_LIGAND,
    fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    topology_fidelity: str | None = None,
    accuracy_claim_grade: str = "restricted-local-delivery",
    result_claim_metadata: dict[str, Any] | None = None,
    hbond_evidence_summary: dict[str, Any] | None = None,
    force_residual_summary: dict[str, Any] | None = None,
    refine_element_summary: dict[str, Any] | None = None,
    worker_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_fidelity = str(topology_fidelity or fidelity or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE)
    resolved_scope = str(claim_scope or CLAIM_SCOPE_PRODUCT_LIGAND)
    if accuracy_claim_grade == GENERAL_MD_ACCURACY_CLAIM and not general_md_accuracy_promotion_allowed(
        fidelity=resolved_fidelity,
        claim_scope=resolved_scope,
    ):
        raise ValueError(
            f"accuracy_claim_grade '{GENERAL_MD_ACCURACY_CLAIM}' is forbidden for fidelity={resolved_fidelity}"
        )
    resolved_request_sha256 = str(request_sha256 or "").lower()
    if resolved_request_sha256 and _SHA256_RE.fullmatch(resolved_request_sha256) is None:
        raise ValueError("request_sha256 must be a 64-character hexadecimal SHA-256")
    if not resolved_request_sha256:
        resolved_request_sha256 = _sha256_text(request)
    resolved_execution_request_sha256 = str(execution_request_sha256 or "").lower()
    if (
        resolved_execution_request_sha256
        and _SHA256_RE.fullmatch(resolved_execution_request_sha256) is None
    ):
        raise ValueError(
            "execution_request_sha256 must be a 64-character hexadecimal SHA-256"
        )
    if not resolved_execution_request_sha256:
        resolved_execution_request_sha256 = _sha256_text(request)
    resolved_transform_id = str(
        execution_request_transform_id or "identity_v1"
    ).strip()
    if _TRANSFORM_ID_RE.fullmatch(resolved_transform_id) is None:
        raise ValueError("execution_request_transform_id is invalid")
    result_file_sha256 = _sha256_file(result_file) if result_file else ""
    payload: dict[str, Any] = {
        "manifest_version": "api_result_manifest_v1",
        "job_id": job_id,
        "status": status,
        "request_sha256": resolved_request_sha256,
        "execution_request_sha256": resolved_execution_request_sha256,
        "execution_request_transform_id": resolved_transform_id,
        "result_file": result_file,
        "result_file_sha256": result_file_sha256,
        "error": error,
        "created_at_utc": _utc_now(),
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": key_id,
        "claim_scope": resolved_scope,
        "fidelity": resolved_fidelity,
        "topology_fidelity": resolved_fidelity,
        "accuracy_claim_grade": accuracy_claim_grade,
        "claim_boundary": (
            "API result manifest only; signs request/status/result-file provenance. It does not claim "
            "scientific validity, run simulations, emit fake results, or promote model outputs. "
            f"{PRODUCT_CLAIM_BOUNDARY_TEXT}"
        ),
    }
    if result_file:
        payload.update(infer_result_artifact_metadata(result_file))
    if isinstance(result_claim_metadata, dict):
        payload["result_claim_metadata"] = dict(result_claim_metadata)
    if isinstance(hbond_evidence_summary, dict):
        payload["hbond_evidence_summary"] = dict(hbond_evidence_summary)
    if isinstance(force_residual_summary, dict):
        payload["force_residual_summary"] = dict(force_residual_summary)
    if isinstance(refine_element_summary, dict):
        payload["refine_element_summary"] = dict(refine_element_summary)
    if isinstance(worker_provenance, dict):
        payload["worker_provenance"] = dict(worker_provenance)
    validate_manifest_claim_fields(payload)
    signature = hmac.new(signing_key.encode("utf-8"), _canonical_json(payload), hashlib.sha256).hexdigest()
    payload["signature"] = signature
    return payload


def verify_result_manifest(manifest: dict[str, Any], *, signing_key: str) -> bool:
    observed = str(manifest.get("signature", "") or "")
    if not observed:
        return False
    payload = {k: v for k, v in manifest.items() if k != "signature"}
    expected = hmac.new(signing_key.encode("utf-8"), _canonical_json(payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(observed, expected)


def write_result_manifest(
    path_like: str | Path,
    *,
    job_id: str,
    request: dict[str, Any],
    status: str,
    request_sha256: str | None = None,
    execution_request_sha256: str | None = None,
    execution_request_transform_id: str | None = None,
    result_file: str = "",
    error: str = "",
    signing_key: str,
    key_id: str,
    claim_scope: str = CLAIM_SCOPE_PRODUCT_LIGAND,
    fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    topology_fidelity: str | None = None,
    accuracy_claim_grade: str = "restricted-local-delivery",
    result_claim_metadata: dict[str, Any] | None = None,
    hbond_evidence_summary: dict[str, Any] | None = None,
    force_residual_summary: dict[str, Any] | None = None,
    refine_element_summary: dict[str, Any] | None = None,
    worker_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    extracted_metadata = _extract_result_metadata(result_file) if result_file else {}
    manifest = build_result_manifest(
        job_id=job_id,
        request=request,
        status=status,
        request_sha256=request_sha256,
        execution_request_sha256=execution_request_sha256,
        execution_request_transform_id=execution_request_transform_id,
        result_file=result_file,
        error=error,
        signing_key=signing_key,
        key_id=key_id,
        claim_scope=claim_scope,
        fidelity=fidelity,
        topology_fidelity=topology_fidelity,
        accuracy_claim_grade=accuracy_claim_grade,
        result_claim_metadata=(
            result_claim_metadata
            if result_claim_metadata is not None
            else extracted_metadata.get("result_claim_metadata")
        ),
        hbond_evidence_summary=(
            hbond_evidence_summary
            if hbond_evidence_summary is not None
            else extracted_metadata.get("hbond_evidence_summary")
        ),
        force_residual_summary=(
            force_residual_summary
            if force_residual_summary is not None
            else extracted_metadata.get("force_residual_summary")
        ),
        refine_element_summary=(
            refine_element_summary
            if refine_element_summary is not None
            else extracted_metadata.get("refine_element_summary")
        ),
        worker_provenance=worker_provenance,
    )
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
